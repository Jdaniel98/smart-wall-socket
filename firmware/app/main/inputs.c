/*
 * Buttons and touch inputs, polled every 10 ms.
 *
 * Proto 0 on-board button (stands in for the two touch zones):
 *   tap          toggle outlet 1 (index 0)
 *   double tap   toggle outlet 2 (index 1)
 *   hold 3 s     clear locks (over-current / over-temperature)
 *   hold 10 s    factory reset of network and Matter pairing
 *
 * Per-outlet touch inputs (EVT touch ICs, or Sonoff S1/S2 if enabled): a
 * press must last 150 ms to count, then it toggles that outlet.
 */
#include "app.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "inputs";

#define POLL_MS 10
#define DEBOUNCE_MS 30
#define TOUCH_MIN_MS 150
#define DOUBLE_TAP_GAP_MS 400
#define HOLD_RESET_MS 3000
#define HOLD_FACTORY_MS 10000

void app_factory_reset(void);

typedef struct {
    gpio_num_t pin;
    bool pressed;        /* debounced */
    uint32_t raw_ms;     /* time the raw level has been stable */
    bool raw_level;
    uint32_t held_ms;
} input_t;

static const board_t *s_b;
static input_t s_button;
static input_t s_touch[SWS_OUTLETS];
static bool s_touch_enabled;

static void post(ctl_type_t type, ctl_src_t src, int outlet)
{
    const ctl_msg_t m = {.type = type, .src = src, .outlet = outlet};
    control_post(&m);
}

static void setup_pin(input_t *in, gpio_num_t pin)
{
    in->pin = pin;
    if (pin == GPIO_NUM_NC) {
        return;
    }
    const gpio_config_t io = {
        .pin_bit_mask = 1ULL << pin,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io);
}

/* Returns the length of a completed press (ms) on release, else 0. */
static uint32_t poll_input(input_t *in)
{
    if (in->pin == GPIO_NUM_NC) {
        return 0;
    }
    const bool level = gpio_get_level(in->pin) == 0; /* active low */
    if (level != in->raw_level) {
        in->raw_level = level;
        in->raw_ms = 0;
    } else if (in->raw_ms < DEBOUNCE_MS) {
        in->raw_ms += POLL_MS;
    }
    if (in->raw_ms >= DEBOUNCE_MS && level != in->pressed) {
        in->pressed = level;
        if (!level) {
            const uint32_t held = in->held_ms;
            in->held_ms = 0;
            return held == 0 ? POLL_MS : held;
        }
    }
    if (in->pressed) {
        in->held_ms += POLL_MS;
    }
    return 0;
}

static void inputs_task(void *arg)
{
    uint32_t pending_tap_ms = 0; /* time since a single tap, 0 = none pending */
    bool hold_feedback = false;

    for (;;) {
        /* On-board button */
        const uint32_t press = poll_input(&s_button);
        if (s_button.pressed && s_button.held_ms >= HOLD_RESET_MS && !hold_feedback) {
            hold_feedback = true;
            ESP_LOGI(TAG, "button held 3 s: release now to clear locks, keep holding for factory reset");
        }
        if (press > 0) {
            hold_feedback = false;
            if (press >= HOLD_FACTORY_MS) {
                ESP_LOGW(TAG, "button held 10 s: factory reset");
                app_factory_reset();
            } else if (press >= HOLD_RESET_MS) {
                post(CTL_RESET_ALL, SRC_BUTTON, -1);
            } else if (pending_tap_ms > 0) {
                pending_tap_ms = 0;
                post(CTL_TOGGLE, SRC_BUTTON, 1); /* double tap */
            } else {
                pending_tap_ms = 1;
            }
        }
        if (pending_tap_ms > 0) {
            pending_tap_ms += POLL_MS;
            if (pending_tap_ms > DOUBLE_TAP_GAP_MS) {
                pending_tap_ms = 0;
                post(CTL_TOGGLE, SRC_BUTTON, 0);
            }
        }

        /* Per-outlet touch inputs */
        if (s_touch_enabled) {
            for (int k = 0; k < SWS_OUTLETS; k++) {
                const uint32_t t = poll_input(&s_touch[k]);
                if (t >= TOUCH_MIN_MS && t < HOLD_RESET_MS) {
                    post(CTL_TOGGLE, SRC_TOUCH, k);
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(POLL_MS));
    }
}

esp_err_t inputs_init(const board_t *b, bool touch_enabled)
{
    s_b = b;
    s_touch_enabled = touch_enabled;
    setup_pin(&s_button, b->button);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        setup_pin(&s_touch[k], touch_enabled ? b->touch[k] : GPIO_NUM_NC);
    }
    if (touch_enabled) {
        ESP_LOGW(TAG, "touch/switch inputs enabled on GPIO %d/%d", b->touch[0], b->touch[1]);
    }
    return xTaskCreate(inputs_task, "inputs", 3072, NULL, 5, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}
