#include "sws/proto.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "cJSON.h"

/* ---------- small JSON writer ---------- */

typedef struct {
    char *b;
    size_t n;
    size_t len;
    bool overflow;
} jbuf_t;

static void jb(jbuf_t *j, const char *fmt, ...)
{
    if (j->overflow) {
        return;
    }
    va_list ap;
    va_start(ap, fmt);
    const int w = vsnprintf(j->b + j->len, j->n - j->len, fmt, ap);
    va_end(ap);
    if (w < 0 || (size_t)w >= j->n - j->len) {
        j->overflow = true;
        return;
    }
    j->len += (size_t)w;
}

/* Number or null (JSON has no NaN/Inf). */
static void jb_num(jbuf_t *j, const char *key, double v, int prec)
{
    if (!isfinite(v)) {
        jb(j, "\"%s\":null", key);
    } else {
        jb(j, "\"%s\":%.*f", key, prec, v);
    }
}

static int jb_done(jbuf_t *j)
{
    return j->overflow ? -1 : (int)j->len;
}

static jbuf_t jb_init(char *buf, size_t n)
{
    jbuf_t j = {.b = buf, .n = n, .len = 0, .overflow = (n == 0)};
    if (n > 0) {
        buf[0] = '\0';
    }
    return j;
}

static const char *policy_name(restore_policy_t p)
{
    switch (p) {
    case RESTORE_ON: return "on";
    case RESTORE_OFF: return "off";
    case RESTORE_LAST:
    default: return "last";
    }
}

/* ---------- command parsing ---------- */

/* Ids go back out in acks, so only allow a safe character set. */
static bool id_ok(const char *s)
{
    const size_t len = strlen(s);
    if (len == 0 || len >= CMD_ID_MAX) {
        return false;
    }
    for (size_t i = 0; i < len; i++) {
        const char c = s[i];
        const bool okc = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                         (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == ':';
        if (!okc) {
            return false;
        }
    }
    return true;
}

static bool get_outlet(const cJSON *root, int *outlet)
{
    const cJSON *o = cJSON_GetObjectItemCaseSensitive(root, "outlet");
    if (!cJSON_IsNumber(o)) {
        return false;
    }
    const double v = o->valuedouble;
    if (v != (int)v || v < 0 || v >= SWS_OUTLETS) {
        return false;
    }
    *outlet = (int)v;
    return true;
}

static int day_bit_from_name(const char *s)
{
    static const char *names[7] = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"};
    for (int i = 0; i < 7; i++) {
        if (strcmp(s, names[i]) == 0) {
            return 1 << i;
        }
    }
    return 0;
}

static bool parse_days(const cJSON *d, uint8_t *out)
{
    if (cJSON_IsString(d)) {
        if (strcmp(d->valuestring, "daily") == 0) {
            *out = SCHED_ALL_DAYS;
        } else if (strcmp(d->valuestring, "weekdays") == 0) {
            *out = 0x1F;
        } else if (strcmp(d->valuestring, "weekends") == 0) {
            *out = 0x60;
        } else {
            return false;
        }
        return true;
    }
    if (!cJSON_IsArray(d)) {
        return false;
    }
    uint8_t mask = 0;
    const cJSON *it;
    cJSON_ArrayForEach(it, d)
    {
        if (!cJSON_IsString(it)) {
            return false;
        }
        const int b = day_bit_from_name(it->valuestring);
        if (b == 0) {
            return false;
        }
        mask |= (uint8_t)b;
    }
    if (mask == 0) {
        return false;
    }
    *out = mask;
    return true;
}

static bool parse_hhmm(const char *s, uint16_t *minute)
{
    if (strlen(s) != 5 || s[2] != ':') {
        return false;
    }
    for (int i = 0; i < 5; i++) {
        if (i != 2 && (s[i] < '0' || s[i] > '9')) {
            return false;
        }
    }
    const int h = (s[0] - '0') * 10 + (s[1] - '0');
    const int m = (s[3] - '0') * 10 + (s[4] - '0');
    if (h > 23 || m > 59) {
        return false;
    }
    *minute = (uint16_t)(h * 60 + m);
    return true;
}

static bool num_field(const cJSON *obj, const char *key, double *out)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (v == NULL) {
        return false;
    }
    if (!cJSON_IsNumber(v) || !isfinite(v->valuedouble)) {
        return false;
    }
    *out = v->valuedouble;
    return true;
}

