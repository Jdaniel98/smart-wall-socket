/* BL0939 over UART: 4800 baud, 8 data bits, no parity, 2 stop bits. */
#include "app.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "metering";
static const board_t *s_b;

/* 35 bytes x 11 bits at 4800 baud is about 80 ms on the wire. */
#define READ_TIMEOUT_MS 150

esp_err_t metering_init(const board_t *b)
{
    s_b = b;
    const uart_config_t cfg = {
        .baud_rate = BL0939_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_2,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_RETURN_ON_ERROR(uart_driver_install(b->meter_uart, 256, 0, 0, NULL, 0), TAG, "install");
    ESP_RETURN_ON_ERROR(uart_param_config(b->meter_uart, &cfg), TAG, "config");
    ESP_RETURN_ON_ERROR(uart_set_pin(b->meter_uart, b->meter_tx, b->meter_rx, UART_PIN_NO_CHANGE,
                                     UART_PIN_NO_CHANGE),
                        TAG, "pins");

    uint8_t frames[8][BL0939_WRITE_LEN];
    const size_t n = bl0939_init_sequence(frames, 8);
    for (size_t i = 0; i < n; i++) {
        uart_write_bytes(b->meter_uart, frames[i], BL0939_WRITE_LEN);
        uart_wait_tx_done(b->meter_uart, pdMS_TO_TICKS(50));
        vTaskDelay(pdMS_TO_TICKS(i == 0 ? 20 : 5)); /* give the soft reset time */
    }
    uart_flush_input(b->meter_uart);
    ESP_LOGI(TAG, "BL0939 initialised on UART%d (TX %d, RX %d)", b->meter_uart, b->meter_tx,
             b->meter_rx);
    return ESP_OK;
}

bool metering_read(bl0939_raw_t *out, bl0939_status_t *status)
{
    *status = BL0939_ERR_LEN;
    if (s_b == NULL) {
        return false;
    }
    uart_flush_input(s_b->meter_uart);
    uart_write_bytes(s_b->meter_uart, BL0939_READ_FULL_CMD, sizeof(BL0939_READ_FULL_CMD));
    uint8_t buf[BL0939_FRAME_LEN];
    const int n = uart_read_bytes(s_b->meter_uart, buf, sizeof(buf), pdMS_TO_TICKS(READ_TIMEOUT_MS));
    if (n != (int)sizeof(buf)) {
        return false;
    }
    *status = bl0939_parse(buf, sizeof(buf), out);
    return *status == BL0939_OK;
}
