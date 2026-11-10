# ADR-0002: Live-only relay switching with a polarity check

- Status: accepted
- Date: 2026-11-10
- Decided by: Daniel Owusu Mensah

## Context

Each outlet of the twin socket is switched by its own 16 A non-latching relay (Hongfa HF115F/005-1HS3AF, second source Omron G5RL-1A-E). The relay can switch the live conductor only, or live and neutral (double-pole).

Heat is the binding constraint: the socket must fit a 35 mm back box and keep its front within 10 °C of room temperature at full load. Spec v0.1 estimates 2.29 W at 13 A + 7 A with single-pole relays.

A second contact of about 5 mΩ in each path adds I²R heat:

| Load | Extra heat from the neutral contact |
|---|---|
| 13 A on one outlet | 13² × 0.005 = 0.85 W |
| 13 A + 7 A | (13² + 7²) × 0.005 = 1.09 W |

That takes the 13 A + 7 A case from about 2.3 W to about 3.4 W (+48%), and double-pole 16 A relays are larger and taller.

The risk with live-only switching: if an installer swaps L and N, the relay switches the neutral, and "off" leaves the appliance live. Reversed polarity is not rare in older Ghanaian wiring.

## Decision

- Switch the **live conductor only**. Neutral stays connected.
- The relay is **functional switching**, never isolation. Isolation for maintenance is the breaker or unplugging, as for any socket.
- The EVT board adds an **earth-referenced reverse-polarity check** at power-on. If L and N are swapped, the socket warns the installer (status light and app) and keeps both outlets off.

## Consequences

- Fits the thermal and depth budgets of spec v0.1.
- The EVT schematic needs a polarity sense circuit on the hot side (high-impedance L–E and N–E sensing), within the reinforced-isolation rules.
- The install card and electrician guide must cover polarity, and the test lab must confirm the approach under GS IEC 60884-2-2 / BS 1363-2:2023.
- Proto 0 (Sonoff Dual R3 v2) is also live-only and has no polarity check: bench wiring must be checked by hand.
