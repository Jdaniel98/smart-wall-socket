#include "sws/protection.h"

#include <string.h>

/* Timers use 0 as "not running", so a timestamp is never stored as 0. */
static sws_ms_t stamp(sws_ms_t now)
{
    return now == 0 ? 1 : now;
}

static bool elapsed(sws_ms_t since, sws_ms_t now, uint64_t ms)
{
    return since != 0 && now >= since && (now - since) >= ms;
}

void prot_cfg_default(prot_cfg_t *cfg, appliance_t appliance, float i_limit)
{
    memset(cfg, 0, sizeof(*cfg));
    cfg->v_low = 185.0f;
    cfg->v_high = 255.0f;
    cfg->v_instant_high = 275.0f;
    cfg->v_hyst = 3.0f;
    cfg->trip_ms = 2000;
    cfg->restore_delay_s = (appliance == APPLIANCE_COMPRESSOR) ? 180 : 30;
    cfg->i_limit = i_limit;
    cfg->i_trip_ms = 5000;
    cfg->i_instant_factor = 1.5f;
    cfg->restore_policy = RESTORE_LAST;
}

const char *prot_cfg_validate(const prot_cfg_t *c, const prot_socket_cfg_t *s)
{
    if (c->v_low < 150.0f || c->v_low > 215.0f) {
        return "v_low must be 150-215 V";
    }
    if (c->v_high < 240.0f || c->v_high > 270.0f) {
        return "v_high must be 240-270 V";
    }
    if (c->v_high - c->v_low < 30.0f) {
        return "v_high must be at least 30 V above v_low";
    }
    if (c->v_instant_high < c->v_high + 5.0f || c->v_instant_high > 290.0f) {
        return "v_instant_high must be v_high+5 to 290 V";
    }
    if (c->v_hyst < 1.0f || c->v_hyst > 10.0f) {
        return "v_hyst must be 1-10 V";
    }
    if (c->trip_ms < 500 || c->trip_ms > 10000) {
        return "trip_ms must be 500-10000";
    }
    if (c->restore_delay_s < 5 || c->restore_delay_s > 900) {
        return "restore_delay_s must be 5-900";
    }
    if (c->i_limit < 0.5f || c->i_limit > s->i_max_board) {
        return "i_limit out of range for this board";
    }
    if (c->i_trip_ms < 1000 || c->i_trip_ms > 60000) {
        return "i_trip_ms must be 1000-60000";
    }
    if (c->i_instant_factor < 1.1f || c->i_instant_factor > 2.0f) {
        return "i_instant_factor must be 1.1-2.0";
    }
    if (c->restore_policy > RESTORE_OFF) {
        return "unknown restore_policy";
    }
    return NULL;
}

static void push_event(prot_t *p, prot_event_type_t type, int outlet, prot_state_t state,
                       prot_reason_t reason, float value, sws_ms_t now)
{
    if (p->ev_count == PROT_EVENT_QUEUE) {
        /* Drop the oldest: the newest state is what matters. */
        p->ev_head = (uint8_t)((p->ev_head + 1) % PROT_EVENT_QUEUE);
        p->ev_count--;
        p->ev_dropped++;
    }
    const uint8_t idx = (uint8_t)((p->ev_head + p->ev_count) % PROT_EVENT_QUEUE);
    p->ev[idx] = (prot_event_t){
        .type = type,
        .outlet = (int8_t)outlet,
        .state = state,
        .reason = reason,
        .value = value,
        .at_ms = now,
    };
    p->ev_count++;
}

bool prot_pop_event(prot_t *p, prot_event_t *out)
{
    if (p->ev_count == 0) {
        return false;
    }
    *out = p->ev[p->ev_head];
    p->ev_head = (uint8_t)((p->ev_head + 1) % PROT_EVENT_QUEUE);
    p->ev_count--;
    return true;
}

static void set_state(prot_t *p, int k, prot_state_t s, prot_reason_t r, float value, sws_ms_t now)
{
    prot_outlet_t *o = &p->o[k];
    if (o->state == s && o->reason == r) {
        return;
    }
    o->state = s;
    o->reason = r;
    o->bad_since = 0;
    o->oc_since = 0;
    o->good_since = (s == PROT_WAITING) ? stamp(now) : 0;
    push_event(p, PEV_STATE, k, s, r, value, now);
}

static void refresh_relays(prot_t *p, sws_ms_t now)
{
    for (int k = 0; k < SWS_OUTLETS; k++) {
        prot_outlet_t *o = &p->o[k];
        const bool want = o->desired_on && o->state == PROT_NORMAL;
        if (want != o->relay_on) {
            o->relay_on = want;
            push_event(p, PEV_RELAY, k, o->state, REASON_NONE, want ? 1.0f : 0.0f, now);
        }
    }
}

