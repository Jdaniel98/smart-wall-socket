/*
 * Matter: two On/Off Plug-in Unit endpoints, one per outlet, so the socket
 * works in Apple Home and Google Home. Matter carries the user's intent; the
 * control task still decides whether a relay may close (restore delay,
 * trips, locks). Metering over Matter (Electrical Power/Energy Measurement)
 * is the next increment; metering goes over MQTT for now.
 *
 * Development builds use Espressif's test attestation certificates, which
 * Apple Home and Google Home accept for uncertified test devices.
 */
#include "sdkconfig.h"

#if CONFIG_SWS_MATTER

#include <esp_log.h>
#include <esp_matter.h>

#include "app.h"

using namespace esp_matter;
using namespace esp_matter::attribute;
using namespace esp_matter::endpoint;
using namespace chip::app::Clusters;

static const char *TAG = "matter";

static uint16_t s_ep[SWS_OUTLETS];
static bool s_started;
static bool s_reporting; /* true while we write OnOff ourselves */

static esp_err_t attr_cb(attribute::callback_type_t type, uint16_t endpoint_id, uint32_t cluster_id,
                         uint32_t attribute_id, esp_matter_attr_val_t *val, void *priv)
{
    if (type != PRE_UPDATE || s_reporting || cluster_id != OnOff::Id ||
        attribute_id != OnOff::Attributes::OnOff::Id) {
        return ESP_OK;
    }
    for (int k = 0; k < SWS_OUTLETS; k++) {
        if (endpoint_id == s_ep[k]) {
            ctl_msg_t m = {};
            m.type = CTL_SET_DESIRED;
            m.src = SRC_MATTER;
            m.outlet = k;
            m.on = val->val.b;
            control_post(&m);
        }
    }
    return ESP_OK;
}

static esp_err_t identify_cb(identification::callback_type_t type, uint16_t endpoint_id,
                             uint8_t effect_id, uint8_t effect_variant, void *priv)
{
    ESP_LOGI(TAG, "identify endpoint %u", endpoint_id);
    return ESP_OK;
}

static void event_cb(const ChipDeviceEvent *event, intptr_t arg)
{
    switch (event->Type) {
    case chip::DeviceLayer::DeviceEventType::kCommissioningComplete:
        ESP_LOGI(TAG, "commissioning complete");
        break;
    case chip::DeviceLayer::DeviceEventType::kFailSafeTimerExpired:
        ESP_LOGW(TAG, "commissioning failed (fail-safe timer expired)");
        break;
    default:
        break;
    }
}

extern "C" bool matter_enabled(void)
{
    return true;
}

extern "C" esp_err_t matter_start(void)
{
    node::config_t node_cfg;
    node_t *node = node::create(&node_cfg, attr_cb, identify_cb);
    if (node == nullptr) {
        ESP_LOGE(TAG, "failed to create Matter node");
        return ESP_FAIL;
    }
    for (int k = 0; k < SWS_OUTLETS; k++) {
        on_off_plug_in_unit::config_t cfg;
        cfg.on_off.on_off = false;
        endpoint_t *ep = on_off_plug_in_unit::create(node, &cfg, ENDPOINT_FLAG_NONE, nullptr);
        if (ep == nullptr) {
            ESP_LOGE(TAG, "failed to create outlet %d endpoint", k);
            return ESP_FAIL;
        }
        s_ep[k] = endpoint::get_id(ep);
        ESP_LOGI(TAG, "outlet %d is Matter endpoint %u", k, s_ep[k]);
    }
    const esp_err_t err = esp_matter::start(event_cb);
    s_started = (err == ESP_OK);
    return err;
}

extern "C" bool matter_report_onoff(int outlet, bool on)
{
    if (!s_started || outlet < 0 || outlet >= SWS_OUTLETS) {
        return false;
    }
    esp_matter_attr_val_t v = esp_matter_bool(on);
    lock::ScopedChipStackLock guard(portMAX_DELAY);
    s_reporting = true;
    const esp_err_t err = attribute::update(s_ep[outlet], OnOff::Id, OnOff::Attributes::OnOff::Id, &v);
    s_reporting = false;
    return err == ESP_OK;
}

extern "C" void matter_factory_reset(void)
{
    esp_matter::factory_reset();
}

#endif
