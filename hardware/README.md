# Hardware

EVT1 schematics for the Smart Wall Socket. **Draft for engineering review, not a release.**

| Path | What it is |
|---|---|
| `evt1/rear/` | Rear board: hot side, barrier crossing, safe zone (KiCad project `sws-rear`) |
| `evt1/front/` | Front board: SELV only (KiCad project `sws-front`) |
| `evt1/lib/sws.kicad_sym` | Project symbol library |
| `evt1/REVIEW.md` | Decisions taken, open items, what to check |
| `tools/evt1_design.py` | The design as data: parts, values, nets |
| `tools/gen.py` | Writes the KiCad files, PDFs come from `kicad-cli` |
| `tools/verify.py` | Checks the exported netlist against the design and runs the safety rules |

Each project folder also holds the schematic PDF, the KiCad netlist and two BOMs: a full one, and one in JLCPCB's assembly format.

## Regenerate

```sh
python3 hardware/tools/gen.py
python3 hardware/tools/verify.py      # must print "0 errors"
for b in rear front; do
  kicad-cli sch export pdf -o hardware/evt1/$b/sws-$b-schematic.pdf hardware/evt1/$b/sws-$b.kicad_sch
  kicad-cli sch export netlist -o hardware/evt1/$b/sws-$b.net hardware/evt1/$b/sws-$b.kicad_sch
done
```

The files are KiCad 7 format (the newest available in the build environment). KiCad 8 opens them and upgrades them on save. Once you start editing in KiCad, treat the KiCad files as the source and stop regenerating.

## How the drawing is built

Every pin carries a net label on its end; there are no wires. That makes the sheets read like a netlist rather than a flow diagram, but it means the drawing cannot drift from the design data: `verify.py` exports the netlist with `kicad-cli` and compares it with the data net by net.

`verify.py` also enforces:

- No net with only one pin.
- Every power input is driven by a source or a PWR_FLAG.
- No net has two outputs.
- Only U5 (isolator), PS1 (LD03), K1 and K2 (relays) touch both mains and safe nets.
- The board-to-board header carries no mains net and has the same pin map on both boards.
- The ESP32 pads match the GPIO map the firmware will use.

## Safety

The rear board's hot-side ground is the **live** busbar (`L_BUS`). Never connect a scope ground or an earthed instrument to it. Bench work on a powered rear board needs an isolation transformer, an RCD and the rules in `docs/proto0-bench-guide.md`.
