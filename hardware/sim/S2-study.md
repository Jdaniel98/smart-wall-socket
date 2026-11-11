# S2 study: polarity check, relay drive and 5 V rail

10 Nov 2026. These are the simulation checks left after R1, run against EVT1 schematic draft D.

## Result

| Check | Verdict |
|---|---|
| Polarity and earth check (block 5) | **Fails as drawn.** With no earth, the socket reads "earthed and correct". A redesign (scheme F) passes every corner once each unit is calibrated. |
| Relay pull-in | Passes. Worst coil voltage is 4.72 V, against 4.35 V must-operate for a coil at 85 °C. |
| Relay holding | 60 % PWM at 23 °C, scaled with coil temperature from the NTC, cuts coil supply current from 80 to 28 mA per relay. Needs bench confirmation. |
| 5 V rail (LD03) | Passes. The worst dip is 0.18 V, and the LD03 peaks at 607 mA, under its ≥660 mA current limit. Stagger the relay pull-ins to gain about 50 mA of margin. |

## 1. Polarity and earth check

### Why draft D fails

Draft C added hysteresis (R31/R33 and R32/R34) from each comparator output back into the peak-detector node. That node is a 1 µF capacitor on a 1 MΩ bleed. With both outputs high, the node sees 3.3 V through 170 kΩ against 1 MΩ, so it settles at 3.3 × 1/1.17 = **2.8 V whatever the input**. It latches.

- **Earthed and correct:** latches to "correct". This is the right answer, but only by luck.
- **Swapped:** reads "swapped", because both outputs start low and stay there.
- **No earth:** the peak (0.6 V) sets bit B. Output B then lifts the node past threshold A, and the circuit latches to **"correct"**.

Ngspice confirms all three (`polarity.py C`).

### Fixing the hysteresis alone is not enough

Topology E keeps the peak detector and moves the hysteresis to the threshold side. It classifies the nominal cases. The worst-case corners fail (`polarity_corners.py E`):

| Wiring | Corners passed | Peak range |
|---|---|---|
| Correct | 3 of 36 | 0.41–1.05 V |
| Swapped | 20 of 20 | 0–0.30 V |
| No earth | 6 of 16 | 0.15–0.90 V |

Two things defeat a static-level detector:

- **BAT54WS leakage at 85 °C.** It is several µA, against a 1.4 µA bleed, and pulls the 1 MΩ peak node down by about 0.25 V.
- **Mains voltage.** Fixed thresholds must separate full from half amplitude while mains itself spans 207–253 V. On top of that come ±20 % drift in the high-voltage arms and the earth–neutral voltage. Together they overlap the factor of 2 that tells "earthed" from "no earth".

### Scheme F: pulse-width ratio

Remove the peak detector. Each comparator compares the half-wave sense voltage directly with its threshold, so POL_A and POL_B become 50 Hz pulse trains. Firmware then:

1. times the pulses over 10 mains cycles (GPIO edge timestamps);
2. converts duty d into the sense amplitude with V = (TH/g + Vf) / cos(πd);
3. divides by the mains peak the BL0939 already measures.

The resulting ratio k doesn't depend on mains voltage. End-of-line test stores each unit's own k0, measured with correct wiring at 230 V, which cancels the arm and threshold tolerances. Classification of k/k0:

- **above 0.68:** earthed and correct;
- **0.33 to 0.68:** no earth;
- **below 0.33:** swapped.

Circuit changes (block 5):

| Ref | Draft D | Scheme F |
|---|---|---|
| R17, R20 | 20 kΩ | 47 kΩ 1 % (larger signal, arms kept equal) |
| D3 | BAT54WS Schottky | BAS116,215 low-leakage diode, 5 nA max (LCSC C48502), in series |
| C12 | 1 µF | removed |
| R21 | 1 MΩ | 470 kΩ |
| R33, R34 | 330 kΩ hysteresis | removed |
| R22 / R23 / R24 | 220k / 68k / 30k | 182k / 100k / 49.9k 1 %: thresholds 1.490 V and 0.496 V |
| R31, R32, U4, D2 | — | unchanged |

Corners: mains 185–265 V; earth–neutral voltage 0–30 V (50 V when swapped); 5 % flat-topped waveform; arms ±20 % common and ±2 % mismatched; 1 % resistors; 3.3 V ±2 %; comparator offset ±7 mV; diode at 0–85 °C; BL0939 reading ±1 %. Results (`polarity_f_corners.py`):

| Wiring | Calibrated per unit | Design k0, arms ±20 % | Design k0, arms ±3 % |
|---|---|---|---|
| Correct | 16/16, k/k0 0.77–0.93 | 8/16 | 16/16, 0.70–0.84 |
| No earth | 8/8, 0.47–0.59 | 4/8 | 8/8, 0.43–0.65 |
| Swapped | 4/4, 0–0.24 | 4/4 | 4/4, 0–0.26 |

So end-of-line calibration is needed for production margin. With design values the bench boards work, but correct wiring has only 0.02 of margin. A 5.1 V zener's soft knee (about 5 µA at 4 V) changes nothing measurable.

### Limit of any passive check

With no earth and an appliance plugged in, the appliance's EMI filter ties the earth pin to neutral. With our outlets off, the appliance's live is open and its filter is referenced to neutral.

