/*
 * Proto 0: Sonoff Dual R3 v2 (BL0939 metering). Bench use only.
 *
 * Pin map (confirmed against units in the field):
 *   GPIO0  on-board button        GPIO13 blue Wi-Fi LED (active low)
 *   GPIO4  BL0939 zero-cross      GPIO14 relay 2 (and red LED 2)
 *   GPIO25 ESP TX -> BL0939 RX    GPIO27 relay 1 (and red LED 1)
 *   GPIO26 ESP RX <- BL0939 TX    GPIO32/33 S1/S2 switch inputs
 *
 * SAFETY: treat every pin on this board as live while it is on mains.
 * The S1/S2 terminals are left disabled by default: anything wired to them
 * is at mains potential on a non-isolated board.
 *
 * Ratings: 10 A per gang, 15 A total, -10 to 40 degC ambient. Our own limits
 * stay at or below these.
 */
#include "sdkconfig.h"

#ifdef CONFIG_SWS_BOARD_DUALR3V2

#include "board.h"

static const board_t s_board = {
    .name = "dualr3v2",

    .meter_uart = UART_NUM_1,
    .meter_tx = GPIO_NUM_25,
    .meter_rx = GPIO_NUM_26,
    .frontend = {
        .shunt_mohm = {1.0, 1.0},
        .div_r_top_kohm = 5 * 390.0,
        .div_r_bottom_kohm = 0.51,
        .vref = 1.218,
    },

    .relay_pin = {GPIO_NUM_27, GPIO_NUM_14},
    .relay_cfg = {
        .pull_in_ms = 50,
        /* Full voltage: the Sonoff's coil drive circuit is not characterised,
         * so PWM holding stays off until measured on the bench
         * (console: `hold <permille>`). */
        .hold_permille = 1000,
        .operate_us = 8000, /* typical for 10 A sugar-cube relays; measure */
    },
    .zero_cross = GPIO_NUM_4,

    .button = GPIO_NUM_0,
    .touch = {GPIO_NUM_32, GPIO_NUM_33},
    .touch_enabled_by_default = false,

    .status_led = GPIO_NUM_13,
    .status_led_active_low = true,

    .socket_limits = {
        .total_i_limit = 15.0f,
        .i_max_board = 10.0f,
        /* No NTCs on this board: the BL0939's own die temperature is used as
         * a crude board-temperature proxy. EVT adds NTCs at the relays and
         * terminals. */
        .t_limit_c = 75.0f,
        .t_reset_margin_c = 10.0f,
        .meter_timeout_ms = 5000,
    },
    .default_i_limit = 10.0f,
    .temp_source = "bl0939_die",
};

const board_t *board_get(void)
{
    return &s_board;
}

#endif
