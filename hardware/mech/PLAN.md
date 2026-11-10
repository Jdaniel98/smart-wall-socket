# EVT1 layout and enclosure plan v0.1

Status: **signed off by Daniel, 10 Nov 2026** (decisions in section 10). The PCB outputs are drafts for engineering review, not a release. The printed parts are for bench and lab pre-assessment only.

Scope:
- PCB layout v0.1 of both boards (rear and front), with mechanical outlines;
- the EVT enclosure (faceplate, inner frame, contact carriers, light guides, rear cover), modelled in Python (build123d), exported as STEP and STL, and 3D-printed;
- one shared parameter file, so the boards and the enclosure can't drift apart.

Coordinates throughout: x across the plate (+ to the right, viewed from the front), y up, z out of the wall. z = 0 is the wall surface. Units are mm.

## 1. Safety scope of the printed enclosure

- **Where printed units may be used:** on the bench, on the isolation transformer with a 30 mA RCD, and at a test lab for pre-assessment. **Never installed live in a wall** in a home.
- **What comes from a certified socket:** the contacts and shutters. Printed plastic is not relied on as insulation. Every hot-to-safe distance in this plan is met in air (≥8 mm) without counting on printed walls.
- **Material for parts that touch or surround mains parts:** flame-retardant PC/ABS, UL94 V-0. For example:
  - Spectrum PC/ABS FR V0: V-0 at 1.5 mm, glow-wire flammability index 960 °C, glow-wire ignition 750 °C;
  - 3DXTech Firewire FR PC/ABS: V-0 at 1.5–3 mm.
  
  The faceplate and light guides can be SLA resin, sanded and painted, as the spec says. Use flame-retardant resin if the faceplate holds the shutters.
- **Glow-wire requirement:** IEC 60884-1 / BS 1363-2 test parts holding current-carrying parts at 850 °C and other parts at 650 °C. The lab confirms which parts are tested. A printed part is not the production material. Production is moulded V-0 polycarbonate (spec v0.1).

## 2. Decision needed first: where the outlet contacts come from

Everything else depends on this. Contacts and shutters are safety parts, so they must not be printed.

| Option | What it is | Depth | Verdict |
|---|---|---|---|
| **A. Donor contacts (recommended)** | Buy a certified unswitched twin socket. Move its L, N and E contacts and its shutters into a printed contact carrier. The contact terminals land on the rear board. | Fits the 35 mm box (stack-up in section 4) | Certified contact metal, our geometry. The assembly is not certified, which is fine for EVT. |
| B. Certified modular inserts | Two clip-in BS 1363 modules, e.g. Scolmore MM010WH: 50 × 50 × 25.6 mm, BS 1363-2 | Each insert fills the whole mechanism depth, so the electronics can't sit behind it | Breaks the 35 mm target. Keep it only as a fallback bench rig. |
| C. OEM smart-socket contact kits | Contact sets that Chinese UK-pattern smart-socket makers use | Probably fits | Sourcing and quality unknown. Look into it for DVT and production. |

With option A, the donor's contact positions become inputs to the CAD. I'll send a measurement checklist (or work from photos with a scale). Buy 3 of the same model, from a brand you can buy again in Accra.

## 3. Envelope (fixed by standards)

- **Faceplate:** 146 × 86 mm, about 9 mm proud of the wall. Fixings at 120.6 mm centres, BS 4662 (spec v0.1).
- **Back box opening:**
  - MK steel 2-gang box: 75 × 135 mm;
  - ABB steel 2-gang box: 72 × 132 mm.
  
  Design to a 70 × 130 mm envelope. Notch the boards at the fixing lugs (x = ±60.3 mm on the centre line).
- **Depth:** 35 mm box. Keep at least 10 mm at the back for cable bends (spec v0.1).
- **BS 1363 geometry:**
  - L and N pin centres 22.2 mm apart;
  - the earth pin's centre line 22.2 mm above the L–N line;
  - viewed from the front with earth up, the line aperture is lower right.
- **Outlet pitch:** 68 mm proposed (centres at x = ±34). This is typical for a twin socket; confirm against the donor.

## 4. Depth stack-up (preliminary, set by the donor contacts)

