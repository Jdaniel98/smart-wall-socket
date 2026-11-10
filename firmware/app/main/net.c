/*
 * Network: Wi-Fi (only when Matter is off; Matter provisions Wi-Fi itself),
 * SNTP, and MQTT over TLS with a per-device client certificate.
 *
 * Topics follow docs/protocol.md: dev/{id}/{telemetry,event,reported,ack,
 * status} from the device, dev/{id}/desired to it. The broker's ACL limits a
 * device to its own topics. A retained last-will on dev/{id}/status marks
 * the device offline.
 *
 * Settings in NVS (namespace "sws"): mqtt_uri, ca_pem, cert_pem, key_pem,
 * and wifi_ssid/wifi_pass for non-Matter builds. Without mqtt_uri the
 * device runs fully offline: protection, Matter and schedules still work.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_wifi.h"
#include "mqtt_client.h"

static const char *TAG = "net";

#define TOPIC_MAX 64
#define CMD_MAX_LEN 2048

static char s_id[24];
static char s_base[40];
static char s_status_topic[TOPIC_MAX];
static char s_desired_topic[TOPIC_MAX];
static esp_mqtt_client_handle_t s_mqtt;
static volatile bool s_connected;
static volatile bool s_time_synced;
static bool s_mqtt_started;
static bool s_sntp_started;
static char *s_ca, *s_cert, *s_key;

/* Reassembly for messages split across MQTT_EVENT_DATA events. */
static char *s_rx;
static size_t s_rx_len, s_rx_total;

bool net_connected(void)
{
    return s_connected;
}

bool net_time_synced(void)
{
    return s_time_synced;
}

int net_rssi(void)
{
    wifi_ap_record_t ap;
    return esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
}

bool net_publish(const char *subtopic, const char *payload, int qos, bool retain)
{
    if (!s_connected || s_mqtt == NULL) {
        return false;
    }
    char topic[TOPIC_MAX];
    snprintf(topic, sizeof(topic), "%s/%s", s_base, subtopic);
    /* enqueue never blocks the caller (the control task). */
    return esp_mqtt_client_enqueue(s_mqtt, topic, payload, 0, qos, retain, true) >= 0;
}

static void deliver_command(const char *data, size_t len)
{
    char *copy = malloc(len + 1);
    if (copy == NULL) {
        return;
    }
    memcpy(copy, data, len);
    copy[len] = '\0';
    const ctl_msg_t m = {.type = CTL_CLOUD_CMD, .src = SRC_CLOUD, .json = copy, .json_len = len};
    if (!control_post(&m)) {
        ESP_LOGW(TAG, "command queue full; command dropped (cloud will retry)");
    }
}

static void mqtt_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    esp_mqtt_event_handle_t e = data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED: {
        s_connected = true;
        ESP_LOGI(TAG, "MQTT connected as %s", s_id);
        esp_mqtt_client_publish(s_mqtt, s_status_topic, "online", 0, 1, 1);
        esp_mqtt_client_subscribe(s_mqtt, s_desired_topic, 1);
        const ctl_msg_t m = {.type = CTL_NET_UP, .src = SRC_CLOUD};
        control_post(&m);
        break;
    }
    case MQTT_EVENT_DISCONNECTED:
        s_connected = false;
        ESP_LOGW(TAG, "MQTT disconnected; client retries on its own");
        break;
    case MQTT_EVENT_DATA:
        if (e->current_data_offset == 0) {
            free(s_rx);
            s_rx = NULL;
            s_rx_len = 0;
            s_rx_total = (size_t)e->total_data_len;
            if (e->topic_len != (int)strlen(s_desired_topic) ||
                strncmp(e->topic, s_desired_topic, e->topic_len) != 0 ||
                s_rx_total > CMD_MAX_LEN) {
                s_rx_total = 0; /* not for us, or too large: ignore */
                break;
            }
            s_rx = malloc(s_rx_total);
        }
        if (s_rx == NULL || s_rx_total == 0 ||
            (size_t)e->current_data_offset + (size_t)e->data_len > s_rx_total) {
            break;
        }
        memcpy(s_rx + e->current_data_offset, e->data, (size_t)e->data_len);
        s_rx_len += (size_t)e->data_len;
        if (s_rx_len == s_rx_total) {
            deliver_command(s_rx, s_rx_len);
            free(s_rx);
            s_rx = NULL;
            s_rx_total = 0;
        }
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGW(TAG, "MQTT error");
        break;
    default:
        break;
    }
}