void prot_init(prot_t *p, const prot_cfg_t cfg[SWS_OUTLETS], const prot_socket_cfg_t *scfg,
               const bool last_on[SWS_OUTLETS], sws_ms_t now)
{
    memset(p, 0, sizeof(*p));
    p->scfg = *scfg;
    p->boot_ms = stamp(now);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        p->cfg[k] = cfg[k];
        prot_outlet_t *o = &p->o[k];
        switch (cfg[k].restore_policy) {
        case RESTORE_ON:
            o->desired_on = true;
            break;
        case RESTORE_OFF:
            o->desired_on = false;
            break;
        case RESTORE_LAST:
        default:
            o->desired_on = last_on ? last_on[k] : false;
            break;
        }
        /* Power-up counts as a restoration: wait for good voltage first.
         * good_since stays 0 until the first good sample (or a meter fault). */
        o->state = PROT_WAITING;
        o->reason = REASON_NONE;
        o->relay_on = false;
    }
}

static bool v_bad(const prot_cfg_t *c, float v, prot_reason_t *why)
{
    if (v < c->v_low) {
        *why = REASON_UNDERVOLTAGE;
        return true;
    }
    if (v > c->v_high) {
        *why = REASON_OVERVOLTAGE;
        return true;
    }
    *why = REASON_NONE;
    return false;
}

static void eval_voltage(prot_t *p, int k, float v, sws_ms_t now)
{
    const prot_cfg_t *c = &p->cfg[k];
    prot_outlet_t *o = &p->o[k];
    prot_reason_t why;
    const bool bad = v_bad(c, v, &why);

    switch (o->state) {
    case PROT_NORMAL:
        if (v > c->v_instant_high) {
            set_state(p, k, PROT_TRIPPED, REASON_SURGE, v, now);
        } else if (bad) {
            if (o->bad_since == 0) {
                o->bad_since = stamp(now);
            }
            if (elapsed(o->bad_since, now, c->trip_ms)) {
                set_state(p, k, PROT_TRIPPED, why, v, now);
            }
        } else {
            o->bad_since = 0;
        }
        break;
    case PROT_TRIPPED:
        if (v >= c->v_low + c->v_hyst && v <= c->v_high - c->v_hyst) {
            set_state(p, k, PROT_WAITING, REASON_NONE, v, now);
        }
        break;
    case PROT_WAITING:
        if (bad || v > c->v_instant_high) {
            set_state(p, k, PROT_TRIPPED, bad ? why : REASON_SURGE, v, now);
        } else {
            if (o->good_since == 0) {
                o->good_since = stamp(now);
            }
            if (elapsed(o->good_since, now, (uint64_t)c->restore_delay_s * 1000u)) {
                set_state(p, k, PROT_NORMAL, REASON_NONE, v, now);
            }
        }
        break;
    case PROT_LOCKED:
    default:
        break;
    }
}

static void lock(prot_t *p, int k, prot_reason_t r, float value, sws_ms_t now)
{
    if (p->o[k].state != PROT_LOCKED) {
        set_state(p, k, PROT_LOCKED, r, value, now);
    }
}

static void eval_current(prot_t *p, const sws_meas_t *m, sws_ms_t now)
{
    for (int k = 0; k < SWS_OUTLETS; k++) {
        const prot_cfg_t *c = &p->cfg[k];
        prot_outlet_t *o = &p->o[k];
        if (o->state == PROT_LOCKED) {
            continue;
        }
        const float i = m->i_rms[k];
        if (i > c->i_limit * c->i_instant_factor) {
            lock(p, k, REASON_OVERCURRENT, i, now);
        } else if (i > c->i_limit) {
            if (o->oc_since == 0) {
                o->oc_since = stamp(now);
            }
            if (elapsed(o->oc_since, now, c->i_trip_ms)) {
                lock(p, k, REASON_OVERCURRENT, i, now);
            }
        } else {
            o->oc_since = 0;
        }
    }

    const float total = m->i_rms[0] + m->i_rms[1];
    if (total > p->scfg.total_i_limit) {
        if (p->total_oc_since == 0) {
            p->total_oc_since = stamp(now);
        }
        /* Use the shorter of the two outlets' sustained trip times. */
        uint32_t t = p->cfg[0].i_trip_ms < p->cfg[1].i_trip_ms ? p->cfg[0].i_trip_ms
                                                                : p->cfg[1].i_trip_ms;
        if (elapsed(p->total_oc_since, now, t)) {
            /* Shed the bigger load; the other outlet keeps running. */
            const int k = (m->i_rms[0] >= m->i_rms[1]) ? 0 : 1;
            lock(p, k, REASON_TOTAL_OVERCURRENT, total, now);
            p->total_oc_since = 0;
        }
    } else {
        p->total_oc_since = 0;
    }
}

