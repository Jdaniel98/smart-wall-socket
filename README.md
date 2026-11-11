# Smart Wall Socket

The first product of **Aether Labs**: a smart twin 13 A wall socket for Ghanaian homes and small businesses on prepaid meters.

- **Protects** appliances: under/over-voltage cut-off with a restore delay after outages, decided on the device.
- **Measures** each outlet: true RMS current, power, power factor and energy.
- **Prices** usage in cedis at current PURC tariffs, and **predicts** when prepaid credit runs out.
- Works with **Apple Home and Google Home** through Matter, and keeps working offline.

A revival and full redesign of the "Keep" smart socket that won the 2021 KNUST Engineering Education Project (KEEP).

## Status

| Stage | State |
|---|---|
| Proto 0: our firmware on a Sonoff Dual R3 v2, bench only | **Firmware v0.1 ready for bench testing** |
| EVT: custom boards (KiCad 8), printed faceplates | Next: schematic after Proto 0 results |
| DVT, PVT, certification (GSA, NCA, Energy Commission, DPC) | 2027 |

## Repository

| Path | What |
|---|---|
| [`firmware/`](firmware/) | ESP-IDF + Matter firmware, host-tested core, provisioning tool |
| [`docs/protocol.md`](docs/protocol.md) | Device ↔ cloud MQTT contract |
| [`docs/proto0-bench-guide.md`](docs/proto0-bench-guide.md) | Safety rules, flashing, pairing, calibration, test plan |
| [`docs/adr/`](docs/adr/) | Decision records |
| [`hardware/`](hardware/) | EVT1 KiCad schematics (draft for review), generator and netlist checks |
| `services/`, `apps/`, `intelligence/` | Coming with the software phases |

## Safety

Mains voltage can kill. Bench work follows the rules in the bench guide: isolation transformer, RCD, closed enclosure, insulated tools, and never alone. No prototype is given to anyone outside the bench until it has passed pre-compliance testing.

## Credits

Original 2021 KEEP team: Daniel Owusu Mensah and four teammates from KNUST Electrical/Electronic Engineering. This repository is a clean rewrite; no v1 code is reused.

© 2026 Aether Labs. All rights reserved.
