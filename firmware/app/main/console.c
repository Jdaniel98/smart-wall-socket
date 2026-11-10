/*
 * Serial console for bench work. Connect ONLY through an isolated USB-UART
 * adapter: on a non-isolated board the UART pins are at mains potential.
 *
 *   status                         readings, states, limits, calibration
 *   relay <0|1> <on|off>           switch an outlet
 *   reset [0|1]                    clear a lock (all outlets if omitted)
 *   cal <v|i0|i1|p0|p1> <ref>      calibrate against a reference meter
 *   hold <300-1000>                relay holding duty, permille (1000 = off)
 *   bench <on|off>                 allow calibration over MQTT
 *   touch <on|off>                 enable per-outlet inputs (reboot to apply)
 *   mqtt <uri>                     e.g. mqtts://broker.example.com:8883
 *   wifi <ssid> <password>         non-Matter builds only
 *   id                             print the device id
 *   reboot | factory
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app.h"
#include "esp_console.h"
#include "esp_log.h"
#include "esp_system.h"

void app_factory_reset(void);

static int parse_outlet(const char *s)
{
    if (strcmp(s, "0") == 0) return 0;
    if (strcmp(s, "1") == 0) return 1;
    return -1;
}

static int cmd_status(int argc, char **argv)
{
    control_snapshot_t s;
    control_snapshot(&s);
    printf("device %s, firmware %s, board %s\n", app_device_id(), SWS_FW_VERSION, board_get()->name);
    printf("meter %s  V %.1f  temp %.1f C (%s)  bad frames %lu  energy rejects %lu\n",
           s.meter_ok ? "ok" : "FAULT", s.meas.v_rms, s.meas.temp_c, board_get()->temp_source,
           (unsigned long)s.bad_frames, (unsigned long)s.energy_rejects);
    for (int k = 0; k < SWS_OUTLETS; k++) {
        printf("outlet %d: %-7s (%s)  want %-3s relay %-3s  I %.3f A  P %.1f W  E %.1f Wh\n", k,
               prot_state_name(s.state[k]), prot_reason_name(s.reason[k]),
               s.desired[k] ? "on" : "off", s.relay[k] ? "on" : "off", s.meas.i_rms[k],
               s.meas.p_w[k], s.wh[k]);
        printf("  limits: %.0f-%.0f V (instant %.0f), trip %lu ms, restore %lu s, I %.1f A\n",
               s.cfg[k].v_low, s.cfg[k].v_high, s.cfg[k].v_instant_high,
               (unsigned long)s.cfg[k].trip_ms, (unsigned long)s.cfg[k].restore_delay_s,
               s.cfg[k].i_limit);
    }
    printf("gains: v %.5f  i %.5f/%.5f  p %.5f/%.5f  hold %u permille  network %s  clock %s\n",
           s.cal.gain_v, s.cal.gain_i[0], s.cal.gain_i[1], s.cal.gain_p[0], s.cal.gain_p[1],
           s.hold_permille, net_connected() ? "online" : "offline",
           net_time_synced() ? "set" : "not set");
    return 0;
}

static int cmd_relay(int argc, char **argv)
{
    if (argc != 3 || parse_outlet(argv[1]) < 0) {
        printf("usage: relay <0|1> <on|off>\n");
        return 1;
    }
    const ctl_msg_t m = {.type = CTL_SET_DESIRED, .src = SRC_CONSOLE, .outlet = parse_outlet(argv[1]),
                         .on = strcmp(argv[2], "on") == 0};
    control_post(&m);
    return 0;
}

static int cmd_reset(int argc, char **argv)
{
    ctl_msg_t m = {.type = CTL_RESET_ALL, .src = SRC_CONSOLE};
    if (argc == 2) {
        m.type = CTL_RESET;
        m.outlet = parse_outlet(argv[1]);
        if (m.outlet < 0) {
            printf("usage: reset [0|1]\n");
            return 1;
        }
    }
    control_post(&m);
    return 0;
}

static int cmd_cal(int argc, char **argv)
{
    static const char *chans[] = {"v", "i0", "i1", "p0", "p1"};
    if (argc != 3) {
        printf("usage: cal <v|i0|i1|p0|p1> <reference value>\n"
               "  hold a steady load for at least 10 s first; uses the last 10 s average\n");
        return 1;
    }
    for (int i = 0; i < 5; i++) {
        if (strcmp(argv[1], chans[i]) == 0) {
            const ctl_msg_t m = {.type = CTL_CAL_LOCAL, .src = SRC_CONSOLE, .channel = i,
                                 .value = strtof(argv[2], NULL)};
            control_post(&m);
            return 0;
        }
    }
    printf("unknown channel\n");
    return 1;
}

static int cmd_hold(int argc, char **argv)
{
    if (argc != 2) {
        printf("usage: hold <300-1000>\n");
        return 1;
    }
    const long v = strtol(argv[1], NULL, 10);
    if (v < 300 || v > 1000) {
        printf("holding duty must be 300-1000 permille\n");
        return 1;
    }
    const ctl_msg_t m = {.type = CTL_SET_HOLD, .src = SRC_CONSOLE, .value = (float)v};
    control_post(&m);
    return 0;
}

static int cmd_flag(int argc, char **argv, const char *key, const char *name)
{
    if (argc != 2 || (strcmp(argv[1], "on") != 0 && strcmp(argv[1], "off") != 0)) {
        printf("usage: %s <on|off>\n", name);
        return 1;
    }
    storage_set_u32(key, strcmp(argv[1], "on") == 0);
    printf("%s %s\n", name, argv[1]);
    return 0;
}

static int cmd_bench(int argc, char **argv)
{
    return cmd_flag(argc, argv, "bench", "bench");
}

static int cmd_touch(int argc, char **argv)
{
    printf("WARNING: on Proto 0 the S1/S2 terminals are at mains potential.\n");
    const int r = cmd_flag(argc, argv, "touch", "touch");
    if (r == 0) {
        printf("reboot to apply\n");
    }
    return r;
}

static int cmd_mqtt(int argc, char **argv)
{
    if (argc != 2) {
        printf("usage: mqtt <uri>   (certificates go in with tools/provision.py)\n");
        return 1;
    }
    storage_set_str("mqtt_uri", argv[1]);
    printf("saved; reboot to connect\n");
    return 0;
}

static int cmd_wifi(int argc, char **argv)
{
    if (matter_enabled()) {
        printf("Matter build: Wi-Fi is set when you add the socket in Apple Home or Google Home\n");
        return 1;
    }
    if (argc != 3) {
        printf("usage: wifi <ssid> <password>\n");
        return 1;
    }
    storage_set_str("wifi_ssid", argv[1]);
    storage_set_str("wifi_pass", argv[2]);
    printf("saved; reboot to connect\n");
    return 0;
}

static int cmd_id(int argc, char **argv)
{
    printf("%s\n", app_device_id());
    return 0;
}

static int cmd_reboot(int argc, char **argv)
{
    esp_restart();
    return 0;
}

static int cmd_factory(int argc, char **argv)
{
    app_factory_reset();
    return 0;
}

esp_err_t console_start(void)
{
    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t rc = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    rc.prompt = "sws>";
    rc.max_cmdline_length = 256;
    esp_console_dev_uart_config_t uc = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    esp_err_t err = esp_console_new_repl_uart(&uc, &rc, &repl);
    if (err != ESP_OK) {
        return err;
    }

    const esp_console_cmd_t cmds[] = {
        {.command = "status", .help = "Readings, states, limits and calibration", .func = cmd_status},
        {.command = "relay", .help = "relay <0|1> <on|off>", .func = cmd_relay},
        {.command = "reset", .help = "reset [0|1]: clear a lock", .func = cmd_reset},
        {.command = "cal", .help = "cal <v|i0|i1|p0|p1> <reference>", .func = cmd_cal},
        {.command = "hold", .help = "hold <300-1000>: relay holding duty", .func = cmd_hold},
        {.command = "bench", .help = "bench <on|off>: allow calibration over MQTT", .func = cmd_bench},
        {.command = "touch", .help = "touch <on|off>: per-outlet inputs", .func = cmd_touch},
        {.command = "mqtt", .help = "mqtt <uri>", .func = cmd_mqtt},
        {.command = "wifi", .help = "wifi <ssid> <password> (non-Matter builds)", .func = cmd_wifi},
        {.command = "id", .help = "Print the device id", .func = cmd_id},
        {.command = "reboot", .help = "Restart", .func = cmd_reboot},
        {.command = "factory", .help = "Forget Wi-Fi and Matter pairing", .func = cmd_factory},
    };
    for (size_t i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++) {
        esp_console_cmd_register(&cmds[i]);
    }
    esp_console_register_help_command();
    return esp_console_start_repl(repl);
}
