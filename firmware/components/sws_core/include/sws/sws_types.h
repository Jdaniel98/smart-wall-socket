/*
 * Smart Wall Socket: shared types for the portable core.
 *
 * Everything under sws_core is plain C99 with no ESP-IDF dependency, so it
 * builds and is unit-tested on a Linux host as well as on the device.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Two outlets per socket. Index 0 is the left outlet, 1 the right. */
#define SWS_OUTLETS 2

/* Monotonic milliseconds since boot. 64-bit so it never wraps in practice. */
typedef uint64_t sws_ms_t;

/* One converted metering sample, in SI units. */
typedef struct {
    bool valid;            /* false if the metering chip gave no usable frame */
    float v_rms;           /* V, shared by both outlets */
    float i_rms[SWS_OUTLETS]; /* A, true RMS per outlet */
    float p_w[SWS_OUTLETS];   /* W, active power per outlet (can be slightly negative near 0) */
    float temp_c;          /* degC, board temperature source (see board notes) */
    bool temp_valid;
} sws_meas_t;

#ifdef __cplusplus
}
#endif