static void eval_temp(prot_t *p, float t, sws_ms_t now)
{
    p->last_temp_c = t;
    p->last_temp_valid = true;
    if (t > p->scfg.t_limit_c) {
        for (int k = 0; k < SWS_OUTLETS; k++) {
                /* Over-temperature overrides any other lock reason. */
            set_state(p, k, PROT_LOCKED, REASON_OVERTEMP, t, now);
        }
    }
}

void prot_update(prot_t *p, const sws_meas_t *m, sws_ms_t now)
{
    if (m != NULL && m->valid) {
        p->last_meas_ms = stamp(now);
        p->meter_ok = true;
        if (p->meter_fault) {
            p->meter_fault = false;
            push_event(p, PEV_METER_OK, -1, PROT_NORMAL, REASON_NONE, 0.0f, now);
        }
        if (m->temp_valid) {
            eval_temp(p, m->temp_c, now);
        }
        eval_current(p, m, now);
        for (int k = 0; k < SWS_OUTLETS; k++) {
            eval_voltage(p, k, m->v_rms, now);
        }
    } else {
        const sws_ms_t ref = p->last_meas_ms ? p->last_meas_ms : p->boot_ms;
        if (!p->meter_fault && elapsed(ref, now, p->scfg.meter_timeout_ms)) {
            p->meter_fault = true;
            p->meter_ok = false;
            p->last_temp_valid = false; /* temperature came from the same frames */
            push_event(p, PEV_METER_FAULT, -1, PROT_NORMAL, REASON_NONE, 0.0f, now);
        }
        if (p->meter_fault) {
            /* Blind mode: WAITING outlets restore on the timer alone; NORMAL
             * outlets stay on; TRIPPED outlets stay off (last seen bad). */
            for (int k = 0; k < SWS_OUTLETS; k++) {
                prot_outlet_t *o = &p->o[k];
                if (o->state != PROT_WAITING) {
                    continue;
                }
                if (o->good_since == 0) {
                    o->good_since = stamp(now);
                }
                if (elapsed(o->good_since, now, (uint64_t)p->cfg[k].restore_delay_s * 1000u)) {
                    set_state(p, k, PROT_NORMAL, REASON_NONE, 0.0f, now);
                }
            }
        }
    }
    refresh_relays(p, now);
}

prot_cmd_result_t prot_set_desired(prot_t *p, int outlet, bool on, sws_ms_t now)
{
    if (outlet < 0 || outlet >= SWS_OUTLETS) {
        return PROT_CMD_BAD_OUTLET;
    }
    prot_outlet_t *o = &p->o[outlet];
    if (on && o->state == PROT_LOCKED) {
        return PROT_CMD_LOCKED;
    }
    o->desired_on = on;
    refresh_relays(p, now);
    return PROT_CMD_OK;
}

prot_cmd_result_t prot_reset(prot_t *p, int outlet, sws_ms_t now)
{
    if (outlet < 0 || outlet >= SWS_OUTLETS) {
        return PROT_CMD_BAD_OUTLET;
    }
    prot_outlet_t *o = &p->o[outlet];
    if (o->state != PROT_LOCKED) {
        return PROT_CMD_NOT_LOCKED;
    }
    /* Refuse an over-temperature reset until the board is known to be cool. */
    if (o->reason == REASON_OVERTEMP &&
        (!p->last_temp_valid || p->last_temp_c > p->scfg.t_limit_c - p->scfg.t_reset_margin_c)) {
        return PROT_CMD_STILL_HOT;
    }
    o->desired_on = false;
    set_state(p, outlet, PROT_NORMAL, REASON_NONE, 0.0f, now);
    refresh_relays(p, now);
    return PROT_CMD_OK;
}

prot_cmd_result_t prot_set_cfg(prot_t *p, int outlet, const prot_cfg_t *cfg)
{
    if (outlet < 0 || outlet >= SWS_OUTLETS) {
        return PROT_CMD_BAD_OUTLET;
    }
    p->cfg[outlet] = *cfg;
    return PROT_CMD_OK;
}

bool prot_relay(const prot_t *p, int outlet)
{
    if (outlet < 0 || outlet >= SWS_OUTLETS) {
        return false;
    }
    return p->o[outlet].relay_on;
}

const char *prot_state_name(prot_state_t s)
{
    switch (s) {
    case PROT_NORMAL: return "normal";
    case PROT_TRIPPED: return "tripped";
    case PROT_WAITING: return "waiting";
    case PROT_LOCKED: return "locked";
    default: return "unknown";
    }
}

const char *prot_reason_name(prot_reason_t r)
{
    switch (r) {
    case REASON_NONE: return "none";
    case REASON_UNDERVOLTAGE: return "undervoltage";
    case REASON_OVERVOLTAGE: return "overvoltage";
    case REASON_SURGE: return "surge";
    case REASON_OVERCURRENT: return "overcurrent";
    case REASON_TOTAL_OVERCURRENT: return "total_overcurrent";
    case REASON_OVERTEMP: return "overtemp";
    default: return "unknown";
    }
}
