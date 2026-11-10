#include "sws/schedule.h"

#include <string.h>

/* Longest gap we replay. Larger jumps (first sync, clock fix) just re-baseline. */
#define MAX_CATCHUP_MIN 10

void sched_init(sched_t *s)
{
    memset(s, 0, sizeof(*s));
    s->last_min = -1;
}

bool sched_set(sched_t *s, int outlet, const sched_entry_t *entries, uint8_t count)
{
    if (outlet < 0 || outlet >= SWS_OUTLETS || count > SCHED_MAX) {
        return false;
    }
    for (uint8_t i = 0; i < count; i++) {
        if (entries[i].minute >= 1440 || entries[i].days == 0 ||
            (entries[i].days & ~SCHED_ALL_DAYS) != 0) {
            return false;
        }
    }
    memcpy(s->e[outlet], entries, sizeof(sched_entry_t) * count);
    s->n[outlet] = count;
    return true;
}

int sched_weekday(int64_t local_epoch_day)
{
    /* 1970-01-01 was a Thursday (Monday = 0, so Thursday = 3). */
    int64_t w = (local_epoch_day + 3) % 7;
    if (w < 0) {
        w += 7;
    }
    return (int)w;
}

static int64_t floor_div(int64_t a, int64_t b)
{
    int64_t q = a / b;
    if ((a % b != 0) && ((a < 0) != (b < 0))) {
        q--;
    }
    return q;
}

void sched_run(sched_t *s, int64_t utc_s, int32_t tz_offset_min, bool act[SWS_OUTLETS],
               bool on[SWS_OUTLETS])
{
    for (int k = 0; k < SWS_OUTLETS; k++) {
        act[k] = false;
        on[k] = false;
    }
    const int64_t now_min = floor_div(utc_s, 60) + tz_offset_min;
    if (s->last_min < 0 || now_min < s->last_min || now_min - s->last_min > MAX_CATCHUP_MIN) {
        s->last_min = now_min;
        return;
    }
    for (int64_t m = s->last_min + 1; m <= now_min; m++) {
        const int64_t day = floor_div(m, 1440);
        const uint16_t mod = (uint16_t)(m - day * 1440);
        const uint8_t day_bit = (uint8_t)(1u << sched_weekday(day));
        for (int k = 0; k < SWS_OUTLETS; k++) {
            for (uint8_t i = 0; i < s->n[k]; i++) {
                const sched_entry_t *e = &s->e[k][i];
                if (e->minute == mod && (e->days & day_bit)) {
                    act[k] = true;
                    on[k] = e->on;
                }
            }
        }
    }
    s->last_min = now_min;
}