static bool parse_limits(const cJSON *lim, sws_cmd_t *c, const char **err)
{
    if (!cJSON_IsObject(lim)) {
        *err = "limits must be an object";
        return false;
    }
    double v;
    const struct {
        const char *key;
        uint32_t bit;
    } nums[] = {
        {"v_low", LIM_V_LOW},
        {"v_high", LIM_V_HIGH},
        {"v_instant_high", LIM_V_INSTANT_HIGH},
        {"trip_ms", LIM_TRIP_MS},
        {"restore_delay_s", LIM_RESTORE_DELAY},
        {"i_limit", LIM_I_LIMIT},
    };
    for (size_t i = 0; i < sizeof(nums) / sizeof(nums[0]); i++) {
        const cJSON *item = cJSON_GetObjectItemCaseSensitive(lim, nums[i].key);
        if (item == NULL) {
            continue;
        }
        if (!num_field(lim, nums[i].key, &v) || v < 0 || v > 1e6) {
            *err = "limit values must be non-negative numbers";
            return false;
        }
        c->lim_mask |= nums[i].bit;
        switch (nums[i].bit) {
        case LIM_V_LOW: c->lim.v_low = (float)v; break;
        case LIM_V_HIGH: c->lim.v_high = (float)v; break;
        case LIM_V_INSTANT_HIGH: c->lim.v_instant_high = (float)v; break;
        case LIM_TRIP_MS: c->lim.trip_ms = (uint32_t)v; break;
        case LIM_RESTORE_DELAY: c->lim.restore_delay_s = (uint32_t)v; break;
        case LIM_I_LIMIT: c->lim.i_limit = (float)v; break;
        default: break;
        }
    }
    const cJSON *pol = cJSON_GetObjectItemCaseSensitive(lim, "restore_policy");
    if (pol != NULL) {
        if (!cJSON_IsString(pol)) {
            *err = "restore_policy must be last, on or off";
            return false;
        }
        if (strcmp(pol->valuestring, "last") == 0) {
            c->lim.restore_policy = RESTORE_LAST;
        } else if (strcmp(pol->valuestring, "on") == 0) {
            c->lim.restore_policy = RESTORE_ON;
        } else if (strcmp(pol->valuestring, "off") == 0) {
            c->lim.restore_policy = RESTORE_OFF;
        } else {
            *err = "restore_policy must be last, on or off";
            return false;
        }
        c->lim_mask |= LIM_RESTORE_POLICY;
    }
    if (c->lim_mask == 0) {
        *err = "no limits given";
        return false;
    }
    return true;
}

static bool parse_schedule(const cJSON *entries, sws_cmd_t *c, const char **err)
{
    if (!cJSON_IsArray(entries)) {
        *err = "entries must be an array";
        return false;
    }
    if (cJSON_GetArraySize(entries) > SCHED_MAX) {
        *err = "too many schedule entries (max 8)";
        return false;
    }
    const cJSON *it;
    uint8_t n = 0;
    cJSON_ArrayForEach(it, entries)
    {
        sched_entry_t *e = &c->sched[n];
        const cJSON *at = cJSON_GetObjectItemCaseSensitive(it, "at");
        const cJSON *on = cJSON_GetObjectItemCaseSensitive(it, "on");
        const cJSON *days = cJSON_GetObjectItemCaseSensitive(it, "days");
        if (!cJSON_IsString(at) || !parse_hhmm(at->valuestring, &e->minute)) {
            *err = "entry.at must be HH:MM";
            return false;
        }
        if (!cJSON_IsBool(on)) {
            *err = "entry.on must be true or false";
            return false;
        }
        e->on = cJSON_IsTrue(on);
        if (days == NULL) {
            e->days = SCHED_ALL_DAYS;
        } else if (!parse_days(days, &e->days)) {
            *err = "entry.days must be daily, weekdays, weekends or a list of mon..sun";
            return false;
        }
        n++;
    }
    c->sched_n = n;
    return true;
}

