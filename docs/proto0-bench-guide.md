# Proto 0 bench guide

How to flash, pair, calibrate and test the Proto 0 firmware on a Sonoff Dual R3 v2.

**Proto 0 never leaves the bench.** It is not a product, is not enclosed to any standard, and must not be used to power anything at home or unattended.

## 1. Safety rules

The Dual R3 measures current through shunts on the mains side, so treat **every pin and pad on the board as live** whenever it is connected to mains.

1. **Flash and debug with mains disconnected.** Power the board from the USB-UART adapter's 3.3 V only.
2. If you need the serial console **while on mains**, use a USB isolator between the computer and the 3.3 V adapter. The board must be on the isolation transformer, inside its enclosure, with only the cable leaving it.
3. **Never wire the S1/S2 terminals.** On this board they are at mains potential. The firmware leaves them disabled.
4. Close the enclosure before applying mains. Make any wiring change with mains disconnected and the plug in your hand.
5. Bench supply order: mains → 30 mA RCD → isolation transformer → variac → enclosure. The isolation transformer stops a single touch to earth from being lethal, but not a touch across L and N, and the RCD cannot see faults on the transformer's secondary. Insulated tools only, and **never work on live mains alone**.
6. Stay within the Sonoff's rating: 10 A per outlet, 15 A total, rooms under 40 °C. The firmware enforces 10 A and 15 A, but do not rely on it.

## 2. What you need

| Item | Notes |
|---|---|
| Sonoff Dual R3 **v2** | Check the PCB marking and that the metering chip is a BL0939. v1 units use a CSE7761 and will report a meter fault. |
| 3.3 V USB-UART adapter | CP2102, CH340 or FT232, set to 3.3 V (never 5 V) |
| USB isolator | Only for using the console on mains (rule 2) |
| Enclosure | Insulated junction box with two BS 1363 sockets wired to L Out 1 / L Out 2, with neutral and earth common. Strain relief on the supply cable. |
| Variac 0–270 V, at least 2 kVA | For the voltage tests |
| Reference meter | Calibrated plug-in or DIN-rail meter that shows V, A, W and PF |
| Loads | 2 kW kettle or heater (resistive), fridge (inductive), LED bulb (low PF), phone charger (a few W), TV on standby (<1 W) |

## 3. Flash the firmware

1. **Back up the original firmware** first. It is the only copy:
   ```sh
   esptool.py --chip esp32 -p /dev/ttyUSB0 read_flash 0 0x400000 sonoff-dualr3v2-original.bin
   ```
2. Wire the adapter to the Dual R3's programming pads: 3V3, GND, TX→RX, RX→TX.
3. Hold the on-board button (GPIO0) while connecting 3.3 V to enter download mode.
4. Flash a CI build: download `firmware-matter` from the latest green run under **Actions**, then:
   ```sh
   cd firmware-matter
   esptool.py --chip esp32 -p /dev/ttyUSB0 write_flash @flash_args
   ```
   Or build and flash locally from `firmware/app`: `idf.py -p /dev/ttyUSB0 flash monitor`.
5. Reconnect without the button held. The console prints the device id and `sws>`. Type `id` and note it.

## 4. Connect it to your broker (optional)

The socket works fully without the cloud: protection, Matter, button and schedules. To see telemetry and send commands:

```sh
# once
python firmware/tools/provision.py ca --out certs/
# per unit (use the id from step 3.5); --bench allows calibration over MQTT
python firmware/tools/provision.py device --id sws-a1b2c3d4e5f6 --ca certs/ \
    --uri mqtts://<your-laptop-ip>:8883 --out build/sws-a1b2c3d4e5f6/ --bench
esptool.py --chip esp32 -p /dev/ttyUSB0 write_flash 0x3F0000 build/sws-a1b2c3d4e5f6/fctry.bin
```

