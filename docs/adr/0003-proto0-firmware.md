# ADR-0003: Proto 0 firmware architecture and toolchain

- Status: accepted
- Date: 2026-11-10
- Decided by: Daniel Owusu Mensah (plan signed off before implementation)

## Context

Proto 0 runs our own firmware on a store-bought Sonoff Dual R3 v2 (ESP32, BL0939, two relays) to develop metering, protection and Matter before any custom board exists. The same firmware must carry over to the EVT board (ESP32-C6, BL0939 behind an ISO7721 isolator).

## Decision

**Toolchain.** ESP-IDF v6.0.2 with `espressif/esp_matter` ~1.6.1 from the component registry (Matter 1.4 or later is required for new certifications). Both are pinned in `firmware/app/main/idf_component.yml` and the CI container tag.

**Structure.**

- `sws_core`: plain C99, no ESP-IDF headers. It holds the BL0939 driver, energy counters, the protection state machine, relay drive timing, schedules and the protocol. It is unit-tested on Linux with AddressSanitizer and UBSan.
- `app`: ESP-IDF glue. A **board layer** (`board_t`) holds everything that differs between Proto 0 and EVT, so adding EVT means adding one board file.
- **One control task** owns all safety state. Inputs, MQTT, Matter and the console only post messages to its queue, so the safety logic has no locks and no shared mutable state. The task runs at high priority on core 1 and is watched by the task watchdog with a 2 s timeout. On a hang the chip resets, and the non-latching relays drop open.

**Protection defaults** (tunable per outlet within fixed bounds; final values come from variac tests):

| Setting | Default |
|---|---|
| Under / over-voltage trip | below 185 V or above 255 V for 2 s |
| Instant over-voltage trip | above 275 V on one reading |
| Re-arm hysteresis | 3 V inside the limits |
| Restore delay | 30 s general, 180 s compressor loads |
| Over-current (Proto 0) | 10 A for 5 s, or 15 A at once; 15 A combined sheds the larger load |
| Over-temperature (Proto 0) | 75 °C, BL0939 die as a proxy (no NTCs on this board) |

Power-up counts as a restoration: outlets wait out their restore delay before switching on.

**Storage.** Three NVS partitions:

- `nvs`: settings, calibration, Matter.
- `nvs_hb`: a once-a-minute heartbeat holding the alive time and energy counters, so an outage loses at most 60 s of energy and its start is known to 60 s.
- `fctry`: device identity from `tools/provision.py`, so re-provisioning never touches calibration or pairing.

**Proto 0 scope limits.**

- Secure boot and flash encryption stay **off**: enabling them burns eFuses permanently on a bench unit.
- PWM relay holding stays off by default until the Sonoff's coil drive is measured.
- The S1/S2 inputs are disabled: they sit at mains potential on a non-isolated board.
- Metering over Matter (Electrical Power and Energy Measurement clusters, which need delegate classes) is the next increment. Metering goes over MQTT for now.

**Offline build.** `SWS_OFFLINE=1` builds without the component registry (Matter off, local cJSON, esp-mqtt from a clone). CI builds both variants.

## Consequences

- The safety logic is tested on every push without hardware.
- Flash budget: 2 × 1.875 MB app slots on 4 MB. If Matter, TLS and MQTT outgrow a slot on the ESP32, Proto 0 falls back to one large app partition and serial updates. The EVT module (ESP32-C6-MINI-1-H4) has the same 4 MB.