bool cmd_parse(const char *json, size_t len, sws_cmd_t *out, const char **err)
{
    memset(out, 0, sizeof(*out));
    *err = NULL;
    cJSON *root = cJSON_ParseWithLength(json, len);
    if (root == NULL || !cJSON_IsObject(root)) {
        cJSON_Delete(root);
        *err = "invalid JSON";
        return false;
    }

    bool ok = false;
    const cJSON *id = cJSON_GetObjectItemCaseSensitive(root, "id");
    const cJSON *cmd = cJSON_GetObjectItemCaseSensitive(root, "cmd");
    if (!cJSON_IsString(id) || !id_ok(id->valuestring)) {
        *err = "missing or invalid id";
        goto done;
    }
    strncpy(out->id, id->valuestring, CMD_ID_MAX - 1);
    if (!cJSON_IsString(cmd)) {
        *err = "missing cmd";
        goto done;
    }

    const char *name = cmd->valuestring;
    if (strcmp(name, "relay") == 0) {
        out->type = CMD_RELAY;
        const cJSON *on = cJSON_GetObjectItemCaseSensitive(root, "on");
        if (!get_outlet(root, &out->outlet)) {
            *err = "outlet must be 0 or 1";
            goto done;
        }
        if (!cJSON_IsBool(on)) {
            *err = "on must be true or false";
            goto done;
        }
        out->on = cJSON_IsTrue(on);
    } else if (strcmp(name, "reset") == 0) {
        out->type = CMD_RESET;
        if (!get_outlet(root, &out->outlet)) {
            *err = "outlet must be 0 or 1";
            goto done;
        }
    } else if (strcmp(name, "limits") == 0) {
        out->type = CMD_LIMITS;
        if (!get_outlet(root, &out->outlet)) {
            *err = "outlet must be 0 or 1";
            goto done;
        }
        if (!parse_limits(cJSON_GetObjectItemCaseSensitive(root, "limits"), out, err)) {
            goto done;
        }
    } else if (strcmp(name, "schedule") == 0) {
        out->type = CMD_SCHEDULE;
        if (!get_outlet(root, &out->outlet)) {
            *err = "outlet must be 0 or 1";
            goto done;
        }
        if (!parse_schedule(cJSON_GetObjectItemCaseSensitive(root, "entries"), out, err)) {
            goto done;
        }
    } else if (strcmp(name, "calibrate") == 0) {
        out->type = CMD_CALIBRATE;
        const cJSON *ch = cJSON_GetObjectItemCaseSensitive(root, "channel");
        double ref;
        static const char *chans[] = {"v", "i0", "i1", "p0", "p1"};
        bool found = false;
        if (cJSON_IsString(ch)) {
            for (int i = 0; i < 5; i++) {
                if (strcmp(ch->valuestring, chans[i]) == 0) {
                    out->cal_ch = (cal_channel_t)i;
                    found = true;
                }
            }
        }
        if (!found) {
            *err = "channel must be v, i0, i1, p0 or p1";
            goto done;
        }
        if (!num_field(root, "reference", &ref) || ref <= 0) {
            *err = "reference must be a positive number";
            goto done;
        }
        out->cal_ref = (float)ref;
    } else {
        *err = "unknown cmd";
        goto done;
    }
    ok = true;

done:
    cJSON_Delete(root);
    return ok;
}

void cmd_apply_limits(const sws_cmd_t *c, prot_cfg_t *cfg)
{
    if (c->lim_mask & LIM_V_LOW) cfg->v_low = c->lim.v_low;
    if (c->lim_mask & LIM_V_HIGH) cfg->v_high = c->lim.v_high;
    if (c->lim_mask & LIM_V_INSTANT_HIGH) cfg->v_instant_high = c->lim.v_instant_high;
    if (c->lim_mask & LIM_TRIP_MS) cfg->trip_ms = c->lim.trip_ms;
    if (c->lim_mask & LIM_RESTORE_DELAY) cfg->restore_delay_s = c->lim.restore_delay_s;
    if (c->lim_mask & LIM_I_LIMIT) cfg->i_limit = c->lim.i_limit;
    if (c->lim_mask & LIM_RESTORE_POLICY) cfg->restore_policy = c->lim.restore_policy;
}

bool cal_adjust(float *gain, float measured, float reference)
{
    if (!(measured > 0.0f) || !(reference > 0.0f) || !isfinite(measured) || !isfinite(reference)) {
        return false;
    }
    const float factor = reference / measured;
    if (factor < 0.8f || factor > 1.2f) {
        return false;
    }
    const float g = *gain * factor;
    if (g < 0.7f || g > 1.3f) {
        return false;
    }
    *gain = g;
    return true;
}

