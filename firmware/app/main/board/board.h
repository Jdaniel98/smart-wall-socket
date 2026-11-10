/*
 * Board layer: everything that differs between Proto 0 (Sonoff Dual R3 v2)
 * and the EVT board lives behind this struct. The rest of the firmware only
 * sees outlets, a metering UART, inputs and one status LED.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "driver/uart.h"
#include "sws/bl0939.h"
#include "sws/protection.h"
#include "sws/relay_drive.h"

typedef struct {
    const char *name;               /* reported to the cloud */

    /* Metering */
    uart_port_t meter_uart;
    gpio_num_t meter_tx;            /* ESP32 TX -> BL0939 RX */
    gpio_num_t meter_rx;            /* ESP32 RX <- BL0939 TX */
    bl0939_frontend_t frontend;

    /* Relays (low-side driven, active high) */
    gpio_num_t relay_pin[SWS_OUTLETS];
    relay_drive_cfg_t relay_cfg;
    gpio_num_t zero_cross;          /* GPIO_NUM_NC if absent */

    /* Inputs (active low) */
    gpio_num_t button;              /* on-board button */
    gpio_num_t touch[SWS_OUTLETS];  /* per-outlet touch or switch input, NC if unused */
    bool touch_enabled_by_default;

    /* One status LED */
    gpio_num_t status_led;
    bool status_led_active_low;

    /* Socket-wide protection limits for this hardware */
    prot_socket_cfg_t socket_limits;
    float default_i_limit;          /* A, per outlet */

    /* Where the temperature used for the over-temperature trip comes from */
    const char *temp_source;
} board_t;

const board_t *board_get(void);
