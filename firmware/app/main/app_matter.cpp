/*
 * Matter: one endpoint per outlet, each carrying two device types:
 *
 *   On/Off Plug-in Unit (0x010A)  OnOff: the user's intent for the outlet
 *   Electrical Sensor   (0x0510)  Power Topology (tree), Electrical Power
 *                                 Measurement (W, V, A, PF) and Electrical
 *                                 Energy Measurement (cumulative kWh imported)
 *
 * This is the layout multi-outlet metering products use (one plug + sensor
 * per outlet endpoint), and Apple Home shows live watts only on outlet-type
 * accessories, so the sensor must sit on the plug's endpoint.
 *
 * Threading: the control task never touches the Matter stack. It copies
 * values into a small shared struct and schedules work on the Matter thread
 * (PlatformMgr().ScheduleWork), so a busy Matter stack can never stall
 * protection or trip the 2 s watchdog.
 *
 * Development builds use Espressif's test attestation certificates.
 */
#include "sdkconfig.h"

#if CONFIG_SWS_MATTER

#include <cmath>
#include <sys/time.h>

#include <esp_log.h>
#include <esp_matter.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>

#include <app/clusters/electrical-power-measurement-server/ElectricalPowerMeasurementDelegate.h>
#include <app/clusters/power-topology-server/PowerTopologyDelegate.h>
#include <app/reporting/reporting.h>
#include <data_model_provider/clusters/electrical_energy_measurement/integration.h>

#include "app.h"
#include "sws/proto.h"

using namespace esp_matter;
using namespace esp_matter::attribute;
using namespace esp_matter::endpoint;
using namespace chip::app::Clusters;
using chip::app::DataModel::Nullable;

static const char *TAG = "matter";

/* Seconds between 1970-01-01 and the Matter epoch, 2000-01-01. */
static constexpr int64_t kMatterEpochOffsetS = 946684800;
/* How often cumulative energy is pushed (it also emits an event each time). */
static constexpr int64_t kEnergyPeriodUs = 30 * 1000 * 1000;

/* ---------- accuracy we claim (Proto 0 target, to be confirmed by bench test T1) ---------- */

namespace EPM = chip::app::Clusters::ElectricalPowerMeasurement;
namespace EEM = chip::app::Clusters::ElectricalEnergyMeasurement;

static const EPM::Structs::MeasurementAccuracyRangeStruct::Type kPowerRange[] = {{
    .rangeMin = -100'000,     /* -100 W: noise around zero */
    .rangeMax = 4'000'000,    /* 4 kW */
    .percentMax = chip::MakeOptional(static_cast<chip::Percent100ths>(200)), /* 2% */
}};
static const EPM::Structs::MeasurementAccuracyRangeStruct::Type kVoltageRange[] = {{
    .rangeMin = 0,
    .rangeMax = 300'000,      /* 300 V */
    .percentMax = chip::MakeOptional(static_cast<chip::Percent100ths>(200)),
}};
static const EPM::Structs::MeasurementAccuracyRangeStruct::Type kCurrentRange[] = {{
    .rangeMin = 0,
    .rangeMax = 16'000,       /* 16 A */
    .percentMax = chip::MakeOptional(static_cast<chip::Percent100ths>(200)),
}};
static const EPM::Structs::MeasurementAccuracyRangeStruct::Type kPfRange[] = {{
    .rangeMin = -10'000,
    .rangeMax = 10'000,
    .percentMax = chip::MakeOptional(static_cast<chip::Percent100ths>(500)),
}};

static const EPM::Structs::MeasurementAccuracyStruct::Type kPowerAccuracy[] = {
    {
        .measurementType = EPM::MeasurementTypeEnum::kActivePower,
        .measured = true,
        .minMeasuredValue = -100'000,
        .maxMeasuredValue = 4'000'000,
        .accuracyRanges = chip::app::DataModel::List<const EPM::Structs::MeasurementAccuracyRangeStruct::Type>(kPowerRange),
    },
    {
        .measurementType = EPM::MeasurementTypeEnum::kRMSVoltage,
        .measured = true,
        .minMeasuredValue = 0,
        .maxMeasuredValue = 300'000,
        .accuracyRanges = chip::app::DataModel::List<const EPM::Structs::MeasurementAccuracyRangeStruct::Type>(kVoltageRange),
    },
    {
        .measurementType = EPM::MeasurementTypeEnum::kRMSCurrent,
        .measured = true,
        .minMeasuredValue = 0,
        .maxMeasuredValue = 16'000,
        .accuracyRanges = chip::app::DataModel::List<const EPM::Structs::MeasurementAccuracyRangeStruct::Type>(kCurrentRange),
    },
    {
        .measurementType = EPM::MeasurementTypeEnum::kPowerFactor,
        .measured = true,
        .minMeasuredValue = -10'000,
        .maxMeasuredValue = 10'000,
        .accuracyRanges = chip::app::DataModel::List<const EPM::Structs::MeasurementAccuracyRangeStruct::Type>(kPfRange),
    },
};

