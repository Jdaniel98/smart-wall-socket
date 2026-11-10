/*
 * Belling BL0939 dual-channel metering IC: frame building, parsing and
 * conversion to SI units.
 *
 * Transport (UART at 4800 baud, 8N2 on the Sonoff Dual R3 v2) is handled by
 * the board layer; this module only deals in bytes, so it is host-testable.
 *
 * Protocol facts (from the BL0939 datasheet, cross-checked against the
 * ESPHome driver that runs on the Sonoff Dual R3 v2):
 *  - Full-packet read: send 0x55 0xAA, receive 35 bytes, first byte 0x55.
 *  - Multi-byte fields are little-endian 24-bit (low, mid, high).
 *  - Read checksum: ~(0x55 + sum of the 34 bytes before the checksum).
 *  - Register write: 0xA5, addr, d_low, d_mid, d_high, ~(0xA5 + addr + data).
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "sws/sws_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BL0939_FRAME_LEN 35
#define BL0939_WRITE_LEN 6
#define BL0939_UART_BAUD 4800

/* Read command: 0x55 then 0xAA requests the full 35-byte packet. */
extern const uint8_t BL0939_READ_FULL_CMD[2];

/* Registers used at start-up. */
#define BL0939_REG_IA_FAST_RMS_CTRL 0x10
#define BL0939_REG_MODE             0x18
#define BL0939_REG_SOFT_RESET       0x19
#define BL0939_REG_USR_WRPROT       0x1A
#define BL0939_REG_TPS_CTRL         0x1B
#define BL0939_REG_IB_FAST_RMS_CTRL 0x1E

/* Raw register values from one full packet. */
typedef struct {
    uint32_t ia_fast_rms;
    uint32_t ia_rms;
    uint32_t ib_rms;
    uint32_t v_rms;
    uint32_t ib_fast_rms;
    int32_t a_watt;   /* signed 24-bit, sign-extended */
    int32_t b_watt;
    uint32_t cfa_cnt; /* 24-bit energy pulse counter, wraps at 2^24 */
    uint32_t cfb_cnt;
    uint16_t tps1;    /* internal temperature, 10 bits used */
} bl0939_raw_t;

typedef enum {
    BL0939_OK = 0,
    BL0939_ERR_LEN,
    BL0939_ERR_HEADER,
    BL0939_ERR_CHECKSUM,
} bl0939_status_t;

/*
 * Divisors that turn raw counts into SI units, plus per-unit gains from
 * calibration. Built from the front-end component values so the same code
 * serves the Sonoff (Proto 0) and the EVT board.
 */
typedef struct {
    double u_ref;              /* counts per volt */
    double i_ref[SWS_OUTLETS]; /* counts per amp */
    double p_ref[SWS_OUTLETS]; /* counts per watt */
    double e_ref[SWS_OUTLETS]; /* pulses per kWh */
    /* Calibration gains, 1.0 = uncalibrated. Written at the test jig. */
    float gain_v;
    float gain_i[SWS_OUTLETS];
    float gain_p[SWS_OUTLETS];
} bl0939_cal_t;

/* Analogue front end, used to derive the reference divisors. */
typedef struct {
    double shunt_mohm[SWS_OUTLETS]; /* current shunt, milliohm */
    double div_r_top_kohm;          /* voltage divider top (e.g. 5 x 390 k) */
    double div_r_bottom_kohm;       /* voltage divider bottom (e.g. 0.51 k) */
    double vref;                    /* internal reference, 1.218 V typ. */
} bl0939_frontend_t;

/* Front end of the Sonoff Dual R3 v2, which matches the Belling reference design. */
extern const bl0939_frontend_t BL0939_FRONTEND_REFERENCE;

/* Fill cal with reference divisors for the given front end and unity gains. */
void bl0939_cal_init(bl0939_cal_t *cal, const bl0939_frontend_t *fe);

/* Build a 6-byte register write frame. value is 24-bit. */
void bl0939_build_write(uint8_t reg, uint32_t value, uint8_t out[BL0939_WRITE_LEN]);

/*
 * Start-up write sequence: soft reset, unlock user writes, mode (50 Hz,
 * 800 ms RMS update), temperature measurement, fast-RMS for both channels.
 * Returns the number of frames written to out (max_frames must be >= 6).
 */
size_t bl0939_init_sequence(uint8_t out[][BL0939_WRITE_LEN], size_t max_frames);

/* Parse one 35-byte full packet. */
bl0939_status_t bl0939_parse(const uint8_t *buf, size_t len, bl0939_raw_t *out);

/* Convert raw values to SI units using cal. Sets m->valid = true. */
void bl0939_convert(const bl0939_raw_t *raw, const bl0939_cal_t *cal, sws_meas_t *m);

/* Chip temperature in degC from TPS1 (datasheet formula). */
float bl0939_temp_c(uint16_t tps1);

#ifdef __cplusplus
}
#endif
