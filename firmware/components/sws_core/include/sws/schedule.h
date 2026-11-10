/*
 * On-device schedules. Stored and run locally; the cloud only syncs them.
 * Schedules never fire for times that passed while the socket was off:
 * after an outage the restore policy decides, not a missed schedule.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "sws/sws_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SCHED_MAX 8
#define SCHED_ALL_DAYS 0x7F

typedef struct {
    uint8_t days;     /* bit 0 = Monday ... bit 6 = Sunday */
    uint16_t minute;  /* local minute of day, 0-1439 */
    bool on;          /* action: switch on (true) or off (false) */
} sched_entry_t;

typedef struct {
    sched_entry_t e[SWS_OUTLETS][SCHED_MAX];
    uint8_t n[SWS_OUTLETS];
    int64_t last_min;  /* last evaluated local epoch minute, -1 = not started */
} sched_t;

void sched_init(sched_t *s);

/* Replace one outlet's entries. Returns false if invalid (nothing changed). */
bool sched_set(sched_t *s, int outlet, const sched_entry_t *entries, uint8_t count);

/*
 * Evaluate at utc_s (Unix seconds) in a zone tz_offset_min east of UTC
 * (0 for Accra). For each outlet, act[k] is set true if an entry fired since
 * the last call, and on[k] gives the last action that fired.
 */
void sched_run(sched_t *s, int64_t utc_s, int32_t tz_offset_min, bool act[SWS_OUTLETS],
               bool on[SWS_OUTLETS]);

/* Weekday of a local epoch day, Monday = 0. */
int sched_weekday(int64_t local_epoch_day);

#ifdef __cplusplus
}
#endif