static const EEM::Structs::MeasurementAccuracyRangeStruct::Type kEnergyRange[] = {{
    .rangeMin = 0,
    .rangeMax = 1'000'000'000'000'000, /* far beyond a socket's lifetime */
    .percentMax = chip::MakeOptional(static_cast<chip::Percent100ths>(200)),
}};
static const EEM::Structs::MeasurementAccuracyStruct::Type kEnergyAccuracy = {
    .measurementType = EEM::MeasurementTypeEnum::kElectricalEnergy,
    .measured = true,
    .minMeasuredValue = 0,
    .maxMeasuredValue = 1'000'000'000'000'000,
    .accuracyRanges = chip::app::DataModel::List<const EEM::Structs::MeasurementAccuracyRangeStruct::Type>(kEnergyRange),
};

/* ---------- delegates ---------- */

/* Tree topology: each outlet endpoint measures itself (and has no children),
 * so there are no endpoint lists to provide. */
class OutletTopology : public PowerTopology::Delegate {
public:
    CHIP_ERROR GetAvailableEndpointAtIndex(size_t, chip::EndpointId &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }
    CHIP_ERROR GetActiveEndpointAtIndex(size_t, chip::EndpointId &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }
};

/* Holds the latest readings in Matter units and marks attributes dirty only
 * when they move enough to matter, so subscribers are not flooded. */
class OutletPower : public EPM::Delegate {
public:
    EPM::PowerModeEnum GetPowerMode() override { return EPM::PowerModeEnum::kAc; }
    uint8_t GetNumberOfMeasurementTypes() override { return MATTER_ARRAY_SIZE(kPowerAccuracy); }

    CHIP_ERROR StartAccuracyRead() override { return CHIP_NO_ERROR; }
    CHIP_ERROR GetAccuracyByIndex(uint8_t i, EPM::Structs::MeasurementAccuracyStruct::Type &out) override
    {
        if (i >= MATTER_ARRAY_SIZE(kPowerAccuracy)) {
            return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
        }
        out = kPowerAccuracy[i];
        return CHIP_NO_ERROR;
    }
    CHIP_ERROR EndAccuracyRead() override { return CHIP_NO_ERROR; }

    CHIP_ERROR StartRangesRead() override { return CHIP_NO_ERROR; }
    CHIP_ERROR GetRangeByIndex(uint8_t, EPM::Structs::MeasurementRangeStruct::Type &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }
    CHIP_ERROR EndRangesRead() override { return CHIP_NO_ERROR; }

    CHIP_ERROR StartHarmonicCurrentsRead() override { return CHIP_NO_ERROR; }
    CHIP_ERROR GetHarmonicCurrentsByIndex(uint8_t, EPM::Structs::HarmonicMeasurementStruct::Type &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }
    CHIP_ERROR EndHarmonicCurrentsRead() override { return CHIP_NO_ERROR; }

    CHIP_ERROR StartHarmonicPhasesRead() override { return CHIP_NO_ERROR; }
    CHIP_ERROR GetHarmonicPhasesByIndex(uint8_t, EPM::Structs::HarmonicMeasurementStruct::Type &) override
    {
        return CHIP_ERROR_PROVIDER_LIST_EXHAUSTED;
    }
    CHIP_ERROR EndHarmonicPhasesRead() override { return CHIP_NO_ERROR; }

    Nullable<int64_t> GetVoltage() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetActiveCurrent() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetReactiveCurrent() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetApparentCurrent() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetActivePower() override { return mPower.now; }
    Nullable<int64_t> GetReactivePower() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetApparentPower() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetRMSVoltage() override { return mVoltage.now; }
    Nullable<int64_t> GetRMSCurrent() override { return mCurrent.now; }
    Nullable<int64_t> GetRMSPower() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetFrequency() override { return chip::app::DataModel::NullNullable; }
    Nullable<int64_t> GetPowerFactor() override { return mPf.now; }
    Nullable<int64_t> GetNeutralCurrent() override { return chip::app::DataModel::NullNullable; }