Run Mosquitto with the config in [protocol.md](protocol.md#broker-rules-mosquitto) and a client certificate of your own for the laptop. Then:

```sh
mosquitto_sub -h <host> -p 8883 --cafile certs/ca.crt --cert me.crt --key me.key -t 'dev/#' -v
mosquitto_pub ... -t dev/sws-a1b2c3d4e5f6/desired \
  -m '{"id":"t1","cmd":"limits","outlet":0,"limits":{"i_limit":5}}'
```

## 5. Pair with Apple Home or Google Home

Development builds use Espressif's test credentials. Setup code **20202021**, discriminator **3840**, manual pairing code **3497-011-2332**. The QR code is printed in the boot log.

- **Apple Home:** Add Accessory → More options → enter the code. Accept the "uncertified accessory" warning. You get two outlets.
- **Google Home:** first create a Matter integration for test devices (vendor ID 0xFFF1, product ID 0x8000) in the Google Home Developer Console, then add it in the Google Home app.

Matter sets the Wi-Fi network, then the socket connects to your broker if provisioned.

## 6. Calibrate

Use a steady resistive load (kettle full of water, or a heater) on one outlet. Run it for at least 20 s, then read the reference meter. Each `cal` uses the device's mean over the last 10 s.

```
sws> cal v  229.8     # reference voltage
sws> cal i0 8.65      # reference current, outlet 0
sws> cal p0 1988      # reference power, outlet 0
```
Repeat `i1` and `p1` on the other outlet. `status` shows the gains. A correction larger than ±20% is refused: that points at a wiring or meter problem, not calibration. The gains survive reflashing and factory reset.

## 7. Test plan

Record every result in the table at the end. A test passes only if all its criteria pass.

| # | Test | How | Pass when |
|---|---|---|---|
| T1 | Accuracy | Each of the 5 loads on each outlet; compare V, I, P with the reference after 30 s | Within ±2% of the reference from 10 W to 2.2 kW (roadmap). Note error at <10 W separately; the spec target for EVT is ±1%. |
| T2 | Under-voltage | Lamp on outlet 0. Variac down from 230 V to 180 V | Off 2–3 s after crossing 185 V. Stays off at 186 V (hysteresis). Comes back 30 s after rising above 188 V |
| T3 | Short dip | Variac to 175 V for about 1 s, then back | No trip |
| T4 | Over-voltage | Variac to 258 V and hold; separately, step quickly to 276 V | Trips after 2 s at 258 V; trips on the first reading at 276 V (within about 1 s: the BL0939 updates every 800 ms) |
| T5 | Dip while waiting | Trip it, raise the voltage, then dip again before the delay ends | Back to tripped; the 30 s count starts again |
| T6 | Outage | Lamp on, pull mains for 2 min, restore | Outlets stay off for the restore delay (30 s, or 180 s if set as compressor). An `outage` event of about 120 s (±60 s) arrives |
| T7 | Over-current | `limits` i_limit 5 A, then a 2 kW kettle (8.7 A > 1.5 × 5 A) | Locks within about 1 s; tap does nothing; button held 3 s clears it; outlet comes back off |
| T8 | Sustained over-current | i_limit 8 A, same kettle | Locks after about 5 s |
| T9 | Offline | Unplug the router's internet (LAN up), then the router | Button, schedules and protection keep working; telemetry resumes on reconnect with `wh` continuous |
| T10 | Matter | Toggle from Apple Home during normal running and during a restore wait | Normal: switches within 1 s. Waiting: the app shows on and the relay closes when the delay ends |
| T10b | Matter metering | Kettle on outlet 0; read the outlet in Home Assistant (Matter integration) and, with iOS 27, in Apple Home | Watts within ±2% of the reference; kWh rises and matches `status`; outlet 1 shows about 0 W |
| T11 | Watchdog | `reboot` with a load on | Relays drop at once, then the restore delay runs |
| T12 | Meter fault | Not testable without opening the BL0939 link; covered by host tests | — |

Defaults to tune from these results: `v_low`, `v_high`, `restore_delay_s` per appliance type. Put agreed values in an ADR.

### Results

| Date | Test | Outlet | Load | Reference | Device | Error | Pass? | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |
