# EVT1 schematic: review notes

Draft D, 10 Nov 2026. For Daniel's engineering review before layout starts.

## What changed in draft D

The hot-side supply is now an LNK3204D half-wave buck, which closes R1 (Daniel's decision, 10 Nov 2026). The R1 study (`hardware/sim/R1-study.md`) showed the KP3310 could not both survive a surge and supply the hot side.

- **Input:** R2 47 Ω 2 W fusible → D1 + D8 (two M7 in series) → π-filter of C1/C23 (4.7 µF 450 V) with L1 (1 mH).
- **Buck:** U1 LNK3204D. BP/M set to 1 µF (reduced current limit). L2 1 mH. D9 ES1J freewheel diode, 35 ns.
- **Feedback:** sampled through D10/C25 and set by R35/R36 for 5.0 V. Trim R35 at bring-up.
- **3.3 V:** U7 XC6206 from +5V_HOT. R37 is an unfitted preload.
- **Removed:** the KP3310 and D7 (SMCJ400A).
- **Simulated:** the switch peaks at 465 V for a 4 kV surge, against a 725 V rating. Estimated hot-side standby is about 0.1 W.

## What changed in draft C

| Change | Why |
|---|---|
| F1 is now a Schurter UMT-H 1 A time-lag fuse (3403.0274.23), 1500 A breaking capacity, 277 VAC. | If the MOV fails short, F1 has to interrupt the circuit's prospective fault current. The 1 A TE5 fuse planned before is rated to break only 25 A at 250 VAC. |
| D7, SMCJ400A, clamps the KP3310 drain to ground. | Keeps the drain under its 650 V rating in a surge, provided R2 limits the current (see R1). It stays off in normal use: 400 V stand-off against a 389 V peak at 275 V. |
| Comparator hysteresis: R31/R32 split the inputs; R33/R34 (330 kΩ) feed back from the outputs. | Bit A now sets above 1.05 V and clears below 0.95 V; bit B sets above 0.32 V and clears below 0.22 V. Worst cases (correct wiring at 207 V, no earth at 253 V) still clear both bands. |
| Net ties NT1–NT4 at the shunt pads. | They force the BL0939 IP/IN traces to start at the shunt pads (Kelvin sensing), which the ±1 % target depends on. They are not BOM parts. |
| Drawing: hot-side blocks tinted, IC pins grouped by function, decoupling capacitors placed with their ICs. | Readability. |

## Scope

Both boards from the EVT hardware plan v0.1. The plan's decisions D1, D2, D4, D5 and D6 are taken as accepted. D3 (what to do when no earth is detected) stays open; it changes firmware only, not this schematic.

| Board | Sheet layout | Parts | Nets |
|---|---|---|---|
| Rear (`sws-rear`) | One sheet: hot side, hot-side sensing, barrier crossing, safe zone | 99 (+ 4 net ties) | 69 |
| Front (`sws-front`) | One sheet: power and processor, user interface | 67 | 45 |

`verify.py` passes with 0 errors: the KiCad netlist matches the design data, and the safety rules in `hardware/README.md` hold.

## New decisions, for the decision log

| # | Decision | Why |
|---|---|---|
| D7 | BL0939 address pins strapped to address 5: A1 and A3 to 3.3 V, A2 and A4 to the hot-side ground. | The firmware sends 0x55 (read) and 0xA5 (write). Per the datasheet these are 0x50 and 0xA0 plus the 4-bit address, so they only work at address 5. The pins have internal pull-downs; left floating, the chip sits at address 0 and never answers. |
| D8 | Voltage divider bottom resistor 470 Ω (Proto 0 used 510 Ω). | The datasheet's pin table limits VP to ±100 mV (70 mV rms); its electrical table says 200 mV peak. I designed to the lower figure. With 510 Ω, the 275 V instant trip is already past the limit (71.9 mV rms). With 470 Ω, 230 V gives 55.4 mV rms and the limit is reached at 290 V. The firmware's EVT board file sets `div_r_bottom_kohm = 0.47`. |
| D9 | Light lines: four SK6812MINI-E addressable RGB LEDs on one data pin, two per outlet. Their 5 V rail is switched off in standby. | All 22 usable ESP32-C6 GPIOs are allocated, so discrete white and RGB LEDs do not fit. With the rail switched off, the LEDs' idle current (about 1 mA each) stays out of the standby budget. |
| D10 | Isolator safe side powered by its own XC6206 3.3 V LDO on the rear board. | The 2 × 7 header has no spare pin for 3.3 V. Powering the isolator from 5 V would put 5 V logic on ESP32 pins. |
| D11 | The BL0939's two alarm outputs (CF for channel A, I_LEAK for channel B) are ORed on the hot side into isolator channel E. | One isolator channel covers both outlets. Both outputs are active high per the datasheet. |
| D12 | ESP32-C6 GPIO map as below. | Fixed by the netlist; the firmware's `board_evt_c6.c` must match. |

### GPIO map (D12)

| GPIO | Net | Use |
|---|---|---|
| 0, 1 | NTC1, NTC2 | ADC1, relay temperature (10 kΩ pull-ups on the front board) |
| 2 | ALARM | BL0939 fast over-current alarm, active high |
| 3 | ZX | Zero-cross from the BL0939 |
| 4, 5 | NFC_SDA, NFC_SCL | I²C to NT3H2111 (strapping pins, harmless with pull-ups) |
| 6, 7 | TOUCH1, TOUCH2 | AT42QT1011 outputs, **active high** |
| 8 | LED_DIN | Light-line data via RMT (strap, pulled up) |
| 9 | BOOT | Strap, pulled up; test pad |
| 12, 13 | USB D−, D+ | USB-Serial-JTAG test pads |
| 14 | NFC_FD | NFC field detect |
| 15 | LED_PWR_EN | Light-line 5 V switch, high = on (strap, pulled down) |
| 18, 19 | RELAY1, RELAY2 | LEDC PWM to the relay drivers |
| 20, 21 | MTR_RX, MTR_TX | UART1 to the BL0939 through the isolator |
| 22, 23 | POL_A, POL_B | Polarity and earth bits |
| 16, 17 | U0TXD, U0RXD | UART0 test pads |

## Open items before layout

**R1. Hot-side supply. Closed in draft D** with the LNK3204D buck; the study is in `hardware/sim/R1-study.md`. Left to confirm:

- the surge level that applies, with the test lab;
- the MOV's V–I curve at 1 kA;
- conducted emissions of the buck (CISPR 14-1) at pre-compliance.

**R2. Relay footprints.** The relay symbol's pin numbers (1 A1, 2 A2, 3 COM, 4 NO) are placeholders. Draw the G5RL-1A-E footprint from Omron's drawing, then confirm the HF115F/005-1HS3AF lands on it (D2).

**R3. AT42QT1011 pin 6 (SYNC/MODE).** It is strapped low by a fitted 0 Ω resistor, with an unfitted 0 Ω to strap it high. Check the datasheet's mode table and fit the right one.

**R4. NT3H2111 pinout.** Taken from the LCSC part listing (1 LA, 2 VSS, 3 SCL, 4 FD, 5 SDA, 6 VCC, 7 VOUT, 8 LB). Check it against NXP's datasheet before layout.

**R5. Fuse position.** F1 sits in the neutral feed, because the hot side's ground has to be the live busbar for the shunts. For the L–N loop through the LD03 and KP3310 this is equivalent to Mornsun's live-side fuse, but ask the test lab. Also ask what prospective fault current to design for at a socket-outlet; F1's 1500 A breaking capacity assumes a final circuit, not a point near the consumer unit.

**R6. Placeholder footprints, drawn at layout:**

- mains terminal
- BS 1363 outlet contacts
- thermal cut-off
- relay
- LD03
- ESP32-C6-MINI-1 (KiCad 7 has no footprint for it; KiCad 8's library may)
- SK6812MINI-E reverse-mount
- touch electrode
- NFC loop antenna

**R7. LCSC numbers still to assign: 48 parts (40 rear, 8 front).** Includes the new LNK3204D, ES1J, chokes and 450 V capacitors. F1 (Schurter UMT-H) comes from Schurter distributors.

- Parts that need choosing first: shunts, fuse, MOV, wirewound and flameproof resistors, electrolytics, HV resistors (Vishay VR37 is not on LCSC), NTCs, B2B connectors, inductor.
- 1 % resistor values outside JLC's basic list.
- 33 nF and 10 nF C0G capacitors.

The full BOM marks every part's status. Numbers marked "JLC basic, confirm at order" come from JLC's basic-parts list and were not rechecked this session.

**R8. Values to tune at EVT:**

- Touch: Cs (10 nF) and Rs (4.7 kΩ).
- NFC antenna tuning capacitor C115.
- Buck feed-forward capacitor C103 (not fitted).
- Relay holding duty.

## Firmware changes this schematic implies

A new `board_evt_c6.c` with:

- The GPIO map above.
- `div_r_bottom_kohm = 0.47`.
- Touch inputs active high. The board struct gains a polarity flag; today it assumes active low.
- Light lines on RMT with a power-enable pin, instead of the single status LED.
- POL_A/POL_B read only while the BL0939 reports 207–253 V. The isolator's outputs read high whenever the hot side is unpowered.
- ALARM ignored until the BL0939's MODE register is written. Until then CF outputs energy pulses.
- NTC temperature as the over-temperature source.

## Next steps (plan section 9)

1. Your review of this schematic and a decision on R1.
2. SPICE checks:
   - relay pull-in and holding;
   - polarity levels at 207 and 253 V with ±20 % tolerances;
   - BL0939 input filter phase at 50 Hz;
   - LD03 dip during a relay pull-in plus a Wi-Fi transmit;
   - the R1 surge case.
3. Assign the remaining LCSC numbers.
4. Layout v0.1.
