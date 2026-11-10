/*
 * Shared declarations for the application layer.
 *
 * Threading: one control task owns all protection, energy, schedule and
 * relay state. Every other task (inputs, MQTT, Matter, console) talks to it
 * only by posting a ctl_msg_t to its queue, so there are no locks around the
 * safety logic.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "board/board.h"
#include "esp_err.h"
#include "sws/bl0939.h"
#include "sws/protection.h"
#include "sws/schedule.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SWS_FW_VERSION "0.1.0"

/* ---------- control task ---------- */

typedef enum {
    CTL_SET_DESIRED = 1, /* outlet, on */
    CTL_TOGGLE,          /* outlet */
    CTL_RESET,           /* outlet: clear a lock */
    CTL_RESET_ALL,       /* clear every lock that can be cleared */
    CTL_CLOUD_CMD,       /* json (heap, freed by control) */
    CTL_CAL_LOCAL,       /* channel (cal_channel_t), value = reference */
    CTL_SET_HOLD,        /* value = permille */
    CTL_NET_UP,          /* MQTT connected: flush queued events */
} ctl_type_t;

typedef enum {
    SRC_BUTTON = 0,
    SRC_TOUCH,
    SRC_MATTER,
    SRC_CLOUD,
    SRC_CONSOLE,
    SRC_SCHEDULE,
} ctl_src_t;

typedef struct {
    ctl_type_t type;
    ctl_src_t src;
    int outlet;
    bool on;
    int channel;
    float value;
    char *json;
    size_t json_len;
} ctl_msg_t;

typedef struct {
    sws_meas_t meas;
    prot_state_t state[SWS_OUTLETS];
    prot_reason_t reason[SWS_OUTLETS];
    bool desired[SWS_OUTLETS];
    bool relay[SWS_OUTLETS];
    double wh[SWS_OUTLETS];
    bool meter_ok;
    bl0939_cal_t cal;
    prot_cfg_t cfg[SWS_OUTLETS];
    uint16_t hold_permille;
    uint32_t energy_rejects;
    uint32_t bad_frames;
} control_snapshot_t;

esp_err_t control_start(void);
/* Safe from any task. Takes ownership of msg->json on success and failure. */
bool control_post(const ctl_msg_t *msg);
void control_snapshot(control_snapshot_t *out);

/* ---------- hardware ---------- */

esp_err_t metering_init(const board_t *b);
/* Request and read one full packet. Returns false on timeout or bad frame. */
bool metering_read(bl0939_raw_t *out, bl0939_status_t *status);

esp_err_t relays_init(const board_t *b, uint16_t hold_permille);
void relays_set_hold(uint16_t permille);
/* Called every control tick with the protection outputs. */
void relays_apply(const bool want[SWS_OUTLETS], uint64_t now_ms);

esp_err_t inputs_init(const board_t *b, bool touch_enabled);

typedef enum {
    LED_OFF = 0,
    LED_ON,
    LED_BLINK_SLOW,  /* waiting to restore */
    LED_BLINK_FAST,  /* tripped or locked */
    LED_BLIP,        /* running, not connected */
} led_pattern_t;

esp_err_t status_led_init(const board_t *b);
void status_led_set(led_pattern_t p);

/* ---------- storage (NVS) ---------- */

typedef struct {
    int64_t alive_utc;              /* last time the device was known powered */
    uint64_t pulses[SWS_OUTLETS];   /* energy counters */
} heartbeat_t;

esp_err_t storage_init(void);
uint32_t storage_get_u32(const char *key, uint32_t def);
void storage_set_u32(const char *key, uint32_t v);
bool storage_get_str(const char *key, char *buf, size_t len);
void storage_set_str(const char *key, const char *v);
/* Returns a heap copy (NUL-terminated) or NULL. Caller frees. */
char *storage_get_blob_str(const char *key);
bool storage_get_blob(const char *key, void *buf, size_t len);
void storage_set_blob(const char *key, const void *buf, size_t len);
bool storage_load_hb(heartbeat_t *hb);
void storage_save_hb(const heartbeat_t *hb);
void storage_erase_app(void);

/* ---------- network ---------- */

/* Starts MQTT once an IP address is up. Without Matter it also joins Wi-Fi. */
esp_err_t net_start(const char *device_id);
bool net_connected(void);
bool net_time_synced(void);
int net_rssi(void);
/* subtopic e.g. "telemetry" -> dev/{id}/telemetry. False if not connected. */
bool net_publish(const char *subtopic, const char *payload, int qos, bool retain);

/* ---------- Matter ---------- */

esp_err_t matter_start(void);
/* Returns false if Matter is not running yet. Never blocks. */
bool matter_report_onoff(int outlet, bool on);
/* Latest readings for the Electrical Power/Energy Measurement clusters.
 * Never blocks: values are handed to the Matter thread. */
void matter_report_meter(const sws_meas_t *m, bool meter_ok, const double wh[SWS_OUTLETS]);
bool matter_enabled(void);

/* ---------- console ---------- */

esp_err_t console_start(void);

/* ---------- misc ---------- */

const char *app_device_id(void);
uint64_t app_now_ms(void);

#ifdef __cplusplus
}
#endif
