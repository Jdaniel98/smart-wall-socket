# Firmware

ESP-IDF v6.0.2 firmware for the Smart Wall Socket. Proto 0 target: **Sonoff Dual R3 v2**, bench use only. Read the [bench guide](../docs/proto0-bench-guide.md) before connecting anything to mains.

## Layout

```
components/sws_core/   Portable C99 logic, no ESP-IDF headers; unit-tested on Linux
  bl0939.c             BL0939 frames, checksum, conversion to SI units
  energy.c             Cumulative energy from 24-bit pulse counters (wrap, chip reset)
  protection.c         Voltage / current / temperature state machine
  relay_drive.c        Pull-in then PWM holding; zero-cross timing
  schedule.c           On-device weekly schedules
  proto.c              MQTT commands and JSON messages (docs/protocol.md)
app/                   ESP-IDF project
  main/board/          Board layer: Proto 0 today, EVT next
  main/control.c       The one task that owns all safety state
  main/*.c             Metering UART, relays, inputs, LED, NVS, MQTT, console
  main/app_matter.cpp  Matter: per-outlet plug + electrical sensor (W, V, A, PF, kWh)
test/host/             Unit tests (194 checks), run with ASan and UBSan
tools/provision.py     Dev CA, device certificates, factory NVS image
third_party/cjson/     cJSON 1.7.19 (MIT), for host tests and offline builds
```

## Build

### Host tests (any Linux or macOS)

```sh
cmake -S firmware/test/host -B build/host && cmake --build build/host -j && ./build/host/sws_tests
```

### Device (ESP-IDF v6.0.2)

```sh
cd firmware/app
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor    # mains DISCONNECTED
```

The component manager fetches `espressif/esp_matter`, `espressif/mqtt` and `espressif/cjson` on the first build.

### Building without internet

For machines that cannot reach the component registry: Matter off, Wi-Fi from NVS.

```sh
git clone --depth 1 https://github.com/espressif/esp-mqtt /opt/offline/espressif__mqtt
export SWS_OFFLINE=1 IDF_COMPONENT_MANAGER=0 SWS_OFFLINE_EXTRA=/opt/offline
idf.py -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.offline" build
```

Then set Wi-Fi from the console: `wifi <ssid> <password>`, `reboot`.

CI builds both variants on every push and keeps the binaries as artifacts.

## Using it

| Control | Action |
|---|---|
| Button tap | Toggle outlet 1 |
| Button double tap | Toggle outlet 2 |
| Button hold 3 s | Clear locks (over-current or over-temperature) |
| Button hold 10 s | Forget Wi-Fi and Matter pairing (calibration and energy are kept) |
| Blue LED | Solid: online. Short blip: offline. Slow blink: waiting to restore. Fast blink: tripped or locked |

Serial console at 115200 baud (isolated adapter only): type `help`. Main commands are `status`, `relay`, `reset`, `cal`, `hold` and `mqtt`.

## Matter

Each outlet is one endpoint with two device types:

| Device type | Clusters | What Home apps get |
|---|---|---|
| On/Off Plug-in Unit (0x010A) | On/Off, Identify, Groups, Scenes | Switch the outlet |
| Electrical Sensor (0x0510) | Power Topology (tree), Electrical Power Measurement, Electrical Energy Measurement | Live W, V, A and power factor; cumulative kWh |

- Power readings go to the Matter thread once a second. Subscribers are only told when a value moves by about 2% (with floors of 0.5 W, 0.5 V, 10 mA and 1% PF), so a steady load stays quiet.
- Cumulative energy is pushed every 30 s; each push also emits a CumulativeEnergyMeasured event. It is the same counter MQTT reports, so it survives reboots and outages.
- The device advertises ±2% accuracy, the Proto 0 target. Change `kPowerAccuracy` in `app_matter.cpp` once bench test T1 gives real figures.
- Where it shows up: Home Assistant and SmartThings read these clusters. Apple Home shows live watts for metering outlets from iOS 27. Google Home support varies.

## Flash layout (4 MB)

| Partition | Offset | Size | Holds |
|---|---|---|---|
| nvs | 0x10000 | 48 KB | Settings, calibration, Matter fabrics |
| otadata, phy_init | 0x1C000 | 12 KB | |
| ota_0 / ota_1 | 0x20000 / 0x200000 | 1.875 MB each | Firmware A/B |
| nvs_hb | 0x3E0000 | 64 KB | Heartbeat: alive time and energy, once a minute |
| fctry | 0x3F0000 | 24 KB | Device identity from `tools/provision.py` |

## Known limits of v0.1

- Telemetry is not buffered in flash while offline; events are buffered in RAM (last 32). The cumulative energy counters keep totals exact.
- Proto 0 has no NTCs: over-temperature uses the BL0939's die temperature as a rough proxy.
- PWM relay holding is off on the Sonoff until its coil drive is measured (`hold`).
- No secure boot or flash encryption on bench units; device keys are development credentials.
