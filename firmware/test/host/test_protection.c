#include "sws/protection.h"
#include "test.h"

static prot_socket_cfg_t scfg(void)
{
    prot_socket_cfg_t s = {
        .total_i_limit = 15.0f,
        .i_max_board = 10.0f,
        .t_limit_c = 75.0f,
        .t_reset_margin_c = 10.0f,
        .meter_timeout_ms = 5000,
    };
    return s;
}

static sws_meas_t meas(float v, float i0, float i1, float t)
{
    sws_meas_t m = {0};
    m.valid = true;
    m.v_rms = v;
    m.i_rms[0] = i0;
    m.i_rms[1] = i1;
    m.p_w[0] = v * i0;
    m.p_w[1] = v * i1;
    m.temp_c = t;
    m.temp_valid = true;
    return m;
}

/* Feed the same sample every 800 ms (the BL0939 RMS update rate) until t_end. */
static sws_ms_t feed(prot_t *p, sws_ms_t t, sws_ms_t t_end, sws_meas_t m)
{
    for (; t <= t_end; t += 800) {
        prot_update(p, &m, t);
    }
    return t;
}

static void setup(prot_t *p, bool on0, bool on1, sws_ms_t now)
{
    prot_cfg_t cfg[2];
    prot_cfg_default(&cfg[0], APPLIANCE_GENERAL, 10.0f);   /* 30 s restore */
    prot_cfg_default(&cfg[1], APPLIANCE_COMPRESSOR, 10.0f); /* 180 s restore */
    const prot_socket_cfg_t s = scfg();
    const bool last[2] = {on0, on1};
    prot_init(p, cfg, &s, last, now);
}

/* Drains the queue; counts matching events (outlet -2 = any outlet). */
static int count_outlet_events(prot_t *p, prot_event_type_t type, prot_state_t state, int outlet)
{
    int n = 0;
    prot_event_t e;
    while (prot_pop_event(p, &e)) {
        if (e.type == type && (type != PEV_STATE || e.state == state) &&
            (outlet == -2 || e.outlet == outlet)) {
            n++;
        }
    }
    return n;
}

static int count_events(prot_t *p, prot_event_type_t type, prot_state_t state)
{
    return count_outlet_events(p, type, state, -2);
}

static void test_power_up_waits_restore_delay(void)
{
    prot_t p;
    setup(&p, true, true, 0);
    CHECK(p.o[0].state == PROT_WAITING && !prot_relay(&p, 0));
    sws_ms_t t = feed(&p, 0, 29000, meas(230, 0, 0, 30));
    CHECK(!prot_relay(&p, 0)); /* 30 s not yet up */
    t = feed(&p, t, 31000, meas(230, 0, 0, 30));
    CHECK(prot_relay(&p, 0) && p.o[0].state == PROT_NORMAL);
    CHECK(!prot_relay(&p, 1)); /* compressor outlet still waiting (180 s) */
    feed(&p, t, 181000, meas(230, 0, 0, 30));
    CHECK(prot_relay(&p, 1));
}

static void test_restore_policy_off_and_last(void)
{
    prot_t p;
    setup(&p, false, true, 0);
    feed(&p, 0, 200000, meas(230, 0, 0, 30));
    CHECK(!prot_relay(&p, 0)); /* last state was off */
    CHECK(prot_relay(&p, 1));

    prot_cfg_t cfg[2];
    prot_cfg_default(&cfg[0], APPLIANCE_GENERAL, 10.0f);
    prot_cfg_default(&cfg[1], APPLIANCE_GENERAL, 10.0f);
    cfg[0].restore_policy = RESTORE_OFF;
    cfg[1].restore_policy = RESTORE_ON;
    const prot_socket_cfg_t s = scfg();
    const bool last[2] = {true, false};
    prot_init(&p, cfg, &s, last, 0);
    feed(&p, 0, 40000, meas(230, 0, 0, 30));
    CHECK(!prot_relay(&p, 0));
    CHECK(prot_relay(&p, 1));
}

