/*
 * Device <-> cloud messages (see docs/protocol.md): command parsing,
 * command de-duplication, and JSON builders for telemetry, events,
 * reported state and acks.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "sws/protection.h"
#include "sws/schedule.h"
#include "sws/sws_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define CMD_ID_MAX 48

typedef enum {
    CMD_RELAY = 1,
    CMD_RESET,
    CMD_LIMITS,
    CMD_SCHEDULE,
    CMD_CALIBRATE,
} cmd_type_t;

typedef enum {
    CAL_V = 0,
    CAL_I0,
    CAL_I1,
    CAL_P0,
    CAL_P1,
} cal_channel_t;

/* Bits for which limit fields a CMD_LIMITS message sets. */
enum {
    LIM_V_LOW = 1u << 0,
    LIM_V_HIGH = 1u << 1,
    LIM_V_INSTANT_HIGH = 1u << 2,
    LIM_TRIP_MS = 1u << 3,
    LIM_RESTORE_DELAY = 1u << 4,
    LIM_I_LIMIT = 1u << 5,
    LIM_RESTORE_POLICY = 1u << 6,
};

typedef struct {
    char id[CMD_ID_MAX];
    cmd_type_t type;
    int outlet;
    bool on;
    uint32_t lim_mask;
    prot_cfg_t lim;
    sched_entry_t sched[SCHED_MAX];
    uint8_t sched_n;
    cal_channel_t cal_ch;
    float cal_ref;
} sws_cmd_t;

/* Parse a desired-topic message. On failure returns false and sets *err.
 * If the id was readable it is copied into out->id even on failure, so the
 * device can still ack with the error. */
bool cmd_parse(const char *json, size_t len, sws_cmd_t *out, const char **err);

/* Apply the fields of a CMD_LIMITS command onto cfg. */
void cmd_apply_limits(const sws_cmd_t *c, prot_cfg_t *cfg);

/* Multiply *gain by reference/measured. Refuses corrections outside +-20%. */
bool cal_adjust(float *gain, float measured, float reference);

/* Remembers recent command ids so a repeated command is acked, not re-run. */
#define DEDUPE_SLOTS 16
typedef struct {
    char id[CMD_ID_MAX];
    bool ok;
    char err[48];
} dedupe_entry_t;

typedef struct {
    dedupe_entry_t e[DEDUPE_SLOTS];
    uint8_t next;
    uint8_t count;
} dedupe_t;

const dedupe_entry_t *dedupe_find(const dedupe_t *d, const char *id);
void dedupe_put(dedupe_t *d, const char *id, bool ok, const char *err);

/* Running means for the 10-second telemetry aggregate. */
typedef struct {
    double v, i[SWS_OUTLETS], p[SWS_OUTLETS];
    uint32_t n;
} agg_t;

void agg_reset(agg_t *a);
void agg_add(agg_t *a, const sws_meas_t *m);

typedef struct {
    int64_t ts;          /* Unix seconds, 0 if the clock is not set yet */
    uint32_t seq;
    uint32_t uptime_s;
    float v;
    float i[SWS_OUTLETS];
    float p[SWS_OUTLETS];
    double wh[SWS_OUTLETS];
    bool relay[SWS_OUTLETS];
    prot_state_t state[SWS_OUTLETS];
    float temp_c;
    bool temp_valid;
    int rssi;
    bool meter_ok;
} telemetry_t;

/* Fill the measurement part of t from a, leaving other fields alone. */
void telemetry_from_agg(telemetry_t *t, const agg_t *a);

/* Power factor P/(V*I), or a negative value when I is too small to say. */
float power_factor(float p, float v, float i);

/* JSON builders. Return bytes written (excluding NUL), or -1 if buf is too small. */
int msg_telemetry(char *buf, size_t n, const telemetry_t *t);
int msg_prot_event(char *buf, size_t n, const prot_event_t *e, int64_t ts, uint32_t seq);
int msg_boot(char *buf, size_t n, int64_t ts, uint32_t seq, const char *fw, const char *reset_reason);
int msg_outage(char *buf, size_t n, int64_t ts, uint32_t seq, int64_t start, int64_t end,
               uint32_t resolution_s);
int msg_reported(char *buf, size_t n, const prot_t *p, int64_t ts, const char *fw,
                 const char *board, uint32_t cfg_ver, bool time_synced);
int msg_ack(char *buf, size_t n, const char *id, bool ok, const char *err);

#ifdef __cplusplus
}
#endif