/* ---------- de-duplication ---------- */

const dedupe_entry_t *dedupe_find(const dedupe_t *d, const char *id)
{
    for (uint8_t i = 0; i < d->count; i++) {
        if (strcmp(d->e[i].id, id) == 0) {
            return &d->e[i];
        }
    }
    return NULL;
}

void dedupe_put(dedupe_t *d, const char *id, bool ok, const char *err)
{
    dedupe_entry_t *e = &d->e[d->next];
    memset(e, 0, sizeof(*e));
    strncpy(e->id, id, CMD_ID_MAX - 1);
    e->ok = ok;
    if (err != NULL) {
        strncpy(e->err, err, sizeof(e->err) - 1);
    }
    d->next = (uint8_t)((d->next + 1) % DEDUPE_SLOTS);
    if (d->count < DEDUPE_SLOTS) {
        d->count++;
    }
}

/* ---------- aggregation ---------- */

void agg_reset(agg_t *a)
{
    memset(a, 0, sizeof(*a));
}

void agg_add(agg_t *a, const sws_meas_t *m)
{
    if (!m->valid) {
        return;
    }
    a->v += m->v_rms;
    for (int k = 0; k < SWS_OUTLETS; k++) {
        a->i[k] += m->i_rms[k];
        a->p[k] += m->p_w[k];
    }
    a->n++;
}

void telemetry_from_agg(telemetry_t *t, const agg_t *a)
{
    if (a->n == 0) {
        t->v = NAN;
        for (int k = 0; k < SWS_OUTLETS; k++) {
            t->i[k] = NAN;
            t->p[k] = NAN;
        }
        return;
    }
    t->v = (float)(a->v / a->n);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        t->i[k] = (float)(a->i[k] / a->n);
        t->p[k] = (float)(a->p[k] / a->n);
    }
}

float power_factor(float p, float v, float i)
{
    if (!isfinite(p) || !isfinite(v) || !isfinite(i) || i < 0.02f || v < 50.0f) {
        return -1.0f;
    }
    float pf = p / (v * i);
    if (pf < 0.0f) {
        pf = -pf;
    }
    return pf > 1.0f ? 1.0f : pf;
}

/* ---------- builders ---------- */

int msg_telemetry(char *buf, size_t n, const telemetry_t *t)
{
    jbuf_t j = jb_init(buf, n);
    jb(&j, "{\"ts\":%lld,\"seq\":%lu,\"up\":%lu,", (long long)t->ts, (unsigned long)t->seq,
       (unsigned long)t->uptime_s);
    jb_num(&j, "v", t->v, 1);
    jb(&j, ",\"o\":[");
    for (int k = 0; k < SWS_OUTLETS; k++) {
        const float pf = power_factor(t->p[k], t->v, t->i[k]);
        jb(&j, "%s{", k ? "," : "");
        jb_num(&j, "i", t->i[k], 3);
        jb(&j, ",");
        jb_num(&j, "p", t->p[k], 1);
        jb(&j, ",");
        jb_num(&j, "pf", pf < 0 ? NAN : pf, 2);
        jb(&j, ",");
        jb_num(&j, "wh", t->wh[k], 1);
        jb(&j, ",\"relay\":%s,\"state\":\"%s\"}", t->relay[k] ? "true" : "false",
           prot_state_name(t->state[k]));
    }
    jb(&j, "],");
    jb_num(&j, "temp", t->temp_valid ? t->temp_c : NAN, 1);
    jb(&j, ",\"rssi\":%d,\"meter\":\"%s\"}", t->rssi, t->meter_ok ? "ok" : "fault");
    return jb_done(&j);
}

