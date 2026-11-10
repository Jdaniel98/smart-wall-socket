#include <math.h>
#include <stdlib.h>

#include "cJSON.h"
#include "sws/proto.h"
#include "sws/relay_drive.h"
#include "sws/schedule.h"
#include "test.h"

/* 2026-11-10 00:00:00 UTC, a Tuesday. */
#define T_2026_11_10 1794268800LL

static void test_weekday(void)
{
    CHECK(sched_weekday(T_2026_11_10 / 86400) == 1); /* Tuesday */
    CHECK(sched_weekday(0) == 3);                    /* 1970-01-01 Thursday */
    CHECK(sched_weekday(-1) == 2);                   /* 1969-12-31 Wednesday */
}

static void test_schedule_fires_once_at_its_minute(void)
{
    sched_t s;
    sched_init(&s);
    const sched_entry_t e[2] = {
        {.days = 0x1F, .minute = 6 * 60 + 30, .on = true},  /* weekdays 06:30 on */
        {.days = SCHED_ALL_DAYS, .minute = 23 * 60, .on = false},
    };
    CHECK(sched_set(&s, 0, e, 2));
    bool act[2], on[2];

    const int64_t t0 = T_2026_11_10 + 6 * 3600 + 29 * 60; /* Tue 06:29 */
    sched_run(&s, t0, 0, act, on);
    CHECK(!act[0]); /* first run only sets the baseline */
    sched_run(&s, t0 + 30, 0, act, on);
    CHECK(!act[0]);
    sched_run(&s, t0 + 61, 0, act, on); /* 06:30:01 */
    CHECK(act[0] && on[0] && !act[1]);
    sched_run(&s, t0 + 90, 0, act, on);
    CHECK(!act[0]); /* does not fire twice */

    /* Saturday 06:30: weekday-only entry stays quiet. */
    sched_t s2;
    sched_init(&s2);
    CHECK(sched_set(&s2, 0, e, 2));
    const int64_t sat = T_2026_11_10 + 4 * 86400 + 6 * 3600 + 29 * 60;
    sched_run(&s2, sat, 0, act, on);
    sched_run(&s2, sat + 120, 0, act, on);
    CHECK(!act[0]);

    /* Timezone offset: 23:00 at UTC+1 is 22:00 UTC. */
    sched_t s3;
    sched_init(&s3);
    CHECK(sched_set(&s3, 0, e, 2));
    const int64_t t22 = T_2026_11_10 + 21 * 3600 + 59 * 60;
    sched_run(&s3, t22, 60, act, on);
    sched_run(&s3, t22 + 60, 60, act, on);
    CHECK(act[0] && !on[0]);
}

static void test_schedule_gaps_and_validation(void)
{
    sched_t s;
    sched_init(&s);
    const sched_entry_t e = {.days = SCHED_ALL_DAYS, .minute = 600, .on = true};
    CHECK(sched_set(&s, 1, &e, 1));
    bool act[2], on[2];
    const int64_t t = T_2026_11_10 + 9 * 3600 + 55 * 60; /* 09:55 */
    sched_run(&s, t, 0, act, on);
    sched_run(&s, t + 8 * 60, 0, act, on); /* 8-minute gap covers 10:00 */
    CHECK(act[1] && on[1]);

    /* A long outage does not replay missed entries. */
    sched_t s2;
    sched_init(&s2);
    CHECK(sched_set(&s2, 1, &e, 1));
    sched_run(&s2, t, 0, act, on);
    sched_run(&s2, t + 3600, 0, act, on);
    CHECK(!act[1]);

    const sched_entry_t bad_min = {.days = 1, .minute = 1440, .on = true};
    const sched_entry_t bad_days = {.days = 0, .minute = 10, .on = true};
    CHECK(!sched_set(&s, 0, &bad_min, 1));
    CHECK(!sched_set(&s, 0, &bad_days, 1));
    CHECK(!sched_set(&s, 2, &e, 1));
}

