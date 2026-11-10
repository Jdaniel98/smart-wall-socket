/*
 * Control task: the only owner of protection, energy, schedules and relays.
 *
 * Every 100 ms it reads the meter (every 500 ms), runs the protection state
 * machine, applies relay outputs, handles queued commands, and publishes
 * telemetry, events and reported state. None of the safety path waits on
 * the network.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "app.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sws/energy.h"
#include "sws/proto.h"

static const char *TAG = "control";

#define TICK_MS 100
#define METER_PERIOD_MS 500
#define REPORTED_PERIOD_MS (5 * 60 * 1000)
#define PENDING_MAX 32
#define MSG_BUF 1024

typedef enum {
    PEND_PROT = 1,
    PEND_BOOT,
    PEND_OUTAGE,
} pend_kind_t;

typedef struct {
    pend_kind_t kind;
    prot_event_t ev;
    int64_t start, end;
    uint64_t up_ms;
} pending_t;

static QueueHandle_t s_q;
static SemaphoreHandle_t s_snap_lock;
static control_snapshot_t s_snap;
static const board_t *s_board;

static prot_t s_prot;
static energy_acc_t s_energy;
static sched_t s_sched;
static bl0939_cal_t s_cal;
static dedupe_t s_dedupe;
static agg_t s_agg, s_prev_agg;
static sws_meas_t s_last_meas;
static uint16_t s_hold = 1000;
static uint32_t s_bad_frames;

static pending_t s_pend[PENDING_MAX];
static int s_pend_head, s_pend_count;
static uint32_t s_seq;
static bool s_reported_dirty = true;
static bool s_matter_reported_valid[SWS_OUTLETS];
static bool s_matter_reported[SWS_OUTLETS];
static bool s_saved_last_on[SWS_OUTLETS];
static heartbeat_t s_boot_hb;
static bool s_outage_checked;
static char s_buf[MSG_BUF];

uint64_t app_now_ms(void)
{
    return (uint64_t)(esp_timer_get_time() / 1000);
}

static int64_t utc_now(void)
{
    if (!net_time_synced()) {
        return 0;
    }
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (int64_t)tv.tv_sec;
}

/* Timestamp for something that happened at uptime up_ms. 0 if clock unset. */
static int64_t utc_at(uint64_t up_ms)
{
    const int64_t now = utc_now();
    if (now == 0) {
        return 0;
    }
    const uint64_t up_now = app_now_ms();
    return now - (int64_t)((up_now - up_ms) / 1000);
}

bool control_post(const ctl_msg_t *msg)
{
    if (s_q == NULL || xQueueSend(s_q, msg, pdMS_TO_TICKS(50)) != pdTRUE) {
        free(msg->json);
        return false;
    }
    return true;
}

void control_snapshot(control_snapshot_t *out)
{
    xSemaphoreTake(s_snap_lock, portMAX_DELAY);
    *out = s_snap;
    xSemaphoreGive(s_snap_lock);
}

/* ---------- persistence ---------- */

static void load_config(prot_cfg_t cfg[SWS_OUTLETS], bool last_on[SWS_OUTLETS])
{
    bl0939_cal_init(&s_cal, &s_board->frontend);
    float gains[5];
    if (storage_get_blob("cal", gains, sizeof(gains))) {
        s_cal.gain_v = gains[0];
        s_cal.gain_i[0] = gains[1];
        s_cal.gain_i[1] = gains[2];
        s_cal.gain_p[0] = gains[3];
        s_cal.gain_p[1] = gains[4];
    }
    for (int k = 0; k < SWS_OUTLETS; k++) {
        char key[8];
        snprintf(key, sizeof(key), "cfg%d", k);
        prot_cfg_default(&cfg[k], APPLIANCE_GENERAL, s_board->default_i_limit);
        prot_cfg_t stored;
        if (storage_get_blob(key, &stored, sizeof(stored)) &&
            prot_cfg_validate(&stored, &s_board->socket_limits) == NULL) {
            cfg[k] = stored;
        }
        snprintf(key, sizeof(key), "sch%d", k);
        sched_entry_t entries[SCHED_MAX];
        const uint8_t n = (uint8_t)storage_get_u32(key, 0);
        snprintf(key, sizeof(key), "scd%d", k);
        if (n > 0 && n <= SCHED_MAX && storage_get_blob(key, entries, sizeof(sched_entry_t) * n)) {
            sched_set(&s_sched, k, entries, n);
        }
    }
    const uint32_t bits = storage_get_u32("last_on", 0);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        last_on[k] = (bits >> k) & 1u;
        s_saved_last_on[k] = last_on[k];
    }
    s_hold = (uint16_t)storage_get_u32("hold", s_board->relay_cfg.hold_permille);
}

