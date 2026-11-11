# Mechanical: enclosure and board outlines

EVT1 enclosure v0.1 and board outlines v0.1, built from one parameter file so the boards and the printed parts can't drift apart. Signed-off plan: `PLAN.md`. Print instructions: `PRINT.md`. Donor socket measurements: `DONOR-CHECKLIST.md`.

| File | What it does |
|---|---|
| `params.py` | Every dimension, each tagged FIXED, DECIDED, PROPOSED or DONOR. Running it prints the depth stack-up and the fit and zoning checks; it exits 1 if any fail, and CI runs it. |
| `enclosure.py` | Builds the faceplate, inner frame, carriers, light guides and rear cover (build123d). Writes STEP and STL to `out/`, plus `out/fit-report.json` with an interference check across all parts, both boards and the tall components. |
| `outlines.py` | Writes `hardware/evt1/{rear,front}/sws-*.kicad_pcb`: outlines, mounting holes, rule areas and the mechanical, zoning and height-limit drawings on the User layers. It overwrites both boards, so it runs only before placement starts. |
| `render.py` | Ray-traced renders (Blender Cycles) into `renders/`: `exploded`, `assembled`, `rear`, `section`. |
| `concept/` | The earlier concept models and renders. Superseded by the files above. |

Regenerate, from the repository root:

```
pip install build123d bpy shapely   # pcbnew comes with KiCad 7
python3 hardware/mech/params.py
python3 hardware/mech/enclosure.py
python3 hardware/mech/outlines.py   # before placement only
for v in exploded assembled rear section; do python3 hardware/mech/render.py $v 64; done
```

## What is placeholder

- Everything tagged DONOR in `params.py`: the carrier envelope, the contact pads and the faceplate apertures. They change when the donor socket is measured.
- The tall parts in the fit model are blocks of the right size at their zoning-v0 positions. Placement replaces them with the real footprints and 3D models.
