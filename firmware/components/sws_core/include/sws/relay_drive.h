/*
 * Relay coil drive: full voltage to pull in, then PWM holding at reduced
 * duty, and zero-cross timing so contacts close near a voltage zero.
 *
 * Non-latching relays are deliberate: they open by themselves on power loss,
 * so the restore delay always runs before an appliance sees mains again.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "sws/sws_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t pull_in_ms;    /* full duty after energising (50 ms) */
    uint16_t hold_permille; /* holding duty, 1000 = full voltage (PWM holding off) */
    uint32_t operate_us;    /* relay operate time, for zero-cross alignment */
} relay_drive_cfg_t;

typedef struct {
    bool closed;
    sws_ms_t energised_at;
} relay_drive_t;

void relay_drive_init(relay_drive_t *r);

/* Duty in permille for the coil at time now, given whether it should be closed. */
uint16_t relay_drive_duty(relay_drive_t *r, const relay_drive_cfg_t *cfg, bool want_closed,
                          sws_ms_t now);

/*
 * Delay from a zero-cross edge to energising the coil so that the contacts
 * close at the next zero crossing. half_period_us is 10000 at 50 Hz.
 * Returns a value in [0, half_period_us).
 */
uint32_t relay_zc_delay_us(uint32_t operate_us, uint32_t half_period_us);

#ifdef __cplusplus
}
#endif