static void start_mqtt(void)
{
    if (s_mqtt_started) {
        return;
    }
    /* Static: the client may keep pointers into its config. */
    static char uri[128];
    if (!storage_get_str("mqtt_uri", uri, sizeof(uri))) {
        ESP_LOGW(TAG, "no mqtt_uri set: running without the cloud (see firmware/README.md)");
        s_mqtt_started = true;
        return;
    }
    s_ca = storage_get_blob_str("ca_pem");
    s_cert = storage_get_blob_str("cert_pem");
    s_key = storage_get_blob_str("key_pem");
    if (strncmp(uri, "mqtts://", 8) == 0 && (s_ca == NULL || s_cert == NULL || s_key == NULL)) {
        ESP_LOGE(TAG, "mqtts needs ca_pem, cert_pem and key_pem in NVS; cloud disabled");
        s_mqtt_started = true;
        return;
    }

    esp_mqtt_client_config_t cfg = {0};
    cfg.broker.address.uri = uri;
    cfg.broker.verification.certificate = s_ca;
    cfg.credentials.client_id = s_id;
    cfg.credentials.authentication.certificate = s_cert;
    cfg.credentials.authentication.key = s_key;
    cfg.session.keepalive = 30;
    cfg.session.last_will.topic = s_status_topic;
    cfg.session.last_will.msg = "offline";
    cfg.session.last_will.qos = 1;
    cfg.session.last_will.retain = 1;
    cfg.network.reconnect_timeout_ms = 10000;
    cfg.buffer.size = 2048;
    cfg.outbox.limit = 16 * 1024; /* cap RAM used by unsent messages */

    s_mqtt = esp_mqtt_client_init(&cfg);
    if (s_mqtt == NULL) {
        ESP_LOGE(TAG, "MQTT init failed");
        return;
    }
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_event, NULL);
    esp_mqtt_client_start(s_mqtt);
    s_mqtt_started = true;
}

static void time_sync_cb(struct timeval *tv)
{
    if (!s_time_synced) {
        ESP_LOGI(TAG, "clock set from SNTP");
    }
    s_time_synced = true;
}

static void start_sntp(void)
{
    if (s_sntp_started) {
        return;
    }
    esp_sntp_config_t c = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    c.sync_cb = time_sync_cb;
    if (esp_netif_sntp_init(&c) == ESP_OK) {
        s_sntp_started = true;
    }
}

static void ip_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ESP_LOGI(TAG, "got IP");
        start_sntp();
        start_mqtt();
    }
}

#if !CONFIG_SWS_MATTER
#include "esp_timer.h"

static int s_retry;
static esp_timer_handle_t s_reconnect_timer;

static void reconnect_cb(void *arg)
{
    esp_wifi_connect();
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (id == WIFI_EVENT_STA_DISCONNECTED) {
        /* Back off up to 30 s between attempts, without blocking the event loop. */
        const uint64_t delay_ms = s_retry < 6 ? (1u << s_retry) * 500u : 30000u;
        s_retry++;
        esp_timer_stop(s_reconnect_timer);
        esp_timer_start_once(s_reconnect_timer, delay_ms * 1000u);
    } else if (id == WIFI_EVENT_STA_CONNECTED) {
        s_retry = 0;
    }
}

static esp_err_t wifi_start(void)
{
    char ssid[33] = {0}, pass[65] = {0};
    if (!storage_get_str("wifi_ssid", ssid, sizeof(ssid))) {
        ESP_LOGW(TAG, "no Wi-Fi credentials: set them with the console command `wifi <ssid> <pass>`");
        return ESP_OK;
    }
    storage_get_str("wifi_pass", pass, sizeof(pass));
    ESP_ERROR_CHECK(esp_netif_init());
    esp_err_t err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    esp_netif_create_default_wifi_sta();
    const wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    const esp_timer_create_args_t targs = {.callback = reconnect_cb, .name = "wifi_retry"};
    ESP_ERROR_CHECK(esp_timer_create(&targs, &s_reconnect_timer));
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL);
    wifi_config_t wc = {0};
    strncpy((char *)wc.sta.ssid, ssid, sizeof(wc.sta.ssid));
    strncpy((char *)wc.sta.password, pass, sizeof(wc.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    return esp_wifi_start();
}
#endif

esp_err_t net_start(const char *device_id)
{
    strncpy(s_id, device_id, sizeof(s_id) - 1);
    snprintf(s_base, sizeof(s_base), "dev/%s", s_id);
    snprintf(s_status_topic, sizeof(s_status_topic), "%s/status", s_base);
    snprintf(s_desired_topic, sizeof(s_desired_topic), "%s/desired", s_base);

#if !CONFIG_SWS_MATTER
    ESP_ERROR_CHECK(wifi_start());
#endif
    /* With Matter, the Matter stack has created the default event loop and
     * brings Wi-Fi up after commissioning. */
    return esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, ip_event, NULL);
}
