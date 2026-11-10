# Device ↔ cloud protocol, v0

The contract between socket firmware and the cloud. Both sides build against this file; change it first, then the code.

Status: **v0, Proto 0**. Implemented by `firmware/components/sws_core/src/proto.c` and tested in `firmware/test/host/test_misc.c`.

## Transport

- MQTT 3.1.1 over TLS (port 8883), with a client certificate per device.
- Device id: `sws-` followed by the 12 hex digits of the Wi-Fi MAC, e.g. `sws-a1b2c3d4e5f6`. The certificate's CN is the device id.
- Keepalive 30 s. The device reconnects with backoff.
- All payloads are UTF-8 JSON objects. Numbers are SI units: V, A, W, Wh, °C.
- `ts` is Unix seconds (UTC). It is `0` until the device's clock is set by SNTP. Events queued before that are re-stamped when sent, if the clock is set by then.
- `seq` increases by one per message the device sends, and restarts at boot. Use it to spot gaps, not as an id.

### Broker rules (Mosquitto)

```conf
listener 8883
cafile   /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile  /etc/mosquitto/certs/server.key
require_certificate true
use_identity_as_username true
acl_file /etc/mosquitto/acl
```

```conf
# /etc/mosquitto/acl: a device may only use its own topics
pattern readwrite dev/%u/#
```

Cloud services connect with their own certificates and an ACL entry for `dev/#`.

## Topics

| Topic | Direction | QoS | Retained | When |
|---|---|---|---|---|
| `dev/{id}/telemetry` | device → cloud | 0 | no | every 10 s |
| `dev/{id}/event` | device → cloud | 1 | no | trips, restores, locks, relay changes, outages, boots, meter faults |
| `dev/{id}/reported` | device → cloud | 1 | **yes** | on any state or config change, and every 5 min |
| `dev/{id}/status` | device → cloud | 1 | **yes** | `online` on connect; `offline` as the last will |
| `dev/{id}/desired` | cloud → device | 1 | no | commands, each with an `id` |
| `dev/{id}/ack` | device → cloud | 1 | no | one per command `id` |
| `dev/{id}/ota` | cloud → device | 1 | no | reserved; Proto 0 updates over serial or Matter OTA |

`status` is an addition to the roadmap's topic list: the last-will message needs its own retained topic.

## Telemetry

10-second means of 1 Hz-ish readings (the BL0939 updates every 800 ms; the device reads every 500 ms). `wh` is a **cumulative** counter per outlet that never resets, so missed messages never lose energy: subtract consecutive values.

```json
{
  "ts": 1794312000, "seq": 812, "up": 86400,
  "v": 229.4,
  "o": [
    {"i": 8.712, "p": 1991.3, "pf": 1.0, "wh": 12345.6, "relay": true, "state": "normal"},
    {"i": 0.000, "p": 0.1, "pf": null, "wh": 873.2, "relay": false, "state": "waiting"}
  ],
  "temp": 41.2, "rssi": -61, "meter": "ok"
}
```

- `o[0]` is the left outlet, `o[1]` the right.
- `pf` is `null` below 0.02 A, where it means nothing.
- Any value can be `null` if the meter gave no valid readings in the window.
- `temp` is the board temperature source named in `reported.board` notes. On Proto 0 it is the BL0939 die, a rough proxy.
- `state` is one of `normal`, `tripped`, `waiting`, `locked`.

## Events

Every event has `ts`, `seq` and `type`.

| `type` | Extra fields | Meaning |
|---|---|---|
| `trip` | `outlet`, `state`, `reason`, `value` | Voltage left the limits; the outlet is off |
| `waiting` | `outlet`, `state`, `reason`, `value` | Voltage is back; the restore delay is running |
| `restore` | `outlet`, `state`, `reason`, `value` | Restore delay finished; the outlet may switch on |
| `lock` | `outlet`, `state`, `reason`, `value` | Over-current or over-temperature; needs a `reset` |
| `relay` | `outlet`, `on` | The relay actually opened or closed |
| `meter_fault` / `meter_ok` | none | No valid metering for 5 s / metering is back |
| `boot` | `fw`, `reset_reason` | `poweron`, `brownout`, `software`, `panic`, `watchdog`, `other` |
| `outage` | `start`, `end`, `duration_s`, `resolution_s` | Mains was off. `start` is the last heartbeat, so it is up to `resolution_s` (60 s) early |

`reason` is one of `none`, `undervoltage`, `overvoltage`, `surge`, `overcurrent`, `total_overcurrent`, `overtemp`. `value` is the reading that caused it: V for voltage reasons, A for current, °C for temperature.

```json
{"ts":1794312000,"seq":813,"type":"trip","outlet":0,"state":"tripped","reason":"undervoltage","value":171.20}
{"ts":1794312120,"seq":2,"type":"outage","start":1794308400,"end":1794312060,"duration_s":3660,"resolution_s":60}
```

