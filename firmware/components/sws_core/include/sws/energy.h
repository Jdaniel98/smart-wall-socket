/*
 * Cumulative energy per outlet from the BL0939's 24-bit pulse counters.
 *
 * The chip counter wraps at 2^24 and resets to 0 when the chip resets, so
 * this module tracks deltas and keeps a 64-bit total that the app persists.
 * A cumulative counter (never a per-interval value) is what goes to the
 * cloud, so a gap in data never loses energy.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "sws/sws_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Largest believable step between two reads. At 800 ms reads and 3.7 kW the
 * reference front end produces only a few pulses, so anything near half the
 * counter range is a chip reset or a glitch, not energy. */
#define ENERGY_MAX_STEP 0x10000u

typedef struct {
    uint64_t pulses[SWS_OUTLETS]; /* accumulated since manufacture */
    uint32_t last_raw[SWS_OUTLETS];
    bool have_last;
    uint32_t rejected_steps;      /* diagnostics */
} energy_acc_t;

/* Start from a persisted total (pulses). */
void energy_init(energy_acc_t *e, const uint64_t persisted[SWS_OUTLETS]);

/* Call after the metering chip is (re)initialised: the next read sets a new baseline. */
void energy_chip_reset(energy_acc_t *e);

/* Feed the raw counters from one frame. */
void energy_update(energy_acc_t *e, uint32_t raw_a, uint32_t raw_b);

/* Energy in Wh for one outlet, given pulses per kWh and a calibration gain. */
double energy_wh(const energy_acc_t *e, int outlet, double pulses_per_kwh, float gain);

#ifdef __cplusplus
}
#endif