static void test_relay_pull_in_then_hold(void)
{
    relay_drive_t r;
    relay_drive_init(&r);
    const relay_drive_cfg_t cfg = {.pull_in_ms = 50, .hold_permille = 450, .operate_us = 8000};
    CHECK(relay_drive_duty(&r, &cfg, false, 0) == 0);
    CHECK(relay_drive_duty(&r, &cfg, true, 100) == 1000);
    CHECK(relay_drive_duty(&r, &cfg, true, 149) == 1000);
    CHECK(relay_drive_duty(&r, &cfg, true, 150) == 450);
    CHECK(relay_drive_duty(&r, &cfg, true, 99999) == 450);
    CHECK(relay_drive_duty(&r, &cfg, false, 100000) == 0);
    CHECK(relay_drive_duty(&r, &cfg, true, 100001) == 1000); /* re-energise pulls in again */

    CHECK(relay_zc_delay_us(8000, 10000) == 2000);
    CHECK(relay_zc_delay_us(10000, 10000) == 0);
    CHECK(relay_zc_delay_us(13000, 10000) == 7000);
    CHECK(relay_zc_delay_us(5000, 0) == 0);
}

static bool parse(const char *s, sws_cmd_t *c, const char **err)
{
    return cmd_parse(s, strlen(s), c, err);
}

static void test_cmd_parse_relay_reset_calibrate(void)
{
    sws_cmd_t c;
    const char *err;
    CHECK(parse("{\"id\":\"c-1\",\"cmd\":\"relay\",\"outlet\":1,\"on\":true}", &c, &err));
    CHECK(c.type == CMD_RELAY && c.outlet == 1 && c.on && strcmp(c.id, "c-1") == 0);

    CHECK(parse("{\"id\":\"c-2\",\"cmd\":\"reset\",\"outlet\":0}", &c, &err));
    CHECK(c.type == CMD_RESET && c.outlet == 0);

    CHECK(parse("{\"id\":\"c-3\",\"cmd\":\"calibrate\",\"channel\":\"i1\",\"reference\":8.7}", &c, &err));
    CHECK(c.type == CMD_CALIBRATE && c.cal_ch == CAL_I1);
    CHECK_NEAR(c.cal_ref, 8.7, 1e-5);

    CHECK(!parse("{\"id\":\"c-4\",\"cmd\":\"relay\",\"outlet\":2,\"on\":true}", &c, &err));
    CHECK(strcmp(c.id, "c-4") == 0); /* id kept so the device can still ack */
    CHECK(!parse("{\"id\":\"c-5\",\"cmd\":\"relay\",\"outlet\":0.5,\"on\":true}", &c, &err));
    CHECK(!parse("{\"id\":\"c-6\",\"cmd\":\"relay\",\"outlet\":0,\"on\":1}", &c, &err));
    CHECK(!parse("{\"id\":\"bad\\\"id\",\"cmd\":\"relay\",\"outlet\":0,\"on\":true}", &c, &err));
    CHECK(c.id[0] == '\0');
    CHECK(!parse("{\"cmd\":\"relay\"}", &c, &err));
    CHECK(!parse("{\"id\":\"c-7\",\"cmd\":\"format_flash\"}", &c, &err));
    CHECK(err != NULL && strcmp(err, "unknown cmd") == 0);
    CHECK(!parse("not json", &c, &err));
    CHECK(!parse("{\"id\":\"c-8\",\"cmd\":\"calibrate\",\"channel\":\"x\",\"reference\":1}", &c, &err));
}

static void test_cmd_limits_patch(void)
{
    sws_cmd_t c;
    const char *err;
    CHECK(parse("{\"id\":\"l-1\",\"cmd\":\"limits\",\"outlet\":0,"
                "\"limits\":{\"restore_delay_s\":180,\"v_low\":190,\"restore_policy\":\"on\"}}",
                &c, &err));
    prot_cfg_t cfg;
    prot_cfg_default(&cfg, APPLIANCE_GENERAL, 10.0f);
    cmd_apply_limits(&c, &cfg);
    CHECK(cfg.restore_delay_s == 180);
    CHECK_NEAR(cfg.v_low, 190.0, 1e-4);
    CHECK_NEAR(cfg.v_high, 255.0, 1e-4); /* untouched */
    CHECK(cfg.restore_policy == RESTORE_ON);

    CHECK(!parse("{\"id\":\"l-2\",\"cmd\":\"limits\",\"outlet\":0,\"limits\":{}}", &c, &err));
    CHECK(!parse("{\"id\":\"l-3\",\"cmd\":\"limits\",\"outlet\":0,\"limits\":{\"v_low\":\"x\"}}", &c, &err));
    CHECK(!parse("{\"id\":\"l-4\",\"cmd\":\"limits\",\"outlet\":0,\"limits\":{\"v_low\":-5}}", &c, &err));
    CHECK(!parse("{\"id\":\"l-5\",\"cmd\":\"limits\",\"outlet\":0,"
                 "\"limits\":{\"restore_policy\":\"maybe\"}}", &c, &err));
}