static void save_cal(void)
{
    const float gains[5] = {s_cal.gain_v, s_cal.gain_i[0], s_cal.gain_i[1], s_cal.gain_p[0],
                            s_cal.gain_p[1]};
    storage_set_blob("cal", gains, sizeof(gains));
}

static void save_last_on_if_changed(void)
{
    bool changed = false;
    uint32_t bits = 0;
    for (int k = 0; k < SWS_OUTLETS; k++) {
        if (s_prot.o[k].desired_on != s_saved_last_on[k]) {
            changed = true;
            s_saved_last_on[k] = s_prot.o[k].desired_on;
        }
        bits |= (s_saved_last_on[k] ? 1u : 0u) << k;
    }
    if (changed) {
        storage_set_u32("last_on", bits);
        s_reported_dirty = true;
    }
}

static void bump_cfg_ver(void)
{
    storage_set_u32("cfg_ver", storage_get_u32("cfg_ver", 0) + 1);
    s_reported_dirty = true;
}

/* ---------- pending events (kept until MQTT can take them) ---------- */

static void pend_push(const pending_t *p)
{
    if (s_pend_count == PENDING_MAX) {
        s_pend_head = (s_pend_head + 1) % PENDING_MAX; /* drop oldest */
        s_pend_count--;
    }
    s_pend[(s_pend_head + s_pend_count) % PENDING_MAX] = *p;
    s_pend_count++;
}

static void pend_flush(void)
{
    while (s_pend_count > 0 && net_connected()) {
        const pending_t *p = &s_pend[s_pend_head];
        const int64_t ts = utc_at(p->up_ms);
        int n = -1;
        switch (p->kind) {
        case PEND_PROT:
            n = msg_prot_event(s_buf, sizeof(s_buf), &p->ev, ts, ++s_seq);
            break;
        case PEND_BOOT: {
            const char *rr;
            switch (esp_reset_reason()) {
            case ESP_RST_POWERON: rr = "poweron"; break;
            case ESP_RST_BROWNOUT: rr = "brownout"; break;
            case ESP_RST_SW: rr = "software"; break;
            case ESP_RST_PANIC: rr = "panic"; break;
            case ESP_RST_TASK_WDT:
            case ESP_RST_INT_WDT:
            case ESP_RST_WDT: rr = "watchdog"; break;
            default: rr = "other"; break;
            }
            n = msg_boot(s_buf, sizeof(s_buf), ts, ++s_seq, SWS_FW_VERSION, rr);
            break;
        }
        case PEND_OUTAGE:
            n = msg_outage(s_buf, sizeof(s_buf), ts, ++s_seq, p->start, p->end,
                           CONFIG_SWS_HEARTBEAT_PERIOD_S);
            break;
        }
        if (n > 0 && !net_publish("event", s_buf, 1, false)) {
            s_seq--;
            return; /* keep it for the next connection */
        }
        s_pend_head = (s_pend_head + 1) % PENDING_MAX;
        s_pend_count--;
    }
}

/* ---------- commands ---------- */

static void ack(const char *id, bool ok, const char *err)
{
    if (id == NULL || id[0] == '\0') {
        return;
    }
    if (msg_ack(s_buf, sizeof(s_buf), id, ok, err) > 0) {
        net_publish("ack", s_buf, 1, false);
    }
}

