# EVT1 schematic: review notes

Draft F, 11 Nov 2026. For Daniel's engineering review before layout starts.

## What changed in draft F (layout plan)

- **Board link:** J4 and J101 are now 14-way, 1.0 mm FPC connectors instead of the 2 × 7, 1.27 mm header pair. The layout plan puts the boards about 20 mm apart, too far for a header.
  - **Connector:** TE 1-84952-4, bottom contact, right angle, 1 A and 200 V AC per contact (LCSC C574848). JLC had 73 in stock on 11 Nov, so reserve them early; the top-contact version is 1-84953-4 (LCSC C3169461).
  - **Pin map:** unchanged, so +5 V and GND keep two contacts each: 2 A capacity against the 0.6 A peak.
  - **Cable:** 14-way, 1.0 mm FFC, 0.3 mm thick, same-side contacts (Type A). With both connectors bottom-contact and the cable folded into a C between them, the same face of the cable meets both connectors. The conductors run straight through the bends, so J101 pin 1 must sit at the same y as J4 pin 1; I place it that way at layout.
  - **Cable length:** set at layout from the cable path, about 40 mm. JLC's same-side 14-way cables start at 10 cm (C34155); the 5 cm cable (C128003) is reverse-contact, which would need J101 changed to the top-contact 1-84953-4. I'll pick one at layout.
  - **Safety:** the cable carries only SELV and runs in the safe zone. Its insulation is not counted in any hot-to-safe distance.

Draft E (10 Nov) added the part numbers, pinout checks and the first footprints.

## What changed in draft E (S2 simulation checks)

Full study: `hardware/sim/S2-study.md`.

- **Polarity and earth check fails as drawn.** The draft C hysteresis (R31/R33, R32/R34) feeds the 1 MΩ peak-detector node and latches it at about 2.8 V. **A socket with no earth reads "earthed and correct".** Keeping the peak detector and moving the hysteresis still fails most corners: BAT54WS leakage at 85 °C, and the mains range overlapping the factor of 2 between earthed and unearthed.
- **Scheme F, accepted by Daniel and drawn in draft E:**
  - remove the peak detector: C12, R33 and R34 out;
  - D3 becomes a BAS116 low-leakage diode in series;
  - R17/R20 47 kΩ, R21 470 kΩ, threshold ladder 182k/100k/49.9k;
  - POL_A/POL_B become 50 Hz pulse trains;
  - firmware times them, converts duty to amplitude and divides by the BL0939's mains reading;
  - end-of-line test stores each unit's reference ratio.
  
  This passes every corner: 185–265 V, earth–neutral 0–30 V, arms ±20 %, 0–85 °C.
- **Limit of any passive check:** a plugged-in appliance's EMI filter hides a missing earth. No-earth can only be reported from a wiring test with both outlets empty.
- **D3 decided (Daniel, 10 Nov 2026):** no earth gives a warning only, from an installer wiring test run with both outlets empty. Swapped L/N keeps the outlets off. The check runs at power-on with the relays open.
- **Relays pass.** Pull-in margin is 0.37 V with an 85 °C coil. Proposed holding duty is 600 permille at 23 °C, scaled by the NTC temperature.
- **5 V rail passes.** Worst dip 0.18 V; the LD03 peaks at 607 mA, under its 660 mA limit. Firmware rule: stagger the relay pull-ins by at least 60 ms.

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

## Decisions D7–D12

All six accepted by Daniel on 10 Nov 2026. D7 is required by the firmware. D8 is 470 Ω. D9 is 4 × SK6812 RGB with switched 5 V. D10–D12 are as drawn. PR #1 merges once the schematic is closed.

| # | Decision | Why |
|---|---|---|
| D7 | BL0939 address pins strapped to address 5: A1 and A3 to 3.3 V, A2 and A4 to the hot-side ground. | The firmware sends 0x55 (read) and 0xA5 (write). Per the datasheet these are 0x50 and 0xA0 plus the 4-bit address, so they only work at address 5. The pins have internal pull-downs; left floating, the chip sits at address 0 and never answers. |
| D8 | Voltage divider bottom resistor 470 Ω (Proto 0 used 510 Ω). | The datasheet's pin table limits VP to ±100 mV (70 mV rms); its electrical table says 200 mV peak. I designed to the lower figure. With 510 Ω, the 275 V instant trip is already past the limit (71.9 mV rms). With 470 Ω, 230 V gives 55.4 mV rms and the limit is reached at 290 V. The firmware's EVT board file sets `div_r_bottom_kohm = 0.47`. |
| D9 | Light lines: four SK6812MINI-E addressable RGB LEDs on one data pin, two per outlet. Their 5 V rail is switched off in standby. | All 22 usable ESP32-C6 GPIOs are allocated, so discrete white and RGB LEDs do not fit. With the rail switched off, the LEDs' idle current (about 1 mA each) stays out of the standby budget. |
| D10 | Isolator safe side powered by its own XC6206 3.3 V LDO on the rear board. | The board link (then a 2 × 7 header, now a 14-way FFC) has no spare pin for 3.3 V. Powering the isolator from 5 V would put 5 V logic on ESP32 pins. |
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
| 22, 23 | POL_A, POL_B | Polarity and earth pulse trains (50 Hz, edge-timed) |
| 16, 17 | U0TXD, U0RXD | UART0 test pads |

## Open items before layout

**R1. Hot-side supply. Closed in draft D** with the LNK3204D buck; the study is in `hardware/sim/R1-study.md`. Left to confirm:

