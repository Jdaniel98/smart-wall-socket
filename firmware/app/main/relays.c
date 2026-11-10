/*
 * Relay coils on LEDC PWM: full duty to pull in, then the holding duty.
 * Closing waits for a zero crossing (if the board has one) so the contacts
 * meet near 0 V, which cuts arcing and inrush wear. Opening is immediate.
 */
#include "app.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "sws/relay_drive.h"

static const char *TAG = "relays";

#define PWM_FREQ_HZ 20000 /* above hearing, low switching loss */
#define PWM_BITS LEDC_TIMER_10_BIT
#define PWM_MAX ((1u << 10) - 1u)
#define HALF_PERIOD_US 10000 /* 50 Hz mains */
#define ZC_WAIT_MS 25

static const board_t *s_b;
static relay_drive_t s_rd[SWS_OUTLETS];
static relay_drive_cfg_t s_cfg;
static uint16_t s_duty[SWS_OUTLETS];
static SemaphoreHandle_t s_zc;
static bool s_zc_seen, s_zc_missing_logged;

static void IRAM_ATTR zc_isr(void *arg)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(s_zc, &woken);
    if (woken) {
        portYIELD_FROM_ISR();
    }
}

static void set_duty(int k, uint16_t permille)
{
    if (s_duty[k] == permille) {
        return;
    }
    s_duty[k] = permille;
    const uint32_t d = (uint32_t)permille * PWM_MAX / 1000u;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)k, d);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)k);
}

esp_err_t relays_init(const board_t *b, uint16_t hold_permille)
{
    s_b = b;
    s_cfg = b->relay_cfg;
    s_cfg.hold_permille = hold_permille;

    const ledc_timer_config_t t = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = PWM_BITS,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&t));
    for (int k = 0; k < SWS_OUTLETS; k++) {
        relay_drive_init(&s_rd[k]);
        const ledc_channel_config_t c = {
            .gpio_num = b->relay_pin[k],
            .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel = (ledc_channel_t)k,
            .timer_sel = LEDC_TIMER_0,
            .duty = 0,
            .hpoint = 0,
        };
        ESP_ERROR_CHECK(ledc_channel_config(&c));
        s_duty[k] = 0;
    }

    s_zc = xSemaphoreCreateBinary();
    if (b->zero_cross != GPIO_NUM_NC && s_zc != NULL) {
        const gpio_config_t io = {
            .pin_bit_mask = 1ULL << b->zero_cross,
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_POSEDGE,
        };
        gpio_config(&io);
        const esp_err_t err = gpio_install_isr_service(0);
        if (err == ESP_OK || err == ESP_ERR_INVALID_STATE) {
            gpio_isr_handler_add(b->zero_cross, zc_isr, NULL);
        }
    }
    ESP_LOGI(TAG, "relays on GPIO %d/%d, hold %u permille, zero-cross %s", b->relay_pin[0],
             b->relay_pin[1], s_cfg.hold_permille, b->zero_cross != GPIO_NUM_NC ? "on" : "off");
    return ESP_OK;
}

void relays_set_hold(uint16_t permille)
{
    if (permille < 300) {
        permille = 300; /* below this most 5 V coils drop out */
    }
    if (permille > 1000) {
        permille = 1000;
    }
    s_cfg.hold_permille = permille;
    ESP_LOGI(TAG, "holding duty now %u permille", permille);
}

/* Wait for the next zero crossing, then for the part of the half-cycle that
 * makes the contacts land at the following zero. Falls back to closing now. */
static void wait_for_close_point(void)
{
    if (s_b->zero_cross == GPIO_NUM_NC || s_zc == NULL) {
        return;
    }
    xSemaphoreTake(s_zc, 0); /* discard a stale edge */
    if (xSemaphoreTake(s_zc, pdMS_TO_TICKS(ZC_WAIT_MS)) == pdTRUE) {
        s_zc_seen = true;
        esp_rom_delay_us(relay_zc_delay_us(s_cfg.operate_us, HALF_PERIOD_US));
    } else if (!s_zc_missing_logged) {
        s_zc_missing_logged = true;
        ESP_LOGW(TAG, "no zero-cross signal; closing relays without alignment");
    }
}

void relays_apply(const bool want[SWS_OUTLETS], uint64_t now_ms)
{
    for (int k = 0; k < SWS_OUTLETS; k++) {
        const bool was_closed = s_rd[k].closed;
        if (want[k] && !was_closed) {
            wait_for_close_point();
        }
        set_duty(k, relay_drive_duty(&s_rd[k], &s_cfg, want[k], now_ms));
    }
}