| Appliance filter on the earth pin | k/k0 | Reads |
|---|---|---|
| 1 nF to N | 0.68 | correct |
| 4.7 nF to N | 0.97 | correct |
| 10 nF to N | 1.00 | correct |
| 4.7 nF to L (outlet on) | 0.00 | swapped |

**A missing earth can only be detected with nothing plugged in.** Swapped L/N is still detected reliably whenever the earth is present. That bears on open decision D3:

- No-earth should be advisory: a warning from an installer "wiring test" run with both outlets empty.
- Swapped keeps the outlets off.
- The check runs at power-on with the relays open, never while an outlet is on.

## 2. Relay drive

G5RL-1A-E DC5 (Omron) coil:

- 62.5 Ω, 80 mA at 23 °C;
- must operate 70 % (3.5 V), must release 10 % (0.5 V);
- maximum 130 %;
- operate time 15 ms.

The HF115F/005-1HS3AF second source has the same coil: 62 Ω, 3.5 V pick-up and 0.5 V drop-out.

**Pull-in.** Must-operate voltage scales with copper resistance:

- 3.5 V at 23 °C;
- 4.12 V at 70 °C;
- 4.35 V at 85 °C.

Worst available coil voltage is 5.0 V − 2 % (LD03 accuracy) − 0.18 V (worst dip below) = **4.72 V**. That leaves 0.37 V (8 %) of margin with an 85 °C coil. The 50 ms full-duty pull-in is over 3× the 15 ms operate time.

**Holding (firmware).** With the SS14 freewheel diode the coil averages D·5 − (1−D)·0.3 V. Supply current is D times the coil current.

| Duty | Coil voltage | Coil current (23 °C) | 5 V supply current | Coil power |
|---|---|---|---|---|
| 100 % | 5.0 V | 80 mA | 80 mA | 400 mW |
| 60 % | 2.88 V | 46 mA | 28 mA | 133 mW |
| 75 % (60 % scaled for 85 °C) | 3.68 V | 47 mA | 35 mA | 173 mW |

Proposed default: 600 permille at 23 °C, multiplied by 1 + 0.00393 (T − 23) from that relay's NTC and capped at 1000. That keeps the ampere-turns constant as the coil heats. It saves about 0.5 W in the sealed box with both outlets on, which matters for the ≤10 °C faceplate target.

Bench checks:

- drop-out voltage on five relays at 25 °C and 70 °C;
- a plug-insertion knock test while holding (contact chatter shows up as gaps in BL0939 current);
- release time with the freewheel diode, against the datasheet's 5 ms.

## 3. 5 V rail (LD03-23B05R2)

LD03 figures from Mornsun's datasheet:

- 5 V, 600 mA;
- output accuracy ±2 %;
- load regulation ±1 %;
- over-current protection ≥110 % (660 mA);
- maximum capacitive load 3000 µF;
- derating 1.3 %/°C from 70 to 85 °C, so about 480 mA at 85 °C.

Mornsun gives no transient-response figures. The model is therefore a PI-regulated current source clamped at 660 mA, with the loop crossover swept over 1–3 kHz.

Loads:

- ESP32-C6 transmit at 802.11b, 20.5 dBm: 382 mA at 3.3 V, Espressif's datasheet figure, through the TLV62569 at 88 %, for a 12 ms burst;
- relay pull-in, coil L swept 0.05–0.2 H;
- light lines at 37 mA or full white (4 × SK6812MINI-E × 3 × 12 mA = 148 mA);
- isolator side 5 mA.

Results (`power5v.py`, 32 cases):

| Case | 5 V minimum (relay side) | Front board minimum | LD03 peak |
|---|---|---|---|
| One relay pulls in, LEDs dim | 4.83–4.95 V | 4.82–4.94 V | 441–447 mA |
| One relay pulls in, LEDs full white | 4.83–4.95 V | 4.81–4.93 V | 553–558 mA |
| Both pull in together, LEDs full white | 4.82–4.95 V | 4.79–4.93 V | 603–607 mA |

The LD03 never reaches its current limit. The buck needs about 3.4 V and the SK6812 needs 3.7 V, so both have more than 1 V of margin.

Two caveats:

- The 607 mA peak exceeds the 480 mA rating at 85 °C, but only for the 12 ms burst.
- Steady state with LEDs at full white, both relays held at 60 % and Wi-Fi receiving is about 275 mA (57 % of the derated rating).

**Firmware rule:** start the second relay's pull-in at least 60 ms after the first. That takes about 50 mA off the worst peak. No LED brightness cap is needed.

## Files

- `polarity.py`: draft D as drawn (topology C) and threshold-side hysteresis (E)
- `polarity_corners.py`, `polarity_corners_E.json`: corners for E
- `polarity_f.py`, `polarity_f_corners.py`: scheme F and its corners (`polarity_f_corners.json` with ±20 % arms, `polarity_f_corners_3pct.json` with ±3 %)
- `power5v.py`, `power5v_results.json`: 5 V rail

Sources: Omron G5RL datasheet (coil ratings); Hongfa HF115F datasheet; Mornsun LD03-23BxxR2 datasheet; Espressif ESP32-C6-MINI-1 datasheet v1 (current consumption); Opsco SK6812MINI-E datasheet; Diodes Inc./Vishay BAT54WS datasheets (leakage); Nexperia BAS116 product page.
