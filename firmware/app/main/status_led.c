/* One status LED. Patterns: solid = online, blip = offline, slow blink =
 * waiting to restore, fast blink = tripped or locked. */
#include "app.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define STEP_MS 50

static const board_t *s_b;
static volatile led_pattern_t s_pattern = LED_BLIP;

static void led_write(bool on)
{
    gpio_set_level(s_b->status_led, (on ^ s_b->status_led_active_low) ? 1 : 0);
}

static void led_task(void *arg)
{
    uint32_t t = 0;
    for (;;) {
        bool on;
        switch (s_pattern) {
        case LED_ON: on = true; break;
        case LED_BLINK_SLOW: on = (t % 1000) < 500; break;
        case LED_BLINK_FAST: on = (t % 250) < 125; break;
        case LED_BLIP: on = (t % 2000) < 100; break;
        case LED_OFF:
        default: on = false; break;
        }
        led_write(on);
        t += STEP_MS;
        vTaskDelay(pdMS_TO_TICKS(STEP_MS));
    }
}

esp_err_t status_led_init(const board_t *b)
{
    s_b = b;
    if (b->status_led == GPIO_NUM_NC) {
        return ESP_OK;
    }
    gpio_reset_pin(b->status_led);
    gpio_set_direction(b->status_led, GPIO_MODE_OUTPUT);
    led_write(false);
    return xTaskCreate(led_task, "led", 2048, NULL, 2, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}

void status_led_set(led_pattern_t p)
{
    s_pattern = p;
}