static void test_cmd_schedule(void)
{
    sws_cmd_t c;
    const char *err;
    CHECK(parse("{\"id\":\"s-1\",\"cmd\":\"schedule\",\"outlet\":1,\"entries\":["
                "{\"at\":\"06:30\",\"on\":true,\"days\":\"weekdays\"},"
                "{\"at\":\"23:00\",\"on\":false},"
                "{\"at\":\"10:15\",\"on\":true,\"days\":[\"sat\",\"sun\"]}]}",
                &c, &err));
    CHECK(c.sched_n == 3);
    CHECK(c.sched[0].minute == 390 && c.sched[0].days == 0x1F && c.sched[0].on);
    CHECK(c.sched[1].days == SCHED_ALL_DAYS && !c.sched[1].on);
    CHECK(c.sched[2].days == 0x60 && c.sched[2].minute == 615);

    CHECK(parse("{\"id\":\"s-2\",\"cmd\":\"schedule\",\"outlet\":0,\"entries\":[]}", &c, &err));
    CHECK(c.sched_n == 0); /* clears the schedule */
    CHECK(!parse("{\"id\":\"s-3\",\"cmd\":\"schedule\",\"outlet\":0,\"entries\":[{\"at\":\"24:00\",\"on\":true}]}", &c, &err));
    CHECK(!parse("{\"id\":\"s-4\",\"cmd\":\"schedule\",\"outlet\":0,\"entries\":[{\"at\":\"6:30\",\"on\":true}]}", &c, &err));
    CHECK(!parse("{\"id\":\"s-5\",\"cmd\":\"schedule\",\"outlet\":0,\"entries\":[{\"at\":\"06:30\",\"on\":true,\"days\":[\"funday\"]}]}", &c, &err));
}

static void test_dedupe_and_calibration(void)
{
    dedupe_t d = {0};
    CHECK(dedupe_find(&d, "a") == NULL);
    dedupe_put(&d, "a", true, NULL);
    dedupe_put(&d, "b", false, "locked");
    const dedupe_entry_t *e = dedupe_find(&d, "b");
    CHECK(e != NULL && !e->ok && strcmp(e->err, "locked") == 0);
    char id[8];
    for (int i = 0; i < DEDUPE_SLOTS; i++) {
        snprintf(id, sizeof(id), "x%d", i);
        dedupe_put(&d, id, true, NULL);
    }
    CHECK(dedupe_find(&d, "a") == NULL); /* evicted */
    CHECK(dedupe_find(&d, "x15") != NULL);

    float g = 1.0f;
    CHECK(cal_adjust(&g, 228.0f, 230.0f));
    CHECK_NEAR(g, 230.0 / 228.0, 1e-5);
    CHECK(!cal_adjust(&g, 100.0f, 230.0f)); /* >20% correction refused */
    CHECK(!cal_adjust(&g, 0.0f, 230.0f));
    CHECK(!cal_adjust(&g, NAN, 230.0f));
}

