#include "sws/energy.h"

#include <string.h>

#define COUNTER_MASK 0xFFFFFFu

void energy_init(energy_acc_t *e, const uint64_t persisted[SWS_OUTLETS])
{
    memset(e, 0, sizeof(*e));
    if (persisted != NULL) {
        for (int i = 0; i < SWS_OUTLETS; i++) {
            e->pulses[i] = persisted[i];
        }
    }
}

void energy_chip_reset(energy_acc_t *e)
{
    e->have_last = false;
}

void energy_update(energy_acc_t *e, uint32_t raw_a, uint32_t raw_b)
{
    const uint32_t raw[SWS_OUTLETS] = {raw_a & COUNTER_MASK, raw_b & COUNTER_MASK};
    if (!e->have_last) {
        for (int i = 0; i < SWS_OUTLETS; i++) {
            e->last_raw[i] = raw[i];
        }
        e->have_last = true;
        return;
    }
    for (int i = 0; i < SWS_OUTLETS; i++) {
        const uint32_t step = (raw[i] - e->last_raw[i]) & COUNTER_MASK;
        if (step <= ENERGY_MAX_STEP) {
            e->pulses[i] += step;
        } else {
            /* Counter went backwards or jumped: unexpected chip reset or a
             * corrupted frame that passed the checksum. Re-baseline, lose
             * at most one interval. */
            e->rejected_steps++;
        }
        e->last_raw[i] = raw[i];
    }
}

double energy_wh(const energy_acc_t *e, int outlet, double pulses_per_kwh, float gain)
{
    if (outlet < 0 || outlet >= SWS_OUTLETS || pulses_per_kwh <= 0.0) {
        return 0.0;
    }
    return (double)e->pulses[outlet] / pulses_per_kwh * 1000.0 * (double)gain;
}