    /* Called on the Matter thread. Units: mW, mV, mA, PF in 1/100 %. */
    void Update(bool valid, float v, float i, float p)
    {
        if (!valid) {
            Set(mPower, Nullable<int64_t>(), 0, 0, EPM::Attributes::ActivePower::Id);
            Set(mVoltage, Nullable<int64_t>(), 0, 0, EPM::Attributes::RMSVoltage::Id);
            Set(mCurrent, Nullable<int64_t>(), 0, 0, EPM::Attributes::RMSCurrent::Id);
            Set(mPf, Nullable<int64_t>(), 0, 0, EPM::Attributes::PowerFactor::Id);
            return;
        }
        const float pf = power_factor(p, v, i);
        /* Report when a value moves by 2%, or by an absolute floor near zero. */
        Set(mPower, Nullable<int64_t>(llroundf(p * 1000.0f)), 500, 200, EPM::Attributes::ActivePower::Id);
        Set(mVoltage, Nullable<int64_t>(llroundf(v * 1000.0f)), 500, 0, EPM::Attributes::RMSVoltage::Id);
        Set(mCurrent, Nullable<int64_t>(llroundf(i * 1000.0f)), 10, 200, EPM::Attributes::RMSCurrent::Id);
        Set(mPf, pf < 0.0f ? Nullable<int64_t>() : Nullable<int64_t>(llroundf(pf * 10000.0f)), 100, 0,
            EPM::Attributes::PowerFactor::Id);
    }

private:
    struct Value {
        Nullable<int64_t> now;
        Nullable<int64_t> reported;
    };

    /* abs_step: absolute change that triggers a report; pct100: relative
     * change in 1/100 % (0 = absolute only). */
    void Set(Value &v, Nullable<int64_t> next, int64_t abs_step, int64_t pct100, chip::AttributeId attr)
    {
        v.now = next;
        bool report;
        if (next.IsNull() || v.reported.IsNull()) {
            report = next.IsNull() != v.reported.IsNull();
        } else {
            const int64_t a = next.Value(), b = v.reported.Value();
            const int64_t diff = a > b ? a - b : b - a;
            const int64_t base = b < 0 ? -b : b;
            const int64_t rel = pct100 > 0 ? base * pct100 / 10000 : 0;
            report = diff >= abs_step && (pct100 == 0 || diff >= rel);
        }
        if (report) {
            v.reported = next;
            MatterReportingAttributeChangeCallback(mEndpointId, EPM::Id, attr);
        }
    }

    Value mPower, mVoltage, mCurrent, mPf;
};

/* ---------- state shared with the control task ---------- */

typedef struct {
    bool valid;
    float v;
    float i[SWS_OUTLETS];
    float p[SWS_OUTLETS];
    double wh[SWS_OUTLETS];
} meter_snapshot_t;

static uint16_t s_ep[SWS_OUTLETS];
static OutletTopology s_topology[SWS_OUTLETS];
static OutletPower s_power[SWS_OUTLETS];
static volatile bool s_started;
static bool s_reporting; /* only touched on the Matter thread */

static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static meter_snapshot_t s_meter;
static bool s_meter_work_pending;
static bool s_onoff_want[SWS_OUTLETS];
static bool s_onoff_dirty[SWS_OUTLETS];
static bool s_onoff_work_pending;

static bool s_energy_accuracy_set[SWS_OUTLETS];
static int64_t s_last_energy_us[SWS_OUTLETS];

/* ---------- Matter-thread work ---------- */

static void push_energy(int k, double wh, int64_t now_us)
{
    const chip::EndpointId ep = s_ep[k];
    if (!s_energy_accuracy_set[k] && EEM::GetClusterInstance(ep) != nullptr) {
        s_energy_accuracy_set[k] = EEM::SetMeasurementAccuracy(ep, kEnergyAccuracy) == CHIP_NO_ERROR;
    }
    if (s_last_energy_us[k] != 0 && now_us - s_last_energy_us[k] < kEnergyPeriodUs) {
        return;
    }
    s_last_energy_us[k] = now_us;

    EEM::Structs::EnergyMeasurementStruct::Type m;
    m.energy = static_cast<int64_t>(llround(wh * 1000.0)); /* mWh */
    m.endSystime.SetValue(static_cast<uint64_t>(now_us / 1000));
    if (net_time_synced()) {
        struct timeval tv;
        gettimeofday(&tv, nullptr);
        if (tv.tv_sec > kMatterEpochOffsetS) {
            m.endTimestamp.SetValue(static_cast<uint32_t>(tv.tv_sec - kMatterEpochOffsetS));
        }
    }
    EEM::NotifyCumulativeEnergyMeasured(ep, Nullable<EEM::Structs::EnergyMeasurementStruct::Type>(m),
                                        chip::app::DataModel::NullNullable);
}

static void meter_work(intptr_t)
{
    meter_snapshot_t snap;
    portENTER_CRITICAL(&s_mux);
    snap = s_meter;
    s_meter_work_pending = false;
    portEXIT_CRITICAL(&s_mux);

    const int64_t now_us = esp_timer_get_time();
    for (int k = 0; k < SWS_OUTLETS; k++) {
        s_power[k].Update(snap.valid, snap.v, snap.i[k], snap.p[k]);
        push_energy(k, snap.wh[k], now_us);
    }
}