int msg_prot_event(char *buf, size_t n, const prot_event_t *e, int64_t ts, uint32_t seq)
{
    jbuf_t j = jb_init(buf, n);
    const char *type = "unknown";
    switch (e->type) {
    case PEV_STATE:
        switch (e->state) {
        case PROT_TRIPPED: type = "trip"; break;
        case PROT_WAITING: type = "waiting"; break;
        case PROT_NORMAL: type = "restore"; break;
        case PROT_LOCKED: type = "lock"; break;
        }
        break;
    case PEV_RELAY: type = "relay"; break;
    case PEV_METER_FAULT: type = "meter_fault"; break;
    case PEV_METER_OK: type = "meter_ok"; break;
    }
    jb(&j, "{\"ts\":%lld,\"seq\":%lu,\"type\":\"%s\"", (long long)ts, (unsigned long)seq, type);
    if (e->outlet >= 0) {
        jb(&j, ",\"outlet\":%d", e->outlet);
    }
    if (e->type == PEV_STATE) {
        jb(&j, ",\"state\":\"%s\",\"reason\":\"%s\",", prot_state_name(e->state),
           prot_reason_name(e->reason));
        jb_num(&j, "value", e->value, 2);
    } else if (e->type == PEV_RELAY) {
        jb(&j, ",\"on\":%s", e->value > 0.5f ? "true" : "false");
    }
    jb(&j, "}");
    return jb_done(&j);
}

int msg_boot(char *buf, size_t n, int64_t ts, uint32_t seq, const char *fw, const char *reset_reason)
{
    jbuf_t j = jb_init(buf, n);
    jb(&j, "{\"ts\":%lld,\"seq\":%lu,\"type\":\"boot\",\"fw\":\"%s\",\"reset_reason\":\"%s\"}",
       (long long)ts, (unsigned long)seq, fw, reset_reason);
    return jb_done(&j);
}

int msg_outage(char *buf, size_t n, int64_t ts, uint32_t seq, int64_t start, int64_t end,
               uint32_t resolution_s)
{
    jbuf_t j = jb_init(buf, n);
    const int64_t dur = end > start ? end - start : 0;
    jb(&j,
       "{\"ts\":%lld,\"seq\":%lu,\"type\":\"outage\",\"start\":%lld,\"end\":%lld,"
       "\"duration_s\":%lld,\"resolution_s\":%lu}",
       (long long)ts, (unsigned long)seq, (long long)start, (long long)end, (long long)dur,
       (unsigned long)resolution_s);
    return jb_done(&j);
}

int msg_reported(char *buf, size_t n, const prot_t *p, int64_t ts, const char *fw,
                 const char *board, uint32_t cfg_ver, bool time_synced)
{
    jbuf_t j = jb_init(buf, n);
    jb(&j, "{\"ts\":%lld,\"fw\":\"%s\",\"board\":\"%s\",\"cfg_ver\":%lu,\"time_synced\":%s,"
           "\"meter\":\"%s\",\"o\":[",
       (long long)ts, fw, board, (unsigned long)cfg_ver, time_synced ? "true" : "false",
       p->meter_fault ? "fault" : "ok");
    for (int k = 0; k < SWS_OUTLETS; k++) {
        const prot_outlet_t *o = &p->o[k];
        const prot_cfg_t *c = &p->cfg[k];
        jb(&j,
           "%s{\"relay\":%s,\"desired\":%s,\"state\":\"%s\",\"reason\":\"%s\",\"limits\":{",
           k ? "," : "", o->relay_on ? "true" : "false", o->desired_on ? "true" : "false",
           prot_state_name(o->state), prot_reason_name(o->reason));
        jb_num(&j, "v_low", c->v_low, 1);
        jb(&j, ",");
        jb_num(&j, "v_high", c->v_high, 1);
        jb(&j, ",");
        jb_num(&j, "v_instant_high", c->v_instant_high, 1);
        jb(&j, ",\"trip_ms\":%lu,\"restore_delay_s\":%lu,", (unsigned long)c->trip_ms,
           (unsigned long)c->restore_delay_s);
        jb_num(&j, "i_limit", c->i_limit, 2);
        jb(&j, ",\"restore_policy\":\"%s\"}}", policy_name(c->restore_policy));
    }
    jb(&j, "]}");
    return jb_done(&j);
}

int msg_ack(char *buf, size_t n, const char *id, bool ok, const char *err)
{
    jbuf_t j = jb_init(buf, n);
    jb(&j, "{\"id\":\"%s\",\"ok\":%s", id, ok ? "true" : "false");
    if (!ok && err != NULL) {
        /* Error strings are fixed text from this firmware; no quotes in them. */
        jb(&j, ",\"error\":\"%s\"", err);
    }
    jb(&j, "}");
    return jb_done(&j);
}
