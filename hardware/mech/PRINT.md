# EVT1 enclosure v0.1: print sheet

For the print service in Accra. The STL files are in `out/`, in millimetres, in assembly position: orient each one as the Orientation section says. The STEP files beside them are for anyone who needs to edit them.

**These parts are for the bench and the test lab only, never for a socket installed live in a wall.** The 8 mm gap between mains and low voltage is met in air, so printed plastic is never relied on as insulation.

## Parts

Quantities are for one socket. Print **3 sets**.

| Part | File | Qty | Material | Process |
|---|---|---|---|---|
| Faceplate | `faceplate.stl` | 1 | FR PC/ABS (see below). For looks: flame-retardant SLA resin, sanded and painted matte white | FDM or SLA |
| Inner frame | `inner_frame.stl` | 1 | FR PC/ABS | FDM |
| Contact carriers | `carrier_left.stl`, `carrier_right.stl` | 1 each | FR PC/ABS | FDM. **Do not print yet:** these are placeholders until the donor socket is measured (v0.2) |
| Light guides | `light_guide_left.stl`, `light_guide_right.stl` | 1 each | Clear SLA resin | SLA |
| Rear cover | `rear_cover.stl` | 1 | FR PC/ABS | FDM |

## Material: FR PC/ABS, UL94 V-0

For example Spectrum PC/ABS FR V0 or 3DXTech Firewire FR PC/ABS. Spectrum's data sheet gives these figures:

| | Value |
|---|---|
| UL94 rating | V-0 at 1.5 mm and 3.0 mm |
| Glow-wire flammability index | 960 °C |
| Glow-wire ignition | 750 °C at 1.5 mm |
| Heat deflection | 90 °C at 1.8 MPa |
| Nozzle | 240–265 °C |
| Bed | 90–110 °C |
| Cooling fan | 0–25 % |
| Chamber | closed chamber recommended for larger prints |

These ratings come from test specimens. Printed parts may not reach them, which is another reason these parts are for the bench only.

## Settings

| | Value |
|---|---|
| Layer height | 0.15 mm (faceplate), 0.2 mm (others) |
| Walls | 4 perimeters. Every FR PC/ABS wall is at least 1.5 mm, to match the V-0 rating, except under the 0.4 mm-deep L, N, E marks; the light guides (clear resin, 0.06 cm³ each) are the only parts that are not flame-retardant |
| Infill | 100 % for the carriers and the rear cover. 60 % for the frame and the faceplate |
| Tolerance | design is nominal; holes are already sized. Report the printer's measured over- or under-size so I can compensate in v0.2 |

## Orientation

- **Faceplate:** front face down on a smooth bed sheet, so the face takes the sheet's finish. The clip hooks and release slots then print upright, with no supports. SLA: angled about 30°, with supports on the inside only.
- **Inner frame:** flat face down. The posts print upright; the ones for the rear board point up, 16 mm tall.
- **Rear cover:** floor down. The L, N, E marks are recessed into the floor's outer face.
- **Light guides:** the rib vertical, supports on the flange only.

## Hardware (not printed)

- 8 × M2.5 brass heat-set inserts, 3.2 mm hole, 4–5 mm long, pressed into the frame's posts with a soldering iron.
- 8 × M2.5 nylon screws:
  - **Rear board and cover:** 4 screws, 16 mm long, through the rear cover's bosses and the rear board into the posts.
  - **Front board:** 4 screws, 4 mm long.
- 2 × M3.5 box-fixing screws, 25 mm long, through the frame into the back box lugs.
- **Carrier tabs:** they sit on pins on the frame. Fix them with a heat-stake or a drop of cyanoacrylate.

## Checks after printing

- The faceplate clips onto the frame, and comes off with a flat tool in the release slot.
- A BS 1363 plug's earth pin (22.7 mm) passes through the plate and the carrier without touching the rear board. The design leaves 2.3 mm.
- Measure 10 features with calipers and send me the readings. The worst error sets the v0.2 compensation.