static void onoff_work(intptr_t)
{
    bool want[SWS_OUTLETS], dirty[SWS_OUTLETS];
    portENTER_CRITICAL(&s_mux);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        want[k] = s_onoff_want[k];
        dirty[k] = s_onoff_dirty[k];
        s_onoff_dirty[k] = false;
    }
    s_onoff_work_pending = false;
    portEXIT_CRITICAL(&s_mux);

    for (int k = 0; k < SWS_OUTLETS; k++) {
        if (!dirty[k]) {
            continue;
        }
        esp_matter_attr_val_t v = esp_matter_bool(want[k]);
        s_reporting = true;
        const esp_err_t err = attribute::update(s_ep[k], OnOff::Id, OnOff::Attributes::OnOff::Id, &v);
        s_reporting = false;
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "OnOff update for outlet %d failed: %s", k, esp_err_to_name(err));
        }
    }
}

/* ---------- callbacks ---------- */

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

/* ---------- endpoint construction ---------- */

static esp_err_t add_metering(endpoint_t *ep, int k)
{
    electrical_sensor::config_t cfg;
    cfg.power_topology.feature_flags = cluster::power_topology::feature::tree_topology::get_id();
    cfg.power_topology.delegate = &s_topology[k];

    auto &epm = cfg.with_electrical_power_measurement();
    epm.feature_flags = cluster::electrical_power_measurement::feature::alternating_current::get_id();
    epm.power_mode = static_cast<uint8_t>(EPM::PowerModeEnum::kAc);
    epm.number_of_measurement_types = MATTER_ARRAY_SIZE(kPowerAccuracy);
    epm.delegate = &s_power[k];

    auto &eem = cfg.with_electrical_energy_measurement();
    eem.feature_flags = cluster::electrical_energy_measurement::feature::imported_energy::get_id() |
                        cluster::electrical_energy_measurement::feature::cumulative_energy::get_id();

    esp_err_t err = electrical_sensor::add(ep, &cfg);
    if (err != ESP_OK) {
        return err;
    }
    /* Optional EPM attributes: the server enables those that exist here. */
    cluster_t *pc = cluster::get(ep, EPM::Id);
    if (pc == nullptr) {
        return ESP_FAIL;
    }
    cluster::electrical_power_measurement::attribute::create_rms_voltage(pc, nullable<int64_t>());
    cluster::electrical_power_measurement::attribute::create_rms_current(pc, nullable<int64_t>());
    cluster::electrical_power_measurement::attribute::create_power_factor(pc, nullable<int64_t>());
    return ESP_OK;
}

/* ---------- C interface ---------- */

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
        if (add_metering(ep, k) != ESP_OK) {
            /* The outlet still works as a plain plug. */
            ESP_LOGE(TAG, "outlet %d: metering clusters not added", k);
        }
        ESP_LOGI(TAG, "outlet %d is Matter endpoint %u (plug + electrical sensor)", k, s_ep[k]);
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
    bool schedule;
    portENTER_CRITICAL(&s_mux);
    s_onoff_want[outlet] = on;
    s_onoff_dirty[outlet] = true;
    schedule = !s_onoff_work_pending;
    s_onoff_work_pending = true;
    portEXIT_CRITICAL(&s_mux);
    if (schedule && chip::DeviceLayer::PlatformMgr().ScheduleWork(onoff_work, 0) != CHIP_NO_ERROR) {
        portENTER_CRITICAL(&s_mux);
        s_onoff_work_pending = false;
        s_onoff_dirty[outlet] = false;
        portEXIT_CRITICAL(&s_mux);
        return false; /* control task retries next tick */
    }
    return true;
}

extern "C" void matter_report_meter(const sws_meas_t *m, bool meter_ok, const double wh[SWS_OUTLETS])
{
    if (!s_started) {
        return;
    }
    bool schedule;
    portENTER_CRITICAL(&s_mux);
    s_meter.valid = meter_ok && m->valid;
    s_meter.v = m->v_rms;
    for (int k = 0; k < SWS_OUTLETS; k++) {
        s_meter.i[k] = m->i_rms[k];
        s_meter.p[k] = m->p_w[k];
        s_meter.wh[k] = wh[k];
    }
    schedule = !s_meter_work_pending;
    s_meter_work_pending = true;
    portEXIT_CRITICAL(&s_mux);
    if (schedule && chip::DeviceLayer::PlatformMgr().ScheduleWork(meter_work, 0) != CHIP_NO_ERROR) {
        portENTER_CRITICAL(&s_mux);
        s_meter_work_pending = false;
        portEXIT_CRITICAL(&s_mux);
    }
}

extern "C" void matter_factory_reset(void)
{
    esp_matter::factory_reset();
}

#endif
