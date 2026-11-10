/*
 * NVS storage.
 *  - "nvs" partition, namespace "sws": calibration, limits, schedules,
 *    relay intent, MQTT and Wi-Fi settings, device certificates.
 *  - "nvs_hb" partition: the once-a-minute heartbeat (alive time + energy
 *    counters). Kept apart so its frequent writes wear their own sectors.
 *  - "fctry" partition (read-only here): device identity written by
 *    tools/provision.py. Reads check "nvs" first, so a console setting
 *    overrides the factory value.
 */
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "storage";
#define NS "sws"
#define HB_PART "nvs_hb"
#define HB_NS "hb"
#define FCTRY_PART "fctry"

static nvs_handle_t s_nvs;
static nvs_handle_t s_fctry;
static bool s_fctry_ok;
static nvs_handle_t s_hb;
static bool s_hb_ok;

esp_err_t storage_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS layout changed; erasing");
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    ESP_ERROR_CHECK(nvs_open(NS, NVS_READWRITE, &s_nvs));

    err = nvs_flash_init_partition(HB_PART);
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase_partition(HB_PART);
        err = nvs_flash_init_partition(HB_PART);
    }
    if (err == ESP_OK) {
        s_hb_ok = nvs_open_from_partition(HB_PART, HB_NS, NVS_READWRITE, &s_hb) == ESP_OK;
    }
    if (nvs_flash_init_partition(FCTRY_PART) == ESP_OK) {
        s_fctry_ok = nvs_open_from_partition(FCTRY_PART, NS, NVS_READONLY, &s_fctry) == ESP_OK;
    }
    if (!s_fctry_ok) {
        ESP_LOGI(TAG, "no factory identity partition data (run tools/provision.py)");
    }
    if (!s_hb_ok) {
        ESP_LOGE(TAG, "heartbeat partition unavailable (%s): outage log and energy persistence off",
                 esp_err_to_name(err));
    }
    return ESP_OK;
}

uint32_t storage_get_u32(const char *key, uint32_t def)
{
    uint32_t v;
    return nvs_get_u32(s_nvs, key, &v) == ESP_OK ? v : def;
}

void storage_set_u32(const char *key, uint32_t v)
{
    if (nvs_set_u32(s_nvs, key, v) == ESP_OK) {
        nvs_commit(s_nvs);
    }
}

bool storage_get_str(const char *key, char *buf, size_t len)
{
    size_t n = len;
    if (nvs_get_str(s_nvs, key, buf, &n) == ESP_OK) {
        return true;
    }
    n = len;
    return s_fctry_ok && nvs_get_str(s_fctry, key, buf, &n) == ESP_OK;
}

void storage_set_str(const char *key, const char *v)
{
    if (nvs_set_str(s_nvs, key, v) == ESP_OK) {
        nvs_commit(s_nvs);
    }
}

static char *blob_str_from(nvs_handle_t h, const char *key)
{
    size_t n = 0;
    /* Certificates may be stored as string or blob entries. */
    if (nvs_get_str(h, key, NULL, &n) == ESP_OK && n > 0) {
        char *s = malloc(n);
        if (s != NULL && nvs_get_str(h, key, s, &n) == ESP_OK) {
            return s;
        }
        free(s);
        return NULL;
    }
    if (nvs_get_blob(h, key, NULL, &n) != ESP_OK || n == 0) {
        return NULL;
    }
    char *s = malloc(n + 1);
    if (s == NULL) {
        return NULL;
    }
    if (nvs_get_blob(h, key, s, &n) != ESP_OK) {
        free(s);
        return NULL;
    }
    s[n] = '\0';
    return s;
}

char *storage_get_blob_str(const char *key)
{
    char *s = blob_str_from(s_nvs, key);
    if (s == NULL && s_fctry_ok) {
        s = blob_str_from(s_fctry, key);
    }
    return s;
}

bool storage_get_blob(const char *key, void *buf, size_t len)
{
    size_t n = len;
    return nvs_get_blob(s_nvs, key, buf, &n) == ESP_OK && n == len;
}

void storage_set_blob(const char *key, const void *buf, size_t len)
{
    if (nvs_set_blob(s_nvs, key, buf, len) == ESP_OK) {
        nvs_commit(s_nvs);
    }
}

bool storage_load_hb(heartbeat_t *hb)
{
    if (!s_hb_ok) {
        return false;
    }
    size_t n = sizeof(*hb);
    return nvs_get_blob(s_hb, "hb", hb, &n) == ESP_OK && n == sizeof(*hb);
}

void storage_save_hb(const heartbeat_t *hb)
{
    if (s_hb_ok && nvs_set_blob(s_hb, "hb", hb, sizeof(*hb)) == ESP_OK) {
        nvs_commit(s_hb);
    }
}

void storage_erase_app(void)
{
    /* Network and pairing settings only: calibration and energy survive. */
    static const char *keys[] = {"wifi_ssid", "wifi_pass"};
    for (size_t i = 0; i < sizeof(keys) / sizeof(keys[0]); i++) {
        nvs_erase_key(s_nvs, keys[i]);
    }
    nvs_commit(s_nvs);
}
