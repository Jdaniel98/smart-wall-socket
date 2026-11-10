#include "sws/bl0939.h"
#include "sws/energy.h"
#include "test.h"

/* Build a valid 35-byte frame from raw values. */
static void make_frame(uint8_t f[BL0939_FRAME_LEN], uint32_t ia, uint32_t ib, uint32_t v,
                       int32_t aw, int32_t bw, uint32_t cfa, uint32_t cfb, uint16_t tps1)
{
    memset(f, 0, BL0939_FRAME_LEN);
    f[0] = 0x55;
#define PUT24(off, val)                                  \
    do {                                                 \
        uint32_t _v = (uint32_t)(val) & 0xFFFFFF;        \
        f[(off)] = _v & 0xFF;                            \
        f[(off) + 1] = (_v >> 8) & 0xFF;                 \
        f[(off) + 2] = (_v >> 16) & 0xFF;                \
    } while (0)
    PUT24(1, ia);  /* fast rms a */
    PUT24(4, ia);
    PUT24(7, ib);
    PUT24(10, v);
    PUT24(13, ib); /* fast rms b */
    PUT24(16, aw);
    PUT24(19, bw);
    PUT24(22, cfa);
    PUT24(25, cfb);
    f[28] = tps1 & 0xFF;
    f[29] = tps1 >> 8;
    uint8_t sum = 0x55;
    for (int i = 0; i < BL0939_FRAME_LEN - 1; i++) {
        sum = (uint8_t)(sum + f[i]);
    }
    f[34] = (uint8_t)~sum;
}

static void test_init_sequence_matches_known_frames(void)
{
    /* Byte-exact start-up frames used on Sonoff Dual R3 v2 units in the field. */
    static const uint8_t expected[6][6] = {
        {0xA5, 0x19, 0x5A, 0x5A, 0x5A, 0x33},
        {0xA5, 0x1A, 0x55, 0x00, 0x00, 0xEB},
        {0xA5, 0x18, 0x00, 0x10, 0x00, 0x32},
        {0xA5, 0x1B, 0xFF, 0x47, 0x00, 0xF9},
        {0xA5, 0x10, 0x1C, 0x18, 0x00, 0x16},
        {0xA5, 0x1E, 0x1C, 0x18, 0x00, 0x08},
    };
    uint8_t out[8][BL0939_WRITE_LEN];
    const size_t n = bl0939_init_sequence(out, 8);
    CHECK(n == 6);
    for (size_t i = 0; i < n; i++) {
        CHECK(memcmp(out[i], expected[i], 6) == 0);
    }
    CHECK(bl0939_init_sequence(out, 3) == 0);
}

static void test_parse_valid_and_invalid_frames(void)
{
    uint8_t f[BL0939_FRAME_LEN];
    make_frame(f, 1000, 2000, 3000, -5, 7, 0x123456, 0xFFFFFF, 433);
    bl0939_raw_t r;
    CHECK(bl0939_parse(f, sizeof(f), &r) == BL0939_OK);
    CHECK(r.ia_rms == 1000);
    CHECK(r.ib_rms == 2000);
    CHECK(r.v_rms == 3000);
    CHECK(r.a_watt == -5);
    CHECK(r.b_watt == 7);
    CHECK(r.cfa_cnt == 0x123456);
    CHECK(r.cfb_cnt == 0xFFFFFF);
    CHECK(r.tps1 == 433);

    CHECK(bl0939_parse(f, 34, &r) == BL0939_ERR_LEN);
    f[10] ^= 0x01;
    CHECK(bl0939_parse(f, sizeof(f), &r) == BL0939_ERR_CHECKSUM);
    make_frame(f, 1, 1, 1, 0, 0, 0, 0, 0);
    f[0] = 0x54;
    CHECK(bl0939_parse(f, sizeof(f), &r) == BL0939_ERR_HEADER);
}

static void test_reference_conversion(void)
{
    bl0939_cal_t cal;
    bl0939_cal_init(&cal, &BL0939_FRONTEND_REFERENCE);
    /* Reference-design divisors, worked by hand from the datasheet formulas. */
    CHECK_NEAR(cal.i_ref[0], 324004.0 / 1.218, 0.01);
    CHECK_NEAR(cal.u_ref, 79931.0 * 0.51 * 1000.0 / (1.218 * (1950.0 + 0.51)), 0.001);
    CHECK_NEAR(cal.e_ref[0],
               3.6e6 * 4046.0 * 0.51 * 1000.0 / (1638.4 * 256.0 * 1.218 * 1.218 * 1950.51), 0.01);

    bl0939_raw_t r = {0};
    r.v_rms = (uint32_t)(230.0 * cal.u_ref + 0.5);
    r.ia_rms = (uint32_t)(8.7 * cal.i_ref[0] + 0.5);
    r.ib_rms = 0;
    r.a_watt = (int32_t)(2001.0 * cal.p_ref[0] + 0.5);
    r.b_watt = -3;
    r.tps1 = 433;
    sws_meas_t m;
    bl0939_convert(&r, &cal, &m);
    CHECK(m.valid);
    CHECK_NEAR(m.v_rms, 230.0, 0.01);
    CHECK_NEAR(m.i_rms[0], 8.7, 0.001);
    CHECK_NEAR(m.p_w[0], 2001.0, 0.1);
    CHECK(m.p_w[1] < 0.0f && m.p_w[1] > -0.01f);
    CHECK_NEAR(m.temp_c, 25.0, 0.5);

    cal.gain_v = 1.01f;
    bl0939_convert(&r, &cal, &m);
    CHECK_NEAR(m.v_rms, 232.3, 0.02);
}

static void test_energy_wrap_reset_and_glitch(void)
{
    energy_acc_t e;
    const uint64_t persisted[2] = {1000, 0};
    energy_init(&e, persisted);
    energy_update(&e, 0xFFFFF0, 10); /* baseline only */
    CHECK(e.pulses[0] == 1000 && e.pulses[1] == 0);
    energy_update(&e, 0x000010, 15); /* wrapped: +0x20 */
    CHECK(e.pulses[0] == 1000 + 0x20);
    CHECK(e.pulses[1] == 5);

    energy_update(&e, 0x800000, 15); /* impossible jump: rejected */
    CHECK(e.pulses[0] == 1000 + 0x20);
    CHECK(e.rejected_steps == 1);

    energy_chip_reset(&e);
    energy_update(&e, 0, 0);  /* chip restarted from 0: new baseline, no loss */
    energy_update(&e, 6, 0);
    CHECK(e.pulses[0] == 1000 + 0x20 + 6);

    bl0939_cal_t cal;
    bl0939_cal_init(&cal, &BL0939_FRONTEND_REFERENCE);
    energy_acc_t k;
    const uint64_t one_kwh[2] = {(uint64_t)(cal.e_ref[0] + 0.5), 0};
    energy_init(&k, one_kwh);
    CHECK_NEAR(energy_wh(&k, 0, cal.e_ref[0], 1.0f), 1000.0, 0.2);
    CHECK_NEAR(energy_wh(&k, 0, cal.e_ref[0], 0.99f), 990.0, 0.2);
    CHECK(energy_wh(&k, 5, cal.e_ref[0], 1.0f) == 0.0);
}

void suite_bl0939(void)
{
    RUN(test_init_sequence_matches_known_frames);
    RUN(test_parse_valid_and_invalid_frames);
    RUN(test_reference_conversion);
}

void suite_energy(void)
{
    RUN(test_energy_wrap_reset_and_glitch);
}