static const char *prot_err(prot_cmd_result_t r)
{
    switch (r) {
    case PROT_CMD_OK: return NULL;
    case PROT_CMD_BAD_OUTLET: return "bad_outlet";
    case PROT_CMD_LOCKED: return "locked";
    case PROT_CMD_NOT_LOCKED: return "not_locked";
    case PROT_CMD_STILL_HOT: return "still_hot";
    default: return "error";
    }
}

static float *gain_for(cal_channel_t ch)
{
    switch (ch) {
    case CAL_V: return &s_cal.gain_v;
    case CAL_I0: return &s_cal.gain_i[0];
    case CAL_I1: return &s_cal.gain_i[1];
    case CAL_P0: return &s_cal.gain_p[0];
    case CAL_P1: return &s_cal.gain_p[1];
    default: return NULL;
    }
}

/* Mean of the last full telemetry window, for calibration. */
static float measured_for(cal_channel_t ch)
{
    const agg_t *a = &s_prev_agg;
    if (a->n == 0) {
        return NAN;
    }
    switch (ch) {
    case CAL_V: return (float)(a->v / a->n);
    case CAL_I0: return (float)(a->i[0] / a->n);
    case CAL_I1: return (float)(a->i[1] / a->n);
    case CAL_P0: return (float)(a->p[0] / a->n);
    case CAL_P1: return (float)(a->p[1] / a->n);
    default: return NAN;
    }
}

static const char *do_calibrate(cal_channel_t ch, float reference)
{
    float *g = gain_for(ch);
    const float measured = measured_for(ch);
    if (g == NULL || !isfinite(measured)) {
        return "no_measurement_yet";
    }
    if (!cal_adjust(g, measured, reference)) {
        return "correction_out_of_range";
    }
    save_cal();
    ESP_LOGI(TAG, "calibrated channel %d: measured %.3f, reference %.3f, gain %.5f", ch, measured,
             reference, *g);
    return NULL;
}

static void handle_cloud(const char *json, size_t len, uint64_t now)
{
    sws_cmd_t c;
    const char *err = NULL;
    if (!cmd_parse(json, len, &c, &err)) {
        ESP_LOGW(TAG, "rejected command: %s", err);
        ack(c.id, false, err);
        return;
    }
    const dedupe_entry_t *seen = dedupe_find(&s_dedupe, c.id);
    if (seen != NULL) {
        ack(c.id, seen->ok, seen->ok ? NULL : seen->err);
        return;
    }

    switch (c.type) {
    case CMD_RELAY:
        err = prot_err(prot_set_desired(&s_prot, c.outlet, c.on, now));
        break;
    case CMD_RESET:
        err = prot_err(prot_reset(&s_prot, c.outlet, now));
        break;
    case CMD_LIMITS: {
        prot_cfg_t cfg = s_prot.cfg[c.outlet];
        cmd_apply_limits(&c, &cfg);
        err = prot_cfg_validate(&cfg, &s_board->socket_limits);
        if (err == NULL) {
            prot_set_cfg(&s_prot, c.outlet, &cfg);
            char key[8];
            snprintf(key, sizeof(key), "cfg%d", c.outlet);
            storage_set_blob(key, &cfg, sizeof(cfg));
            bump_cfg_ver();
        }
        break;
    }
    case CMD_SCHEDULE:
        if (!sched_set(&s_sched, c.outlet, c.sched, c.sched_n)) {
            err = "invalid_schedule";
        } else {
            char key[8];
            snprintf(key, sizeof(key), "scd%d", c.outlet);
            if (c.sched_n > 0) {
                storage_set_blob(key, c.sched, sizeof(sched_entry_t) * c.sched_n);
            }
            snprintf(key, sizeof(key), "sch%d", c.outlet);
            storage_set_u32(key, c.sched_n);
            bump_cfg_ver();
        }
        break;
    case CMD_CALIBRATE:
        if (storage_get_u32("bench", 0) == 0) {
            err = "bench_mode_off";
        } else {
            err = do_calibrate(c.cal_ch, c.cal_ref);
        }
        break;
    }
    dedupe_put(&s_dedupe, c.id, err == NULL, err);
    ack(c.id, err == NULL, err);
    s_reported_dirty = true;
}