| Item | z from (mm) | z to (mm) | Note |
|---|---|---|---|
| Faceplate front | +9.0 | | 2.0 mm wall, so the inner face is at +7.0 |
| Touch gap | +6.4 | +7.0 | Touch senses through 2.6 mm of plastic and air; the AT42QT1011 works through up to 6 mm |
| Front board (4-layer, 1.6 mm) | +4.8 | +6.4 | LEDs reverse-mounted on its back face, shining forward through cutouts into the light guides |
| ESP32-C6-MINI-1 | +2.4 | +4.8 | On the front board's **back** face. On the front face it would reach +8.8, through the plate's inner face at +7.0 (found in the concept render). |
| Clear gap | +1.6 | +4.8 | 3.2 mm above the tallest rear-board part, but only 0.8 mm under the ESP32. The ESP32 must not sit over the LD03 in plan view; I'll offset them at layout. |
| LD03 top | | +1.6 | 17.6 mm tall, on the rear board's top face |
| Relay tops | | −0.3 | 15.7 mm tall, same face |
| Plug pin tips | | −8.7 | 9.0 − 17.7 mm pin length |
| Rear board (2-layer, 2 oz, 1.6 mm) | −17.6 | −16.0 | Tall parts on top, between and around the outlets. Only SMD parts and terminals underneath. |
| Cable space | −35.0 | −17.6 | 17.4 mm (target ≥10 mm) |

The contacts run from just behind the shutters (about +6) down to the rear board (−16), about 22 mm. That's normal for socket contacts with their terminals, but the donor decides it.

## 5. Plan view (preliminary)

### Rear board

- **Outline:** 128 × 68 mm, notched at the two fixing lugs.
- **Outlet zones:** centres at x = ±34, each roughly 34 × 36 mm (to confirm against the donor). Nothing tall goes there, because the contacts and carriers sit on top.
- **Centre strip (x −15 to +15):**
  - LD03 at the top;
  - K1 and K2 below it, standing vertically, coil ends toward the safe zone;
  - ISO7761 on the barrier, with a 1 mm routed slot under it.
- **Hot side:** the busbar, shunts, BL0939, LNK3204 supply and polarity check, in the end strips and under the outlets on the back face.
- **Safe zone:** a band holding the relay drivers, NTCs (against the relays), the isolator's safe side and the link to the front board. Every hot-to-safe distance is ≥8 mm creepage and clearance, checked in KiCad by net class.

### Front board (SELV only)

- **Outline:** a frame of about 136 × 76 mm in the faceplate cavity, with one cutout per outlet. Each cutout is the contact envelope plus 8 mm, so the board's copper keeps 8 mm from mains metal in air.
- **ESP32-C6-MINI-1:** top centre. The antenna end sits at the top edge in the plate rim, in front of the box opening (z > 0, as spec v0.1 requires), with no copper under or around it.
- **Touch:** one 20 mm electrode centred under each outlet, with a QT1011 beside each.
- **Light lines:** the SK6812MINI-E LEDs in the touch zones, two per outlet.
- **NFC:** the coil antenna in the centre strip, under the plate's NFC mark.

### Board-to-board link

The two boards end up about 20 mm apart. That is too far for the planned 2 × 7, 1.27 mm header pair (J4/J101).

Proposal: a 14-way, 1.0 mm FFC with matching FPC connectors on both boards. It is a small schematic change (J4, J101 and their footprints). It carries +5 V on two conductors: the peak is about 0.6 A with the LEDs and the ESP32 transmitting, against about 1 A per conductor.

## 6. Copper and current path

Path: terminal → L busbar → shunt → TCO → relay COM → relay NO → outlet L contact. Neutral runs from the terminal to both N contacts and to F1.

Track width for 2 oz external copper (IPC-2221):

| Current | 10 °C rise | 20 °C rise |
|---|---|---|
| 13 A (one outlet) | 5.2 mm | 3.4 mm |
| 20 A (shared path) | 9.4 mm | 6.1 mm |

A 9.4 mm track does not fit the strip, and copper loss eats the heat budget. At 60 °C, 30 mm of 6 mm-wide 2 oz track at 20 A dissipates 0.57 W, against 2.3 W for the whole socket. So:

- **Shared live path (terminal to the two shunts):** a soldered tinned-copper bar, 3 × 1.5 mm, 0.27 mΩ per 60 mm, about 0.11 W at 20 A.
- **Neutral:** 2.5 mm² wire links (0.48 mΩ per 60 mm, about 0.19 W at 20 A), never through thin PCB copper.
- **Per-outlet paths:** short, on both layers, stitched, with mask opened and solder added. Aim for 6 mm or more.
- **Shunts:** Kelvin sense traces leave at the net ties, run as a pair to the BL0939 and stay away from the current path.
- **Clearances:** L to N ≥3 mm, with slots where they converge. Relay coil to contact is already 17.6 mm pad to pad. LD03 AC to DC pads is 18.3 mm, so no slot is needed there.

