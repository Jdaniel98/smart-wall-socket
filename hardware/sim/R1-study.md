# R1 study: hot-side supply surge and hold-up

10 Nov 2026. ngspice 42. Scripts in this folder reproduce every number below: `cwg_check.cir`, `surge.py`, `holdup.py`, `lnk_surge.py`.

## Result

**The KP3310 can't meet both requirements on this board.** Surviving a 2 kV surge needs at least 150 Ω in series with its drain. With that resistor, half-wave charging delivers at most 5.7–8.5 mA, while the hot side needs 8 mA typically and 15 mA in the worst case.

**Recommendation: replace it with a Power Integrations LNK3204D (LinkSwitch-TN2) half-wave buck.** Its input stage keeps the switch below 470 V at 4 kV, against a 725 V rating, and the converter is not limited by a charging window. This is a design change, so it waits for Daniel's decision.

## Method

**Surge source.** An IEC 61000-4-5 combination-wave generator (7.76 µF, 14.8 Ω, 1.05 Ω, 9.74 µH, 23.3 Ω), checked in `cwg_check.cir`:

| Waveform | Simulated | Standard |
|---|---|---|
| Open-circuit voltage, front / duration | 1.19 µs / 51.6 µs | 1.2 / 50 µs |
| Short-circuit current, front / duration | 7.75 µs / 21.6 µs | 8 / 20 µs |
| Source impedance | 1.96 Ω | 2 Ω |

Surges were applied L–N at 1, 2 and 4 kV, in both polarities.

**Models.** These are assumptions, not vendor SPICE models.
- MOV 561K: I = 1 mA × (V/560)^20.2, plus 0.15 Ω bulk resistance. This fits 560 V at 1 mA and 925 V at 25 A.
- MOV 471K: the same form, fitted to 470 V and 775 V.
- TVS: breakdown at the maximum VBR, with the dynamic resistance implied by the datasheet clamp voltage (10/1000 µs).
- KP3310 charge path: behavioural. The datasheet gives a 50 V AC sync and a 100–160 mA output limit, but no charge-path current limit, so the study sweeps that limit.
- The LD03 branch is left out, which is conservative because it would take some surge current.

## 1. KP3310 drain in a surge (positive polarity)

Peak drain voltage against the 650 V absolute maximum, 561K MOV:

| TVS at drain | R2 = 47 Ω | 100 Ω | 150 Ω | 220 Ω |
|---|---|---|---|---|
| SMCJ400A, 2 kV | 864 V | 747 V | 689 V | 641 V |
| SMCJ400A, 4 kV | 982 V | 827 V | 751 V | 688 V |
| 5.0SMDJ400A, 2 kV | 682 V | 599 V | 568 V | 547 V |
| 5.0SMDJ400A, 4 kV | 741 V | 633 V | 592 V | 563 V |

Draft C's SMCJ400A only protects the drain at R2 ≥ 220 Ω (2 kV) and fails at 4 kV. A 5 kW TVS with R2 = 150 Ω passes both levels.

**Negative surges:** D1 sees the full MOV clamp in reverse: 928 V at 1 kV, 1126 V at 2 kV and 1327 V at 4 kV. A single M7 (1000 V) is not enough; D1 needs two in series.

## 2. KP3310 charging through R2

Average current the KP3310 can deliver into VDD (held at 6 V), 50 V AC sync:

| Charge-path limit | Line | R2 = 0 | 47 Ω | 100 Ω | 150 Ω | 220 Ω |
|---|---|---|---|---|---|---|
| 0.3 A | 185 V | 15.1 mA | 12.6 | 9.7 | 7.1 | 4.9 |
| 1 A | 185 V | 47.3 mA | 20.8 | 10.6 | 7.2 | 5.0 |
| 3 A | 185 V | 115.7 mA | 21.4 | 10.7 | 7.3 | 5.1 |
| 3 A | 207 V | 103.2 mA | 19.1 | 9.6 | 6.5 | 4.5 |

With a 30 V sync, every value with R2 ≥ 100 Ω falls below 3.6 mA.

The cause is the half-wave input. It is required, because the hot side's ground is the live busbar, and it leaves only two short windows per mains cycle in which the line is below 50 V. Any series resistance large enough to protect the drain starves those windows. This holds whatever the chip's internal charge limit is.

## 3. LNK3204 half-wave buck input stage

Circuit: N_F → RF (fusible) → 2 × M7 → C_bulk → 1 mH → C_bulk, with the 561K MOV across the input. The surge arrives at the crest of 253 V mains, so the bulk capacitors start at 358 V.

| Surge | RF | C_bulk | Bulk / drain peak | RF energy |
|---|---|---|---|---|
| 2 kV | 22 Ω | 2 × 4.7 µF | 539 V | 471 mJ |
| 4 kV | 22 Ω | 2 × 4.7 µF | 562 V | 716 mJ |
| 2 kV | 47 Ω | 2 × 4.7 µF | 460 V | 270 mJ |
| 4 kV | 47 Ω | 2 × 4.7 µF | 465 V | 393 mJ |

With RF = 47 Ω (a 2 W surge-rated wirewound fusible type) and 450 V bulk capacitors, the peak stays within the capacitors' surge rating and far below the LNK3204's 725 V switch. The steady-state loss in RF is around 1 mW.

On a negative surge, the 2 × M7 string sees the MOV clamp plus the bulk voltage: about 1.7 kV at 4 kV, inside its 2 kV rating.

## Proposed hot-side supply (needs Daniel's sign-off)

- **Replaces KP3310, D7 and R2:**
  - LNK3204D (SO-8C) high-side buck, 5 V out, referenced to L_BUS.
  - Input: RF 47 Ω 2 W fusible, 2 × M7, π-filter of 2 × 4.7 µF / 450 V with 1 mH.
  - A 3.3 V LDO for the hot side.
- **Standby:** under 30 mW no-load (datasheet) plus about 50 mW of hot-side load at roughly 60 % efficiency, so about 0.1 W. That is better than the KP3310's estimated 0.11–0.22 W.
- **Costs:**
  - About eight more parts, including two inductors.
  - A switching converter on the mains, so conducted emissions (CISPR 14-1) need checking at the lab.
  - The barrier and its crossing parts don't change.

## Rejected

- **UCC12050 isolated DC-DC from the safe 5 V.** Its peak efficiency is 60 %, and much lower at a 50 mW load, so standby would get worse. It would also be a fifth part across the barrier.
- **KP3310 with a 5 kW TVS.** It survives surges but can't power the hot side (section 2).

## Still to confirm

- **Surge level.** Ask the test lab which level applies (1 or 2 kV L–N under the EMC immunity standard). The design above passes 4 kV.
- **MOV model at high current.** The 0.15 Ω bulk resistance is an estimate; check it against the MOV maker's V–I curve at 1 kA.