static void handle_msg(const ctl_msg_t *m, uint64_t now)
{
    switch (m->type) {
    case CTL_SET_DESIRED:
        if (prot_set_desired(&s_prot, m->outlet, m->on, now) == PROT_CMD_LOCKED) {
            ESP_LOGW(TAG, "outlet %d is locked (%s); reset it first", m->outlet,
                     prot_reason_name(s_prot.o[m->outlet].reason));
        }
        break;
    case CTL_TOGGLE:
        if (m->outlet >= 0 && m->outlet < SWS_OUTLETS) {
            const bool on = !s_prot.o[m->outlet].desired_on;
            if (prot_set_desired(&s_prot, m->outlet, on, now) == PROT_CMD_LOCKED) {
                ESP_LOGW(TAG, "outlet %d is locked; hold the button 3 s to reset", m->outlet);
            }
        }
        break;
    case CTL_RESET:
        ESP_LOGI(TAG, "reset outlet %d: %s", m->outlet,
                 prot_err(prot_reset(&s_prot, m->outlet, now)) ?: "ok");
        break;
    case CTL_RESET_ALL:
        for (int k = 0; k < SWS_OUTLETS; k++) {
            if (s_prot.o[k].state == PROT_LOCKED) {
                ESP_LOGI(TAG, "reset outlet %d: %s", k, prot_err(prot_reset(&s_prot, k, now)) ?: "ok");
            }
        }
        break;
    case CTL_CLOUD_CMD:
        handle_cloud(m->json, m->json_len, now);
        break;
    case CTL_CAL_LOCAL: {
        const char *err = do_calibrate((cal_channel_t)m->channel, m->value);
        ESP_LOGI(TAG, "calibration: %s", err ? err : "saved");
        break;
    }
    case CTL_SET_HOLD:
        s_hold = (uint16_t)m->value;
        relays_set_hold(s_hold);
        storage_set_u32("hold", s_hold);
        break;
    case CTL_NET_UP:
        s_reported_dirty = true;
        break;
    }
    free(m->json);
}

/* ---------- periodic work ---------- */

static void publish_telemetry(void)
{
    telemetry_t t = {0};
    telemetry_from_agg(&t, &s_agg);
    s_prev_agg = s_agg;
    agg_reset(&s_agg);
    if (!net_connected()) {
        return; /* the cumulative energy counter means nothing is lost */
    }
    t.ts = utc_now();
    t.seq = ++s_seq;
    t.uptime_s = (uint32_t)(app_now_ms() / 1000);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        t.wh[k] = energy_wh(&s_energy, k, s_cal.e_ref[k], s_cal.gain_p[k]);
        t.relay[k] = s_prot.o[k].relay_on;
        t.state[k] = s_prot.o[k].state;
    }
    t.temp_c = s_last_meas.temp_c;
    t.temp_valid = s_last_meas.temp_valid && s_prot.meter_ok;
    t.rssi = net_rssi();
    t.meter_ok = s_prot.meter_ok;
    if (msg_telemetry(s_buf, sizeof(s_buf), &t) > 0) {
        net_publish("telemetry", s_buf, 0, false);
    }
}

static void publish_reported(void)
{
    if (!net_connected()) {
        return;
    }
    const int n = msg_reported(s_buf, sizeof(s_buf), &s_prot, utc_now(), SWS_FW_VERSION,
                               s_board->name, storage_get_u32("cfg_ver", 0), net_time_synced());
    if (n > 0 && net_publish("reported", s_buf, 1, true)) {
        s_reported_dirty = false;
    }
}

