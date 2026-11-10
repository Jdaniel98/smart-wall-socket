/*
 * Smart Wall Socket firmware, Proto 0.
 *
 * Start-up order matters: protection and relays come up first and run
 * without any network. Matter, MQTT and the console start afterwards.
 */
#include <stdio.h>

#include "app.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_system.h"
#include "sdkconfig.h"

static const char *TAG = "main";
static char s_device_id[20];

const char *app_device_id(void)
{
    return s_device_id;
}

#if CONFIG_SWS_MATTER
void matter_factory_reset(void);
#else
bool matter_enabled(void)
{
    return false;
}
esp_err_t matter_start(void)
{
    return ESP_OK;
}
void matter_report_onoff(int outlet, bool on)
{
}
#endif

void app_factory_reset(void)
{
    ESP_LOGW(TAG, "factory reset: forgetting Wi-Fi and pairing; calibration and energy are kept");
    storage_erase_app();
#if CONFIG_SWS_MATTER
    matter_factory_reset(); /* erases Matter fabrics and restarts */
#else
    esp_restart();
#endif
}

void app_main(void)
{
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(s_device_id, sizeof(s_device_id), "sws-%02x%02x%02x%02x%02x%02x", mac[0], mac[1],
             mac[2], mac[3], mac[4], mac[5]);

    const board_t *b = board_get();
    ESP_LOGI(TAG, "Smart Wall Socket %s on %s, device %s", SWS_FW_VERSION, b->name, s_device_id);

    ESP_ERROR_CHECK(storage_init());
    status_led_init(b);
    ESP_ERROR_CHECK(control_start()); /* protection runs from here on */
    inputs_init(b, storage_get_u32("touch", b->touch_enabled_by_default) != 0);

    if (matter_start() != ESP_OK) {
        ESP_LOGE(TAG, "Matter failed to start; the socket still works locally");
    }
    if (net_start(s_device_id) != ESP_OK) {
        ESP_LOGE(TAG, "network failed to start; the socket still works locally");
    }
    console_start();
}
