# Hardware

EVT1 schematics for the Smart Wall Socket. **Draft for engineering review, not a release.**

| Path | What it is |
|---|---|
| `evt1/rear/` | Rear board, one sheet: hot side, barrier crossing, safe zone (KiCad project `sws-rear`) |
| `evt1/front/` | Front board, one sheet: SELV only (KiCad project `sws-front`) |
| `evt1/lib/sws.kicad_sym` | Project symbol library |
| `evt1/REVIEW.md` | Decisions taken, open items, what to check |
| `tools/evt1_design.py` | The design as data: parts, values, nets |
| `tools/layout.py` | Places each block in its frame and draws the wires with a small grid router |
| `tools/gen.py` | Writes the KiCad files; PDFs come from `kicad-cli` |
| `tools/kicad-theme-paper.json` | Paper colour theme used for the PDFs |
| `tools/verify.py` | Checks the exported netlist against the design and runs the safety rules |

Each project folder also holds the schematic PDF, the KiCad netlist and two BOMs: a full one, and one in JLCPCB's assembly format.

## Regenerate

```sh
python3 hardware/tools/gen.py
python3 hardware/tools/verify.py      # must print "0 errors"
mkdir -p ~/.config/kicad/7.0/colors && cp hardware/tools/kicad-theme-paper.json ~/.config/kicad/7.0/colors/paper.json
for b in rear front; do
  kicad-cli sch export pdf -t paper -o hardware/evt1/$b/sws-$b-schematic.pdf hardware/evt1/$b/sws-$b.kicad_sch
  kicad-cli sch export netlist -o hardware/evt1/$b/sws-$b.net hardware/evt1/$b/sws-$b.kicad_sch
done
```

The files are KiCad 7 format (the newest available in the build environment). KiCad 8 opens them and upgrades them on save. Once you start editing in KiCad, treat the KiCad files as the source and stop regenerating.

## How the drawing is built

Each board is one sheet laid out in columns, and each functional block sits in its own titled frame. On the rear board the columns run hot side, barrier crossing, safe zone, with the barrier drawn as a dashed line.

Inside a block, parts are placed in rows, and each IC has the parts that connect to its left-hand pins on its left. A grid router then draws the nets as wires:

- Rails (GND, the 3.3 V and 5 V rails, and the live hot-side reference `L_BUS`) use power symbols.
- Signals that leave a block end in flag labels.
- Where the router can't find a clean path, it uses a pair of labels instead; this happened on 5 connections across both boards.

`verify.py` exports the netlist with `kicad-cli` and compares it with the design data net by net. Any wire that shorts, splits or misses a pin fails the check.

`verify.py` also enforces:

- No net with only one pin.
- Every power input is driven by a source or a PWR_FLAG.
- No net has two outputs.
- Only U5 (isolator), PS1 (LD03), K1 and K2 (relays) touch both mains and safe nets.
- The board-to-board header carries no mains net and has the same pin map on both boards.
- The ESP32 pads match the GPIO map the firmware will use.

## CI

`.github/workflows/hardware.yml` runs on every push that touches `hardware/`. It installs KiCad 7's `kicad-cli`, runs `verify.py`, and uploads both schematic PDFs as a build artifact. A failed check blocks the PR.

## Safety

The rear board's hot-side ground is the **live** busbar (`L_BUS`). Never connect a scope ground or an earthed instrument to it. Bench work on a powered rear board needs an isolation transformer, an RCD and the rules in `docs/proto0-bench-guide.md`.