The device keeps the last 32 events in RAM while offline and sends them on reconnect, oldest first.

## Reported state

Retained, so a newly connected app or service sees the device's true state at once.

```json
{
  "ts": 1794312000, "fw": "0.1.0", "board": "dualr3v2", "cfg_ver": 7,
  "time_synced": true, "meter": "ok",
  "o": [
    {"relay": true, "desired": true, "state": "normal", "reason": "none",
     "limits": {"v_low": 185.0, "v_high": 255.0, "v_instant_high": 275.0, "trip_ms": 2000,
                "restore_delay_s": 30, "i_limit": 10.00, "restore_policy": "last"}},
    {"relay": false, "desired": true, "state": "waiting", "reason": "none",
     "limits": {"v_low": 185.0, "v_high": 255.0, "v_instant_high": 275.0, "trip_ms": 2000,
                "restore_delay_s": 180, "i_limit": 10.00, "restore_policy": "last"}}
  ]
}
```

`desired` is what the user asked for; `relay` is what the socket is actually doing. They differ while waiting, tripped or locked. Apps show `relay` as the truth and `desired` as the intent. `cfg_ver` goes up by one on every limits or schedule change.

## Commands (`desired`)

Every command has an `id` (1–47 characters from `A–Z a–z 0–9 - _ . :`) and a `cmd`. The device answers each `id` exactly once on `ack`. If the same `id` arrives again (the cloud retried), the device re-sends the first answer and does **not** run the command twice. It remembers the last 16 ids.

### `relay`
```json
{"id": "c-7f3a", "cmd": "relay", "outlet": 0, "on": true}
```
Sets the user's intent. Turning on while `waiting` succeeds, but the relay closes only when the restore delay ends. Fails with `locked` if the outlet is locked.

### `reset`
```json
{"id": "c-7f3b", "cmd": "reset", "outlet": 0}
```
Clears a lock. The outlet comes back **off**; the user then turns it on. Errors: `not_locked`, `still_hot` (an over-temperature lock is refused until the board is 10 °C below the limit).

### `limits`
Partial update: send only the fields that change.
```json
{"id": "c-7f3c", "cmd": "limits", "outlet": 1,
 "limits": {"restore_delay_s": 180, "v_low": 190, "restore_policy": "last"}}
```

| Field | Range | Default |
|---|---|---|
| `v_low` | 150–215 V | 185 |
| `v_high` | 240–270 V, at least 30 V above `v_low` | 255 |
| `v_instant_high` | `v_high` + 5 to 290 V (trips on one reading) | 275 |
| `trip_ms` | 500–10,000 | 2000 |
| `restore_delay_s` | 5–900 | 30 (general), 180 (fridge, freezer, AC) |
| `i_limit` | 0.5 A to the board maximum (Proto 0: 10 A) | board maximum |
| `restore_policy` | `last`, `on`, `off` | `last` |

Hysteresis (3 V), the over-current timing (5 s above `i_limit`, or one reading above 1.5 × `i_limit`) and the combined limit (Proto 0: 15 A) are fixed by firmware. An invalid combination is rejected whole, with the reason as the error text.

### `schedule`
Replaces the outlet's whole schedule (maximum 8 entries; an empty list clears it). Times are local (Ghana: UTC+0).
```json
{"id": "c-7f3d", "cmd": "schedule", "outlet": 0, "entries": [
  {"at": "06:30", "on": true,  "days": "weekdays"},
  {"at": "23:00", "on": false},
  {"at": "10:15", "on": true,  "days": ["sat", "sun"]}
]}
```
`days` is `daily` (default), `weekdays`, `weekends`, or a list of `mon`…`sun`. Schedules run on the device and keep running offline. Entries missed while the socket had no power are **not** replayed: after an outage the restore policy decides.

### `calibrate` (bench units only)
```json
{"id": "c-7f3e", "cmd": "calibrate", "channel": "p0", "reference": 1998.4}
```
`channel` is `v`, `i0`, `i1`, `p0` or `p1`. The device compares the reference with its mean over the last 10 s window and adjusts that channel's gain. Corrections larger than ±20% are refused. Works only when `bench` is set at provisioning; otherwise the error is `bench_mode_off`.

## Acks

```json
{"id": "c-7f3a", "ok": true}
{"id": "c-7f3a", "ok": false, "error": "locked"}
```

Error texts are fixed strings from the firmware (no quotes), safe to show to an engineer and to map to user-facing copy.

## Not in v0

- Telemetry buffered in flash while offline (only events are buffered, in RAM). The cumulative `wh` counters mean energy totals are still exact.
- Signed OTA over `dev/{id}/ota`.
- Metering over Matter (Electrical Power and Energy Measurement clusters).