static void test_undervoltage_trip_and_restore(void)
{
    prot_t p;
    setup(&p, true, false, 0);
    sws_ms_t t = feed(&p, 0, 40000, meas(230, 1, 0, 30));
    CHECK(prot_relay(&p, 0));
    (void)count_events(&p, PEV_STATE, PROT_NORMAL);

    /* A 1.6 s sag does not trip (limit is 2 s). */
    t = feed(&p, t, t + 1600, meas(170, 1, 0, 30));
    CHECK(prot_relay(&p, 0));
    t = feed(&p, t, t + 4000, meas(230, 1, 0, 30));

    /* A sustained sag trips. */
    t = feed(&p, t, t + 3000, meas(170, 1, 0, 30));
    CHECK(p.o[0].state == PROT_TRIPPED && p.o[0].reason == REASON_UNDERVOLTAGE);
    CHECK(!prot_relay(&p, 0));
    /* Outlet 0 trips exactly once; outlet 1 was still in its 180 s restore
     * wait, so the earlier short sag already sent it back to TRIPPED. */
    CHECK(count_outlet_events(&p, PEV_STATE, PROT_TRIPPED, 0) == 1);
    CHECK(p.o[1].state == PROT_TRIPPED);

    /* Back to 186 V: inside the limit but not past the 3 V hysteresis. */
    t = feed(&p, t, t + 5000, meas(186, 0, 0, 30));
    CHECK(p.o[0].state == PROT_TRIPPED);

    /* Good voltage starts the restore timer... */
    t = feed(&p, t, t + 10000, meas(229, 0, 0, 30));
    CHECK(p.o[0].state == PROT_WAITING);
    /* ...and a new dip while waiting trips again and resets the timer. */
    t = feed(&p, t, t, meas(180, 0, 0, 30));
    CHECK(p.o[0].state == PROT_TRIPPED);
    t = feed(&p, t, t + 25000, meas(230, 0, 0, 30));
    CHECK(p.o[0].state == PROT_WAITING && !prot_relay(&p, 0));
    feed(&p, t, t + 7000, meas(230, 0, 0, 30));
    CHECK(p.o[0].state == PROT_NORMAL && prot_relay(&p, 0));
}

static void test_surge_trips_on_one_sample(void)
{
    prot_t p;
    setup(&p, true, false, 0);
    sws_ms_t t = feed(&p, 0, 40000, meas(230, 0, 0, 30));
    CHECK(prot_relay(&p, 0));
    prot_update(&p, &(sws_meas_t){0}, t); /* invalid sample is ignored */
    sws_meas_t m = meas(280, 0, 0, 30);
    prot_update(&p, &m, t + 800);
    CHECK(p.o[0].state == PROT_TRIPPED && p.o[0].reason == REASON_SURGE);
    CHECK(!prot_relay(&p, 0));
}

static void test_overcurrent_locks_until_reset(void)
{
    prot_t p;
    setup(&p, true, true, 0);
    sws_ms_t t = feed(&p, 0, 200000, meas(230, 2, 2, 30));
    CHECK(prot_relay(&p, 0) && prot_relay(&p, 1));

    /* 11 A on a 10 A limit: allowed for 5 s, then locked. */
    t = feed(&p, t, t + 4000, meas(230, 11, 2, 30));
    CHECK(prot_relay(&p, 0));
    t = feed(&p, t, t + 2000, meas(230, 11, 2, 30));
    CHECK(p.o[0].state == PROT_LOCKED && p.o[0].reason == REASON_OVERCURRENT);
    CHECK(!prot_relay(&p, 0) && prot_relay(&p, 1));

    /* Locked outlets ignore voltage and refuse to turn on. */
    t = feed(&p, t, t + 50000, meas(230, 0, 2, 30));
    CHECK(p.o[0].state == PROT_LOCKED);
    CHECK(prot_set_desired(&p, 0, true, t) == PROT_CMD_LOCKED);
    CHECK(prot_reset(&p, 1, t) == PROT_CMD_NOT_LOCKED);

    /* Reset brings it back off; the user turns it on. */
    CHECK(prot_reset(&p, 0, t) == PROT_CMD_OK);
    CHECK(p.o[0].state == PROT_NORMAL && !prot_relay(&p, 0));
    CHECK(prot_set_desired(&p, 0, true, t) == PROT_CMD_OK);
    CHECK(prot_relay(&p, 0));

    /* 16 A (1.6x limit) locks on a single sample. */
    sws_meas_t m = meas(230, 16, 2, 30);
    prot_update(&p, &m, t + 800);
    CHECK(p.o[0].state == PROT_LOCKED);
}

static void test_total_overcurrent_sheds_bigger_load(void)
{
    prot_t p;
    setup(&p, true, true, 0);
    sws_ms_t t = feed(&p, 0, 200000, meas(230, 2, 2, 30));
    t = feed(&p, t, t + 6000, meas(230, 9, 7, 30)); /* 16 A total > 15 A */
    CHECK(p.o[0].state == PROT_LOCKED && p.o[0].reason == REASON_TOTAL_OVERCURRENT);
    CHECK(p.o[1].state == PROT_NORMAL && prot_relay(&p, 1));
}

