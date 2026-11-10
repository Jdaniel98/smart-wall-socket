/*
 * Protection state machine. Runs on the device and never waits for the network.
 *
 * Per outlet:
 *   NORMAL  --(V outside limits for trip_ms, or above v_instant_high once)--> TRIPPED
 *   TRIPPED --(V back inside limits with hysteresis)--> WAITING
 *   WAITING --(V stays inside limits for restore_delay_s)--> NORMAL
 *   WAITING --(V outside limits)--> TRIPPED (timer resets)
 *   any     --(over-current or over-temperature)--> LOCKED (needs a user reset)
 *
 * At power-up every outlet starts in WAITING, so appliances never get the
 * restoration surge: the restore delay runs first. Each outlet then follows
 * its restore policy (last state, always on, always off).
 *
 * The relay of an outlet is closed only when its state is NORMAL and the
 * user wants it on.
 *
 * Metering fault (no valid sample for meter_timeout_ms): voltage and current
 * checks pause, outlets that are on stay on, WAITING outlets restore on the
 * timer alone, TRIPPED outlets stay off, and temperature trips still apply
 * if the temperature source is separate from the metering chip.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "sws/sws_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    PROT_NORMAL = 0,
    PROT_TRIPPED,
    PROT_WAITING,
    PROT_LOCKED,
} prot_state_t;

typedef enum {
    REASON_NONE = 0,
    REASON_UNDERVOLTAGE,
    REASON_OVERVOLTAGE,
    REASON_SURGE,        /* above v_instant_high, tripped on one sample */
    REASON_OVERCURRENT,
    REASON_TOTAL_OVERCURRENT,
    REASON_OVERTEMP,
} prot_reason_t;

typedef enum {
    RESTORE_LAST = 0,
    RESTORE_ON,
    RESTORE_OFF,
} restore_policy_t;

/* Per-outlet limits. Users can change these within the bounds checked by
 * prot_cfg_validate(). */
typedef struct {
    float v_low;              /* V */
    float v_high;             /* V */
    float v_instant_high;     /* V, trips on a single sample */
    float v_hyst;             /* V, re-arm margin inside the limits */
    uint32_t trip_ms;         /* how long V must stay out of limits */
    uint32_t restore_delay_s; /* how long V must stay good before restoring */
    float i_limit;            /* A, sustained over-current threshold */
    uint32_t i_trip_ms;       /* how long I may exceed i_limit */
    float i_instant_factor;   /* trip on one sample above i_limit * factor */
    restore_policy_t restore_policy;
} prot_cfg_t;

/* Socket-wide limits, set by the board (not user-adjustable). */
typedef struct {
    float total_i_limit;      /* A, both outlets combined */
    float i_max_board;        /* A, upper bound for any user i_limit */
    float t_limit_c;          /* degC, over-temperature lock */
    float t_reset_margin_c;   /* degC below t_limit before a reset is allowed */
    uint32_t meter_timeout_ms;
} prot_socket_cfg_t;

typedef enum {
    PEV_STATE = 1,   /* outlet changed state; reason says why */
    PEV_RELAY,       /* relay output changed; value = 1 closed, 0 open */
    PEV_METER_FAULT,
    PEV_METER_OK,
} prot_event_type_t;

typedef struct {
    prot_event_type_t type;
    int8_t outlet;          /* -1 for socket-wide events */
    prot_state_t state;     /* new state for PEV_STATE */
    prot_reason_t reason;
    float value;            /* the measurement that caused it, or relay level */
    sws_ms_t at_ms;
} prot_event_t;

#define PROT_EVENT_QUEUE 16

typedef struct {
    prot_state_t state;
    prot_reason_t reason;  /* why it is TRIPPED or LOCKED */
    bool desired_on;       /* the user's intent */
    bool relay_on;         /* output */
    sws_ms_t bad_since;    /* 0 = voltage currently within limits */
    sws_ms_t good_since;   /* WAITING timer start, 0 = not started */
    sws_ms_t oc_since;     /* 0 = not over-current */
} prot_outlet_t;

typedef struct {
    prot_cfg_t cfg[SWS_OUTLETS];
    prot_socket_cfg_t scfg;
    prot_outlet_t o[SWS_OUTLETS];
    bool meter_ok;         /* a valid sample arrived within meter_timeout_ms */
    bool meter_fault;      /* fault declared and reported */
    sws_ms_t last_meas_ms;
    sws_ms_t boot_ms;
    sws_ms_t total_oc_since;
    float last_temp_c;
    bool last_temp_valid;
    prot_event_t ev[PROT_EVENT_QUEUE];
    uint8_t ev_head, ev_count;
    uint32_t ev_dropped;
} prot_t;

typedef enum {
    PROT_CMD_OK = 0,
    PROT_CMD_BAD_OUTLET,
    PROT_CMD_LOCKED,         /* outlet must be reset first */
    PROT_CMD_NOT_LOCKED,
    PROT_CMD_STILL_HOT,      /* over-temperature reset refused */
} prot_cmd_result_t;

/* Appliance presets for sensible defaults. */
typedef enum {
    APPLIANCE_GENERAL = 0,
    APPLIANCE_COMPRESSOR,  /* fridge, freezer, AC: long restore delay */
} appliance_t;

void prot_cfg_default(prot_cfg_t *cfg, appliance_t appliance, float i_limit);

/* NULL if valid, otherwise a short reason string. */
const char *prot_cfg_validate(const prot_cfg_t *cfg, const prot_socket_cfg_t *scfg);

/* last_on: persisted relay intent per outlet, used by RESTORE_LAST. */
void prot_init(prot_t *p, const prot_cfg_t cfg[SWS_OUTLETS], const prot_socket_cfg_t *scfg,
               const bool last_on[SWS_OUTLETS], sws_ms_t now);

/* Call often (every 50-200 ms). m is the new sample, or NULL if none arrived. */
void prot_update(prot_t *p, const sws_meas_t *m, sws_ms_t now);

/* User intent from touch, app, Matter or a schedule. */
prot_cmd_result_t prot_set_desired(prot_t *p, int outlet, bool on, sws_ms_t now);

/* Clear a LOCKED outlet. The outlet comes back off; the user turns it on. */
prot_cmd_result_t prot_reset(prot_t *p, int outlet, sws_ms_t now);

/* Replace an outlet's limits (already validated). */
prot_cmd_result_t prot_set_cfg(prot_t *p, int outlet, const prot_cfg_t *cfg);

bool prot_relay(const prot_t *p, int outlet);

/* Returns false when the queue is empty. */
bool prot_pop_event(prot_t *p, prot_event_t *out);

const char *prot_state_name(prot_state_t s);
const char *prot_reason_name(prot_reason_t r);

#ifdef __cplusplus
}
#endif