- the surge level that applies, with the test lab;
- the MOV's V–I curve at 1 kA;
- conducted emissions of the buck (CISPR 14-1) at pre-compliance.

**R2. Relay footprint. Drawn** (`hardware/tools/footprints.py`).
- Omron G5RL-1A-E pinning: coil 1/8, COM 3+6, NO 4+5. The doubled terminals carry the 16 A.
- Hongfa HF115F (D2 second source) is drawn on a 2.52 mm grid (20.16 / 5.04 mm) where Omron uses 20.0 / 5.0 mm. Contact holes are 1.5 mm and sit midway, so either relay fits.
- Still to do: confirm Hongfa's row pitch (assumed 7.56 mm), and check both relays against their drawings with a printed 1:1 footprint before release.

**R3. AT42QT1011 pin 6 (SYNC/MODE). Closed.** The pinout matches Microchip's datasheet. Strapped high (Fast mode, about 1 ms between bursts). Low-power mode sleeps about 80 ms per burst and would make the touch keys feel slow.

**R4. NT3H2111 pinout. Closed.** Checked against NXP's NT3H2111_2211 datasheet (TSSOP8): 1 LA, 2 VSS, 3 SCL, 4 FD, 5 SDA, 6 VCC, 7 VOUT, 8 LB. The LNK3204D SO-8C pinout is also confirmed against Power Integrations' datasheet: 1 BP/M, 2 FB, 4 D, 5–8 S, no pin 3.

**R5. Fuse position.** F1 sits in the neutral feed, because the hot side's ground has to be the live busbar for the shunts. For the L–N loop through the LD03 and the LNK3204 supply this is equivalent to Mornsun's live-side fuse, but ask the test lab. Also ask what prospective fault current to design for at a socket-outlet; F1's 1500 A breaking capacity assumes a final circuit, not a point near the consumer unit.

**R6. Footprints.**
- **Drawn:** the relay (R2), plus three parts from manufacturer data (details in `lib/sws.pretty/README.md`):
  - **Schurter UMT-H fuse:** Schurter's land, pads 3.75 × 5.6 mm with a 10.0 mm gap.
  - **Mornsun LD03:** 2.54 mm grid, AC pins 18.3 mm (pad to pad) from DC pins. Mornsun's drawing is only a graphic, so the pin positions come from two built designs that agree. Caliper-check the first module. Plan for 17.6 mm height (the current Mornsun table; the 2021 datasheet says 16.0) in the 35 mm box.
  - **SK6812MINI-E reverse-mount LED:** 3.6 × 3.2 mm cutout with R0.5 corners. The body corners need the extra 0.2 mm, because a 3.4 × 3.0 cutout with R0.5 corners hits them. Light exits on the B side; place it on the side away from the faceplate.
- **Imported:** ESP32-C6-MINI-1, Espressif's own footprint (CC-BY-SA 4.0).
- **Set by the enclosure, drawn at layout:**
  - mains terminal;
  - BS 1363 outlet contacts;
  - thermal cut-off;
  - touch electrodes;
  - NFC antenna.

**R7. Part numbers. Closed 10 Nov 2026.** Every BOM line has an LCSC number or a stated source (`ASSIGN` table in `evt1_design.py`).

Notable choices:
- Bourns CSS2H 5 W metal-element shunts.
- ROHM KTR18 500 V anti-surge resistors in the mains divider (low JLC stock, so order early).
- Ymin 450 V bulk capacitors rated 12 000 h.
- Panasonic FK electrolytics. C19 and C26 move to 6.3 × 5.8 mm footprints.
- 0.5 % feedback resistor for the buck.

Bought outside LCSC:
- LNK3204D-TL (DigiKey);
- VR37 high-voltage resistors (DigiKey/Mouser);
- LD03 (Mornsun or DigiKey, D4);
- Schurter UMT-H;
- Bourns FW20A fusible resistor for R2.

Open:
- The MOV is a plain 10D561K for EVT; a thermally protected type (Littelfuse TMOV or SETsafe SFV) is needed for DVT.
- R1 (12 Ω 3 W) gets its LCSC number at order.

**R8. Values to tune at EVT:**

- Touch: Cs (10 nF) and Rs (4.7 kΩ).
- NFC antenna tuning capacitor C115.
- Buck feed-forward capacitor C103 (not fitted).
- Relay holding duty. S2 proposes 600 permille at 23 °C, scaled by 1 + 0.00393 (T − 23) from the relay NTC. Confirm with drop-out and knock tests.

## Firmware changes this schematic implies

A new `board_evt_c6.c` with:

- The GPIO map above.
- `div_r_bottom_kohm = 0.47`.
- Touch inputs active high. The board struct gains a polarity flag; today it assumes active low.
- Light lines on RMT with a power-enable pin, instead of the single status LED.
- Polarity check (scheme F, `hardware/sim/S2-study.md`): with the relays open, timestamp POL_A/POL_B edges over 10 mains cycles. Take duty d of A, or of B if A never goes high. Amplitude = (TH/g + Vf)/cos(πd), with TH_A 1.490 V, TH_B 0.496 V, g 0.911, Vf 0.50 V. Ratio k = amplitude / (BL0939 Vrms × √2), compared with the unit's stored k0:
  - above 0.68: correct;
  - 0.33–0.68: no earth (warning);
  - below 0.33: swapped (outlets stay off).
  
  A duty of 100 % means the hot side is down (isolator default). Store k0 at end-of-line test.
- Relay holding: 600 permille at 23 °C × (1 + 0.00393 (T − 23)) from the relay's NTC, capped at 1000. Start the second relay's pull-in at least 60 ms after the first.
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