static void test_builders_emit_valid_json(void)
{
    char buf[1024];
    telemetry_t t = {0};
    agg_t a;
    agg_reset(&a);
    sws_meas_t m = {.valid = true, .v_rms = 230.0f, .i_rms = {8.7f, 0.0f}, .p_w = {1980.0f, 0.1f}};
    agg_add(&a, &m);
    m.v_rms = 232.0f;
    agg_add(&a, &m);
    telemetry_from_agg(&t, &a);
    CHECK_NEAR(t.v, 231.0, 1e-4);
    t.ts = T_2026_11_10;
    t.seq = 7;
    t.wh[0] = 12345.67;
    t.relay[0] = true;
    t.state[1] = PROT_WAITING;
    t.temp_valid = false;
    t.rssi = -61;
    t.meter_ok = true;
    int n = msg_telemetry(buf, sizeof(buf), &t);
    CHECK(n > 0);
    cJSON *j = cJSON_Parse(buf);
    CHECK(j != NULL);
    if (j) {
        const cJSON *o = cJSON_GetObjectItem(j, "o");
        CHECK(cJSON_GetArraySize(o) == 2);
        const cJSON *o0 = cJSON_GetArrayItem(o, 0);
        CHECK_NEAR(cJSON_GetObjectItem(o0, "pf")->valuedouble, 1980.0 / (231.0 * 8.7), 0.01);
        CHECK(cJSON_IsNull(cJSON_GetObjectItem(cJSON_GetArrayItem(o, 1), "pf")));
        CHECK(cJSON_IsNull(cJSON_GetObjectItem(j, "temp")));
        CHECK(strcmp(cJSON_GetObjectItem(cJSON_GetArrayItem(o, 1), "state")->valuestring, "waiting") == 0);
        cJSON_Delete(j);
    }
    CHECK(msg_telemetry(buf, 40, &t) == -1); /* too small */

    agg_reset(&a);
    telemetry_from_agg(&t, &a); /* no samples: values become null */
    n = msg_telemetry(buf, sizeof(buf), &t);
    j = cJSON_Parse(buf);
    CHECK(n > 0 && j != NULL && cJSON_IsNull(cJSON_GetObjectItem(j, "v")));
    cJSON_Delete(j);

    const prot_event_t ev = {.type = PEV_STATE, .outlet = 0, .state = PROT_TRIPPED,
                             .reason = REASON_UNDERVOLTAGE, .value = 171.2f};
    n = msg_prot_event(buf, sizeof(buf), &ev, T_2026_11_10, 9);
    j = cJSON_Parse(buf);
    CHECK(n > 0 && j != NULL);
    if (j) {
        CHECK(strcmp(cJSON_GetObjectItem(j, "type")->valuestring, "trip") == 0);
        CHECK(strcmp(cJSON_GetObjectItem(j, "reason")->valuestring, "undervoltage") == 0);
        cJSON_Delete(j);
    }

    prot_t p;
    prot_cfg_t cfg[2];
    prot_cfg_default(&cfg[0], APPLIANCE_GENERAL, 10.0f);
    prot_cfg_default(&cfg[1], APPLIANCE_COMPRESSOR, 10.0f);
    const prot_socket_cfg_t s = {.total_i_limit = 15, .i_max_board = 10, .t_limit_c = 75,
                                 .t_reset_margin_c = 10, .meter_timeout_ms = 5000};
    prot_init(&p, cfg, &s, NULL, 0);
    n = msg_reported(buf, sizeof(buf), &p, T_2026_11_10, "0.1.0", "dualr3v2", 3, true);
    j = cJSON_Parse(buf);
    CHECK(n > 0 && j != NULL);
    if (j) {
        const cJSON *o1 = cJSON_GetArrayItem(cJSON_GetObjectItem(j, "o"), 1);
        CHECK(cJSON_GetObjectItem(cJSON_GetObjectItem(o1, "limits"), "restore_delay_s")->valueint == 180);
        cJSON_Delete(j);
    }

    CHECK(msg_ack(buf, sizeof(buf), "c-1", false, "locked") > 0);
    CHECK(strcmp(buf, "{\"id\":\"c-1\",\"ok\":false,\"error\":\"locked\"}") == 0);
    CHECK(msg_boot(buf, sizeof(buf), 0, 1, "0.1.0", "poweron") > 0);
    CHECK(msg_outage(buf, sizeof(buf), 100, 2, 10, 70, 60) > 0);
    j = cJSON_Parse(buf);
    CHECK(j != NULL && cJSON_GetObjectItem(j, "duration_s")->valueint == 60);
    cJSON_Delete(j);
}

void suite_schedule(void)
{
    RUN(test_weekday);
    RUN(test_schedule_fires_once_at_its_minute);
    RUN(test_schedule_gaps_and_validation);
}

void suite_relay(void)
{
    RUN(test_relay_pull_in_then_hold);
}

void suite_proto(void)
{
    RUN(test_cmd_parse_relay_reset_calibrate);
    RUN(test_cmd_limits_patch);
    RUN(test_cmd_schedule);
    RUN(test_dedupe_and_calibration);
    RUN(test_builders_emit_valid_json);
}
