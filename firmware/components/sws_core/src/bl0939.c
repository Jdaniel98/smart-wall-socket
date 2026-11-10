#include "sws/bl0939.h"

#include <string.h>

#define BL0939_HEADER 0x55
#define BL0939_READ_CMD 0x55
#define BL0939_WRITE_CMD 0xA5

const uint8_t BL0939_READ_FULL_CMD[2] = {0x55, 0xAA};

/* Belling reference design, also used by the Sonoff Dual R3 v2:
 * 1 mOhm shunts, 5 x 390 kOhm + 0.51 kOhm divider, 1.218 V reference. */
const bl0939_frontend_t BL0939_FRONTEND_REFERENCE = {
    .shunt_mohm = {1.0, 1.0},
    .div_r_top_kohm = 5 * 390.0,
    .div_r_bottom_kohm = 0.51,
    .vref = 1.218,
};

/* Datasheet transfer constants (direct, shunt-sensing mode). */
#define K_CURRENT 324004.0 /* counts per (mV across shunt / Vref) */
#define K_VOLTAGE 79931.0  /* counts per (mV at divider tap / Vref) */
#define K_POWER 4046.0     /* counts per (mV_shunt * mV_divider / Vref^2) */
#define K_ENERGY_DIV (1638.4 * 256.0) /* power counts per energy pulse rate */

void bl0939_cal_init(bl0939_cal_t *cal, const bl0939_frontend_t *fe)
{
    memset(cal, 0, sizeof(*cal));
    const double vref = fe->vref;
    /* Divider ratio, in mV at the tap per volt of mains. */
    const double div_mv_per_v =
        1000.0 * fe->div_r_bottom_kohm / (fe->div_r_top_kohm + fe->div_r_bottom_kohm);

    cal->u_ref = K_VOLTAGE * div_mv_per_v / vref;
    cal->gain_v = 1.0f;
    for (int ch = 0; ch < SWS_OUTLETS; ch++) {
        /* mV across the shunt per amp equals the shunt value in milliohm. */
        const double shunt_mv_per_a = fe->shunt_mohm[ch];
        cal->i_ref[ch] = K_CURRENT * shunt_mv_per_a / vref;
        cal->p_ref[ch] = K_POWER * shunt_mv_per_a * div_mv_per_v / (vref * vref);
        /* Pulses per kWh: power counts per watt * 3.6e6 J/kWh / pulse divisor. */
        cal->e_ref[ch] = cal->p_ref[ch] * 3.6e6 / K_ENERGY_DIV;
        cal->gain_i[ch] = 1.0f;
        cal->gain_p[ch] = 1.0f;
    }
}

void bl0939_build_write(uint8_t reg, uint32_t value, uint8_t out[BL0939_WRITE_LEN])
{
    out[0] = BL0939_WRITE_CMD;
    out[1] = reg;
    out[2] = (uint8_t)(value & 0xFF);
    out[3] = (uint8_t)((value >> 8) & 0xFF);
    out[4] = (uint8_t)((value >> 16) & 0xFF);
    uint8_t sum = 0;
    for (int i = 0; i < 5; i++) {
        sum = (uint8_t)(sum + out[i]);
    }
    out[5] = (uint8_t)~sum;
}

size_t bl0939_init_sequence(uint8_t out[][BL0939_WRITE_LEN], size_t max_frames)
{
    static const struct {
        uint8_t reg;
        uint32_t value;
    } seq[] = {
        {BL0939_REG_SOFT_RESET, 0x5A5A5A},  /* reset to defaults */
        {BL0939_REG_USR_WRPROT, 0x000055},  /* allow user register writes */
        {BL0939_REG_MODE, 0x001000},        /* 50 Hz, 800 ms RMS update, CF off */
        {BL0939_REG_TPS_CTRL, 0x0047FF},    /* alarms on, auto temperature, 100 ms */
        {BL0939_REG_IA_FAST_RMS_CTRL, 0x00181C}, /* half-cycle fast RMS */
        {BL0939_REG_IB_FAST_RMS_CTRL, 0x00181C},
    };
    const size_t n = sizeof(seq) / sizeof(seq[0]);
    if (max_frames < n) {
        return 0;
    }
    for (size_t i = 0; i < n; i++) {
        bl0939_build_write(seq[i].reg, seq[i].value, out[i]);
    }
    return n;
}

static uint32_t u24(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16);
}

static int32_t s24(const uint8_t *p)
{
    uint32_t v = u24(p);
    if (v & 0x800000u) {
        v |= 0xFF000000u;
    }
    return (int32_t)v;
}

bl0939_status_t bl0939_parse(const uint8_t *buf, size_t len, bl0939_raw_t *out)
{
    if (buf == NULL || len != BL0939_FRAME_LEN) {
        return BL0939_ERR_LEN;
    }
    if (buf[0] != BL0939_HEADER) {
        return BL0939_ERR_HEADER;
    }
    uint8_t sum = BL0939_READ_CMD;
    for (size_t i = 0; i < BL0939_FRAME_LEN - 1; i++) {
        sum = (uint8_t)(sum + buf[i]);
    }
    if ((uint8_t)~sum != buf[BL0939_FRAME_LEN - 1]) {
        return BL0939_ERR_CHECKSUM;
    }

    /* Field offsets in the 35-byte packet. */
    out->ia_fast_rms = u24(&buf[1]);
    out->ia_rms = u24(&buf[4]);
    out->ib_rms = u24(&buf[7]);
    out->v_rms = u24(&buf[10]);
    out->ib_fast_rms = u24(&buf[13]);
    out->a_watt = s24(&buf[16]);
    out->b_watt = s24(&buf[19]);
    out->cfa_cnt = u24(&buf[22]);
    out->cfb_cnt = u24(&buf[25]);
    out->tps1 = (uint16_t)(buf[28] | (buf[29] << 8));
    /* buf[30] reserved, buf[31..32] TPS2, buf[33] reserved, buf[34] checksum */
    return BL0939_OK;
}

float bl0939_temp_c(uint16_t tps1)
{
    const float tb = (float)(tps1 & 0x3FF);
    return (170.0f / 448.0f) * (tb / 2.0f - 32.0f) - 45.0f;
}

void bl0939_convert(const bl0939_raw_t *raw, const bl0939_cal_t *cal, sws_meas_t *m)
{
    m->valid = true;
    m->v_rms = (float)(raw->v_rms / cal->u_ref) * cal->gain_v;
    m->i_rms[0] = (float)(raw->ia_rms / cal->i_ref[0]) * cal->gain_i[0];
    m->i_rms[1] = (float)(raw->ib_rms / cal->i_ref[1]) * cal->gain_i[1];
    m->p_w[0] = (float)(raw->a_watt / cal->p_ref[0]) * cal->gain_p[0];
    m->p_w[1] = (float)(raw->b_watt / cal->p_ref[1]) * cal->gain_p[1];
    m->temp_c = bl0939_temp_c(raw->tps1);
    m->temp_valid = true;
}