static void heartbeat(void)
{
    const int64_t now = utc_now();
    if (now == 0) {
        return;
    }
    heartbeat_t hb = {.alive_utc = now};
    for (int k = 0; k < SWS_OUTLETS; k++) {
        hb.pulses[k] = s_energy.pulses[k];
    }
    storage_save_hb(&hb);
}

/* Once the clock is set after a power-on, report how long the power was off. */
static void check_outage(void)
{
    if (s_outage_checked || !net_time_synced()) {
        return;
    }
    s_outage_checked = true;
    const esp_reset_reason_t rr = esp_reset_reason();
    if ((rr != ESP_RST_POWERON && rr != ESP_RST_BROWNOUT) || s_boot_hb.alive_utc <= 0) {
        return;
    }
    const int64_t boot_utc = utc_now() - (int64_t)(app_now_ms() / 1000);
    if (boot_utc > s_boot_hb.alive_utc) {
        pending_t p = {.kind = PEND_OUTAGE, .start = s_boot_hb.alive_utc, .end = boot_utc,
                       .up_ms = app_now_ms()};
        pend_push(&p);
    }
}

static void run_schedules(uint64_t now)
{
    const int64_t t = utc_now();
    if (t == 0) {
        return;
    }
    bool act[SWS_OUTLETS], on[SWS_OUTLETS];
    sched_run(&s_sched, t, CONFIG_SWS_TZ_OFFSET_MIN, act, on);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        if (act[k]) {
            ESP_LOGI(TAG, "schedule: outlet %d %s", k, on[k] ? "on" : "off");
            prot_set_desired(&s_prot, k, on[k], now);
        }
    }
}

static void drain_prot_events(void)
{
    prot_event_t e;
    while (prot_pop_event(&s_prot, &e)) {
        if (e.type == PEV_STATE) {
            ESP_LOGW(TAG, "outlet %d -> %s (%s, %.1f)", e.outlet, prot_state_name(e.state),
                     prot_reason_name(e.reason), e.value);
            s_reported_dirty = true;
        }
        pending_t p = {.kind = PEND_PROT, .ev = e, .up_ms = e.at_ms};
        pend_push(&p);
    }
}

/* Matter shows the user's intent (desired), so a tap during a restore wait
 * does not bounce back. A refused command is corrected here. */
static void sync_matter(void)
{
    if (!matter_enabled()) {
        return;
    }
    for (int k = 0; k < SWS_OUTLETS; k++) {
        const bool d = s_prot.o[k].desired_on;
        if (!s_matter_reported_valid[k] || s_matter_reported[k] != d) {
            s_matter_reported[k] = d;
            s_matter_reported_valid[k] = true;
            matter_report_onoff(k, d);
        }
    }
}

static void update_led(void)
{
    led_pattern_t p = net_connected() ? LED_ON : LED_BLIP;
    for (int k = 0; k < SWS_OUTLETS; k++) {
        const prot_state_t s = s_prot.o[k].state;
        if (s == PROT_TRIPPED || s == PROT_LOCKED) {
            p = LED_BLINK_FAST;
            break;
        }
        if (s == PROT_WAITING && s_prot.o[k].desired_on) {
            p = LED_BLINK_SLOW;
        }
    }
    status_led_set(p);
}

static void update_snapshot(void)
{
    xSemaphoreTake(s_snap_lock, portMAX_DELAY);
    s_snap.meas = s_last_meas;
    for (int k = 0; k < SWS_OUTLETS; k++) {
        s_snap.state[k] = s_prot.o[k].state;
        s_snap.reason[k] = s_prot.o[k].reason;
        s_snap.desired[k] = s_prot.o[k].desired_on;
        s_snap.relay[k] = s_prot.o[k].relay_on;
        s_snap.wh[k] = energy_wh(&s_energy, k, s_cal.e_ref[k], s_cal.gain_p[k]);
        s_snap.cfg[k] = s_prot.cfg[k];
    }
    s_snap.meter_ok = s_prot.meter_ok;
    s_snap.cal = s_cal;
    s_snap.hold_permille = s_hold;
    s_snap.energy_rejects = s_energy.rejected_steps;
    s_snap.bad_frames = s_bad_frames;
    xSemaphoreGive(s_snap_lock);
}