## 7. Enclosure parts

Each part is modelled in build123d, exported as STEP and STL, and rendered.

1. **Faceplate.**
   - Shape: 146 × 86 × 9 mm, gently curved side wall, 1.5 mm edge radius.
   - Outlets: BS 1363 apertures with pockets for the donor shutters.
   - Light and touch: thin translucent light-line windows; a 0.2 mm recessed touch line; the NFC mark.
   - Fixing: clip hooks, plus a release slot on the bottom edge.
2. **Inner frame.**
   - EVT: printed FR PC/ABS, 3 mm, with screw clearance at 120.6 mm. DVT: steel, per the spec.
   - It carries the contact carriers, the standoffs for both boards, and the catches for the faceplate.
3. **Contact carriers (×2).** FR PC/ABS. Each holds a donor L, N and E contact set and its shutter, and shrouds them so the creepage to the front board is ≥8 mm.
4. **Light guides (×2).** Clear resin, fed from the LEDs below.
5. **Rear cover.**
   - Material: FR PC/ABS.
   - It covers the back of the rear board.
   - It has marked L, N and E terminal openings, each terminal taking 3 × 2.5 mm², and cable guides.

Print notes: allow ±0.2 mm for FDM and ±0.1 mm for SLA. Each part gets an orientation chosen for strength along its clips.

## 8. How the work runs

1. **Shared parameters.** `hardware/mech/params.py` holds the envelope, outlet positions, stack-up and donor contact data. The enclosure and the board outlines (Edge.Cuts, holes, keep-outs) are both generated from it.
2. **Placement.** pcbnew (KiCad 7 Python) places footprints from the schematic netlist. Then I place the critical parts myself: mains copper, the bar and wire pads, shunts, barrier slots, the isolator and the antenna.
3. **Routing.**
   - Mains and power copper are drawn by script.
   - Signals go through Freerouting (it runs here), then I clean them up.
   - DRC uses net classes HOT, SAFE and MAINS_HC, with an 8 mm HOT–SAFE rule.
4. **Checks.**
   - DRC must report 0 errors.
   - `verify.py` gains a board check: minimum copper distance from HOT to SAFE ≥8 mm, measured on the board.
   - The board STEPs are merged into the enclosure assembly, with an interference check.
   - Renders of the whole assembly.
5. **Outputs:**
   - Gerbers, drill files, and BOM and CPL for JLCPCB;
   - the assembly STEP and the STLs;
   - a review doc.
   
   Everything goes on a `hw/evt1-layout` branch for your review.

## 9. Schedule (order boards by about 10 Dec)

| Week | Work |
|---|---|
| 11–17 Nov | Your sign-off. You measure the donor socket. I write the parameters, enclosure v0.1 and board outlines. |
| 18–24 Nov | Placement and mains copper. Enclosure v0.2 with a fit check. First print of the faceplate and frame. |
| 25 Nov–1 Dec | Routing, DRC, review package. |
| 2–8 Dec | Your review and the fixes. Gerbers. Order about 10 Dec: JLC 2-layer 2 oz plus 4-layer, about 1 week to build plus 1–2 weeks shipping to Accra. |

## 10. Decisions (signed off by Daniel, 10 Nov 2026)

1. **Outlet contacts:** option A. Contacts and shutters come from a certified unswitched twin socket, fitted into printed carriers. Daniel buys 3 of one model sold in Accra and measures it with `DONOR-CHECKLIST.md`.
2. **Board link:** a 14-way, 1.0 mm FFC with FPC connectors replaces the 2 × 7, 1.27 mm header (J4/J101).
3. **Printing:** a print service in Accra. I supply the STLs plus a sheet of materials and settings.
4. **Front board:** 1.6 mm thick. The ESP32 sits on its back face, offset from the LD03 in plan view.

## Sources

- MK steel back boxes (BS 4662): 2-gang 75 × 135 mm, fixing centres 120.6 mm.
- ABB flush-box dimensions: 2-gang 132 × 72 × 35 mm.
- BS 1363 pin geometry (Wikipedia summary, dimensions.com): 22.2 mm centres, earth 22.2 mm above.
- Scolmore MM010WH module: 50 × 50 × 25.6 mm.
- Spectrum PC/ABS FR V0 TDS; 3DXTech Firewire FR PC/ABS.
- Spec v0.1 sections Space, Industrial design and Insulation.