static void test_overtemp_locks_both_and_needs_cooling(void)
{
    prot_t p;
    setup(&p, true, true, 0);
    sws_ms_t t = feed(&p, 0, 200000, meas(230, 2, 2, 40));
    t = feed(&p, t, t, meas(230, 2, 2, 80));
    CHECK(p.o[0].state == PROT_LOCKED && p.o[1].state == PROT_LOCKED);
    CHECK(p.o[0].reason == REASON_OVERTEMP);
    CHECK(!prot_relay(&p, 0) && !prot_relay(&p, 1));

    t = feed(&p, t, t + 1000, meas(230, 0, 0, 70)); /* still within 10 degC of limit */
    CHECK(prot_reset(&p, 0, t) == PROT_CMD_STILL_HOT);
    t = feed(&p, t, t + 1000, meas(230, 0, 0, 60));
    CHECK(prot_reset(&p, 0, t) == PROT_CMD_OK);
}

static void test_meter_fault_behaviour(void)
{
    /* Boot with a dead metering chip: fault reported, outlets restore on the timer. */
    prot_t p;
    setup(&p, true, false, 0);
    sws_ms_t t;
    for (t = 0; t <= 4000; t += 100) {
        prot_update(&p, NULL, t);
    }
    CHECK(!p.meter_fault);
    for (; t <= 6000; t += 100) {
        prot_update(&p, NULL, t);
    }
    CHECK(p.meter_fault);
    CHECK(count_events(&p, PEV_METER_FAULT, PROT_NORMAL) == 1);
    for (; t <= 40000; t += 100) {
        prot_update(&p, NULL, t);
    }
    CHECK(prot_relay(&p, 0));
    CHECK(count_events(&p, PEV_METER_FAULT, PROT_NORMAL) == 0); /* reported once */

    /* Recovery is reported. */
    sws_meas_t m = meas(230, 1, 0, 30);
    prot_update(&p, &m, t);
    CHECK(!p.meter_fault);
    CHECK(count_events(&p, PEV_METER_OK, PROT_NORMAL) == 1);

    /* A tripped outlet stays off if the meter dies. */
    t = feed(&p, t, t + 3000, meas(170, 0, 0, 30));
    CHECK(p.o[0].state == PROT_TRIPPED);
    for (sws_ms_t end = t + 120000; t <= end; t += 100) {
        prot_update(&p, NULL, t);
    }
    CHECK(p.meter_fault && p.o[0].state == PROT_TRIPPED && !prot_relay(&p, 0));
}

static void test_event_queue_drops_oldest(void)
{
    prot_t p;
    setup(&p, false, false, 0);
    (void)count_events(&p, PEV_STATE, PROT_NORMAL);
    for (int i = 0; i < PROT_EVENT_QUEUE + 4; i++) {
        prot_set_desired(&p, 0, true, 0);
        prot_set_desired(&p, 0, false, 0);
    }
    /* Outlet is WAITING so no relay events: queue stays empty. */
    CHECK(p.ev_count == 0);
    feed(&p, 0, 40000, meas(230, 0, 0, 30));
    (void)count_events(&p, PEV_STATE, PROT_NORMAL);
    for (int i = 0; i < PROT_EVENT_QUEUE + 4; i++) {
        prot_set_desired(&p, 0, (i % 2) == 0, 50000);
    }
    CHECK(p.ev_count == PROT_EVENT_QUEUE);
    CHECK(p.ev_dropped == 4);
}

static void test_cfg_validation(void)
{
    const prot_socket_cfg_t s = scfg();
    prot_cfg_t c;
    prot_cfg_default(&c, APPLIANCE_GENERAL, 10.0f);
    CHECK(prot_cfg_validate(&c, &s) == NULL);
    c.v_low = 140;
    CHECK(prot_cfg_validate(&c, &s) != NULL);
    prot_cfg_default(&c, APPLIANCE_GENERAL, 10.0f);
    c.i_limit = 12.0f; /* above the Sonoff's 10 A */
    CHECK(prot_cfg_validate(&c, &s) != NULL);
    prot_cfg_default(&c, APPLIANCE_GENERAL, 10.0f);
    c.v_low = 215;
    c.v_high = 240;
    CHECK(prot_cfg_validate(&c, &s) != NULL); /* band too narrow */
    prot_cfg_default(&c, APPLIANCE_GENERAL, 10.0f);
    c.restore_delay_s = 1;
    CHECK(prot_cfg_validate(&c, &s) != NULL);
}

void suite_protection(void)
{
    RUN(test_power_up_waits_restore_delay);
    RUN(test_restore_policy_off_and_last);
    RUN(test_undervoltage_trip_and_restore);
    RUN(test_surge_trips_on_one_sample);
    RUN(test_overcurrent_locks_until_reset);
    RUN(test_total_overcurrent_sheds_bigger_load);
    RUN(test_overtemp_locks_both_and_needs_cooling);
    RUN(test_meter_fault_behaviour);
    RUN(test_event_queue_drops_oldest);
    RUN(test_cfg_validation);
}