static void control_task(void *arg)
{
    prot_cfg_t cfg[SWS_OUTLETS];
    bool last_on[SWS_OUTLETS];
    sched_init(&s_sched);
    load_config(cfg, last_on);

    uint64_t now = app_now_ms();
    prot_init(&s_prot, cfg, &s_board->socket_limits, last_on, now);

    if (!storage_load_hb(&s_boot_hb)) {
        memset(&s_boot_hb, 0, sizeof(s_boot_hb));
    }
    energy_init(&s_energy, s_boot_hb.pulses);
    energy_chip_reset(&s_energy);

    relays_init(s_board, s_hold);
    if (metering_init(s_board) != ESP_OK) {
        ESP_LOGE(TAG, "metering UART init failed; protection runs in meter-fault mode");
    }
    agg_reset(&s_agg);
    agg_reset(&s_prev_agg);

    pending_t boot = {.kind = PEND_BOOT, .up_ms = now};
    pend_push(&boot);

    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));

    uint64_t last_meter = 0, last_telemetry = now, last_reported = now, last_hb = 0,
             last_sched = 0;
    TickType_t wake = xTaskGetTickCount();

    for (;;) {
        now = app_now_ms();

        /* 1. Measure and protect. */
        if (now - last_meter >= METER_PERIOD_MS) {
            last_meter = now;
            bl0939_raw_t raw;
            bl0939_status_t st;
            if (metering_read(&raw, &st)) {
                sws_meas_t m;
                bl0939_convert(&raw, &s_cal, &m);
                energy_update(&s_energy, raw.cfa_cnt, raw.cfb_cnt);
                agg_add(&s_agg, &m);
                s_last_meas = m;
                prot_update(&s_prot, &m, now);
            } else {
                if (st != BL0939_OK) {
                    s_bad_frames++;
                }
                prot_update(&s_prot, NULL, now);
            }
        } else {
            prot_update(&s_prot, NULL, now);
        }

        /* 2. Commands from buttons, Matter, cloud and console. */
        ctl_msg_t m;
        while (xQueueReceive(s_q, &m, 0) == pdTRUE) {
            handle_msg(&m, now);
        }

        /* 3. Schedules, once a second. */
        if (now - last_sched >= 1000) {
            last_sched = now;
            run_schedules(now);
        }

        /* 4. Drive the relays. */
        bool want[SWS_OUTLETS];
        for (int k = 0; k < SWS_OUTLETS; k++) {
            want[k] = prot_relay(&s_prot, k);
        }
        relays_apply(want, now);

        /* 5. Report. */
        drain_prot_events();
        save_last_on_if_changed();
        sync_matter();
        check_outage();
        if (now - last_telemetry >= (uint64_t)CONFIG_SWS_TELEMETRY_PERIOD_S * 1000u) {
            last_telemetry = now;
            publish_telemetry();
        }
        if (s_reported_dirty || now - last_reported >= REPORTED_PERIOD_MS) {
            last_reported = now;
            publish_reported();
        }
        pend_flush();
        if (now - last_hb >= (uint64_t)CONFIG_SWS_HEARTBEAT_PERIOD_S * 1000u) {
            last_hb = now;
            heartbeat();
        }

        update_led();
        update_snapshot();
        esp_task_wdt_reset();
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(TICK_MS));
    }
}

esp_err_t control_start(void)
{
    s_board = board_get();
    s_q = xQueueCreate(16, sizeof(ctl_msg_t));
    s_snap_lock = xSemaphoreCreateMutex();
    if (s_q == NULL || s_snap_lock == NULL) {
        return ESP_ERR_NO_MEM;
    }
    /* High priority: protection must not starve behind Wi-Fi or Matter work. */
    return xTaskCreatePinnedToCore(control_task, "control", 6144, NULL, 10, NULL, 1) == pdPASS
               ? ESP_OK
               : ESP_FAIL;
}
