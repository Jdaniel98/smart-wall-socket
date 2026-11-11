#!/usr/bin/env python3
"""
Footprints for hardware/evt1/lib/sws.pretty that are drawn from manufacturer data.
KiCad 7 format. Run: python3 hardware/tools/footprints.py

Drawn here:
  Relay_Omron_G5RL-1A-E   Omron G5RL-1A-E(-HR) PCB layout, bottom view mirrored to top view.
                          Holes: six, Omron 1.3 +/-0.1 dia; rows 7.5, pin 1->3 20.0, 3->4 5.0.
                          Pins: 1, 8 coil; 3, 6 COM; 4, 5 NO (Omron G2RL/G5RL-1A-E convention,
                          cross-checked against the Flux model of G5RL-1A-E-HR DC5).
                          Second source Hongfa HF115F/005-1HS3AF uses a 2.52 mm grid
                          (20.16 / 5.04 mm, rows assumed 7.56). Contact holes are 1.5 mm and
                          placed midway between the two grids so both relays fit; coil holes
                          1.3 mm. Confirm against both drawings before layout release.
  Fuse_Schurter_UMT-H     Schurter UMT-H datasheet: body 15.4 +/-0.2 x 5.35, solder pads 3.75 x 5.6 with a
                          10.0 mm inner gap (pad centres +/-6.875). Cross-checked against two
                          independent KiCad footprints that use the same land.
  Mornsun_LD03-23B        LD03-23BxxR2, 25.4 x 25.4 mm body (height 16.0 in the 2021 datasheet, 17.6 on
                          Mornsun's current product table: plan for 17.6). 2.54 mm grid; pin 1 AC(N),
                          2 AC(L), 4 -Vo, 5 +Vo, no pin 3. Top view: pin 1 at origin, pin 2 at +5.08 y,
                          pin 5 at +20.32 x, pin 4 at (20.32, 10.16); body corner 2.54 outside pin 1.
                          Taken from two independent built designs (OpenEnergyMonitor emonVs, LD05-23B
                          same package; TasmotaFresh LD03-23B03R2), because the Mornsun drawing is a
                          graphic. Confirm with calipers on the first module before layout release.
  LED_SK6812MINI-E_Reverse  OPSCO SK6812MINI-E (LCSC C5149201), reverse mount. Body 3.2 x 2.8 x 1.78;
                          pins 1 VDD, 2 DOUT, 3 GND, 4 DIN; pitch 1.5. Pads on F.Cu, light leaves through
                          the cutout to the back; place the footprint on the side away from the
                          faceplate (flip to B.Cu if the front board's F side faces the faceplate).
                          Cutout 3.6 x 3.2 with R0.5 corners, so a 1.0 mm router bit clears the body
                          corners (a 3.4 x 3.0 cutout with R0.5 corners would hit them). Pads 0.82 x 1.5
                          at +/-2.65, 0.1 mm from the cutout. Pin pattern (seen from the pad side:
                          1 and 2 at +x, 4 and 3 at -x, 1 opposite 4) matches three independent
                          production keyboard footprints and the LCSC/EasyEDA land.
Imported (not generated): ESP32-C6-MINI-1 from espressif/kicad-libraries (CC-BY-SA 4.0 with
the KiCad design exception), see sws.pretty/README.md.
"""
import os, uuid

OUT = os.path.join(os.path.dirname(__file__), "..", "evt1", "lib", "sws.pretty")


_seed = {"name": "", "n": 0}


def u():
    # deterministic tstamps, so regenerating does not churn the files
    _seed["n"] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sws.pretty/{_seed['name']}/{_seed['n']}"))


def emit(name, fn):
    _seed["name"], _seed["n"] = name, 0
    with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
        f.write(fn())


def line(x1, y1, x2, y2, layer, w=0.12):
    return (f'  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}") (tstamp {u()}))')


def rect(x1, y1, x2, y2, layer, w=0.12):
    return "\n".join([line(x1, y1, x2, y1, layer, w), line(x2, y1, x2, y2, layer, w),
                      line(x2, y2, x1, y2, layer, w), line(x1, y2, x1, y1, layer, w)])


def pad_tht(num, x, y, drill, size, shape="circle"):
    return (f'  (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {size:.2f} {size:.2f}) '
            f'(drill {drill:.2f}) (layers "*.Cu" "*.Mask") (tstamp {u()}))')


def pad_smd(num, x, y, w, h, layer="F"):
    return (f'  (pad "{num}" smd roundrect (at {x:.3f} {y:.3f}) (size {w:.2f} {h:.2f}) '
            f'(layers "{layer}.Cu" "{layer}.Paste" "{layer}.Mask") (roundrect_rratio 0.15) (tstamp {u()}))')


def arc(sx, sy, mx, my, ex, ey, layer, w=0.1):
    return (f'  (fp_arc (start {sx:.3f} {sy:.3f}) (mid {mx:.3f} {my:.3f}) (end {ex:.3f} {ey:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}") (tstamp {u()}))')


def round_rect(hx, hy, r, layer, w=0.1):
    """Closed rectangle centred on the origin, half sizes hx, hy, corner radius r."""
    k = r * (1 - 0.70710678)
    out = [line(-hx + r, -hy, hx - r, -hy, layer, w), line(hx, -hy + r, hx, hy - r, layer, w),
           line(hx - r, hy, -hx + r, hy, layer, w), line(-hx, hy - r, -hx, -hy + r, layer, w)]
    out += [arc(hx - r, -hy, hx - k, -hy + k, hx, -hy + r, layer, w),
            arc(hx, hy - r, hx - k, hy - k, hx - r, hy, layer, w),
            arc(-hx + r, hy, -hx + k, hy - k, -hx, hy - r, layer, w),
            arc(-hx, -hy + r, -hx + k, -hy + k, -hx + r, -hy, layer, w)]
    return "\n".join(out)


def text(kind, val, x, y, layer, hide=False):
    h = " hide" if hide else ""
    return (f'  (fp_text {kind} "{val}" (at {x:.2f} {y:.2f}) (layer "{layer}"){h}\n'
            f'    (effects (font (size 1 1) (thickness 0.15))) (tstamp {u()}))')


def relay_g5rl():
    # top view: pin 1 at origin, contact row along +x, second row at -row
    row = 7.53                       # between Omron 7.5 and Hongfa 7.56 (assumed)
    x3, x4 = 20.08, 25.10            # between Omron (20.0, 25.0) and Hongfa (20.16, 25.20)
    pads = [pad_tht("1", 0, 0, 1.3, 2.2, "rect"), pad_tht("8", 0, -row, 1.3, 2.2),
            pad_tht("3", x3, 0, 1.5, 2.8), pad_tht("4", x4, 0, 1.5, 2.8),
            pad_tht("6", x3, -row, 1.5, 2.8), pad_tht("5", x4, -row, 1.5, 2.8)]
    bx1, bx2 = -2.3, -2.3 + 29.0
    by1, by2 = -row / 2 - 6.35, -row / 2 + 6.35
    body = [rect(bx1, by1, bx2, by2, "F.Fab", 0.1), rect(bx1 - 0.15, by1 - 0.15, bx2 + 0.15, by2 + 0.15, "F.SilkS"),
            rect(bx1 - 0.5, by1 - 0.5, bx2 + 0.5, by2 + 0.5, "F.CrtYd", 0.05),
            # coil / contact separation marker on silk (8 mm barrier runs between x = 1.1 and x = 18.7)
            line(10.0, by1 - 0.15, 10.0, by2 + 0.15, "F.SilkS")]
    return "\n".join([
        '(footprint "Relay_Omron_G5RL-1A-E" (version 20221018) (generator pcbnew)',
        '  (layer "F.Cu")',
        '  (descr "Omron G5RL-1A-E(-HR) 16 A SPST-NO, 1 coil 1/8, COM 3/6, NO 4/5; holes widened to fit Hongfa HF115F-1HS3 (2.52 mm grid). Verify both drawings.")',
        '  (tags "relay Omron G5RL Hongfa HF115F")',
        '  (attr through_hole)',
        text("reference", "REF**", 12.0, by1 - 1.5, "F.SilkS"),
        text("value", "Relay_Omron_G5RL-1A-E", 12.0, by2 + 1.5, "F.Fab"),
        text("user", "COIL", 3.2, -row / 2, "F.SilkS"),
        text("user", "COM  NO", 22.6, -row / 2, "F.SilkS"),
        *body, *pads, ")", ""])


def fuse_umt_h():
    px, pw, ph = 6.875, 3.75, 5.6            # Schurter: 10.0 inner gap, pads 3.75 x 5.6
    bx, by = 15.4 / 2, 5.35 / 2
    sy = ph / 2 + 0.2
    return "\n".join([
        '(footprint "Fuse_Schurter_UMT-H" (version 20221018) (generator pcbnew)',
        '  (layer "F.Cu")',
        '  (descr "Schurter UMT-H SMD fuse 5.3 x 16 mm, 277 VAC, 1500 A breaking capacity. Land per Schurter datasheet: pads 3.75 x 5.6, 10.0 inner gap. Pads are mains: 10 mm between them, keep other copper 3 mm away.")',
        '  (tags "fuse Schurter UMT-H 3403")',
        '  (attr smd)',
        text("reference", "REF**", 0, -sy - 1.2, "F.SilkS"),
        text("value", "Fuse_Schurter_UMT-H", 0, sy + 1.2, "F.Fab"),
        text("user", "${REFERENCE}", 0, 0, "F.Fab"),
        rect(-bx, -by, bx, by, "F.Fab", 0.1),
        line(-px + pw / 2 + 0.3, -sy, px - pw / 2 - 0.3, -sy, "F.SilkS"),
        line(-px + pw / 2 + 0.3, sy, px - pw / 2 - 0.3, sy, "F.SilkS"),
        rect(-px - pw / 2 - 0.25, -sy - 0.3, px + pw / 2 + 0.25, sy + 0.3, "F.CrtYd", 0.05),
        pad_smd("1", -px, 0, pw, ph), pad_smd("2", px, 0, pw, ph), ")", ""])


def ld03_23b():
    g = 2.54
    pads = [pad_tht("1", 0, 0, 1.2, 2.0, "rect"), pad_tht("2", 0, 2 * g, 1.2, 2.0),
            pad_tht("5", 8 * g, 0, 1.2, 2.2), pad_tht("4", 8 * g, 4 * g, 1.2, 2.2)]
    x1, y1, x2, y2 = -g, -g, 9 * g, 9 * g
    bar = 4 * g                                  # isolation boundary midway between AC and DC pins
    return "\n".join([
        '(footprint "Mornsun_LD03-23B" (version 20221018) (generator pcbnew)',
        '  (layer "F.Cu")',
        '  (descr "Mornsun LD03-23BxxR2 3 W AC-DC module, 25.4 x 25.4 x 17.6 mm, 2.54 mm grid. 1 AC(N), 2 AC(L), 4 -Vo, 5 +Vo. Straddles the reinforced barrier: AC pins at x = 0, DC pins at x = 20.32 (18.3 mm pad to pad). AC pads 2.0 mm for 3.1 mm L-N clearance. Pin positions from two built designs; confirm on the first module.")',
        '  (tags "Mornsun LD03 AC-DC isolated")',
        '  (attr through_hole)',
        text("reference", "REF**", 4 * g, y1 - 1.5, "F.SilkS"),
        text("value", "Mornsun_LD03-23B", 4 * g, y2 + 1.5, "F.Fab"),
        text("user", "AC", 2.6, 1.0 * g, "F.SilkS"),
        text("user", "DC", 8 * g - 2.6, 2 * g, "F.SilkS"),
        text("user", "BARRIER", bar, 4 * g, "F.Fab"),
        rect(x1, y1, x2, y2, "F.Fab", 0.1),
        rect(x1 - 0.15, y1 - 0.15, x2 + 0.15, y2 + 0.15, "F.SilkS"),
        rect(x1 - 0.5, y1 - 0.5, x2 + 0.5, y2 + 0.5, "F.CrtYd", 0.05),
        line(bar, y1 - 0.15, bar, y2 + 0.15, "F.SilkS"),
        *pads, ")", ""])


def sk6812mini_e():
    cx, cy, r = 1.8, 1.6, 0.5                   # cutout half sizes (3.6 x 3.2), router radius
    px, pp, pw, ph = 2.65, 0.75, 1.5, 0.82      # pad centre x, half pitch, pad length, pad width
    pads = [pad_smd("1", px, -pp, pw, ph), pad_smd("2", px, pp, pw, ph),
            pad_smd("3", -px, pp, pw, ph), pad_smd("4", -px, -pp, pw, ph)]
    ox = px + pw / 2
    return "\n".join([
        '(footprint "LED_SK6812MINI-E_Reverse" (version 20221018) (generator pcbnew)',
        '  (layer "F.Cu")',
        '  (descr "OPSCO SK6812MINI-E addressable RGB LED, reverse mount through a 3.6 x 3.2 mm cutout (R0.5 corners clear the 3.2 x 2.8 body). 1 VDD, 2 DOUT, 3 GND, 4 DIN, pitch 1.5. Pads on F.Cu, light exits on the B side. LCSC C5149201.")',
        '  (tags "LED RGB addressable SK6812 reverse mount")',
        '  (attr smd)',
        text("reference", "REF**", 0, -cy - 1.2, "F.SilkS"),
        text("value", "SK6812MINI-E", 0, cy + 1.2, "F.Fab"),
        rect(-1.6, -1.4, 1.6, 1.4, "F.Fab", 0.1),
        round_rect(cx, cy, r, "Edge.Cuts", 0.1),
        # pin 1 marker beside pad 1 on silk
        line(ox + 0.35, -pp - 0.41, ox + 0.35, -pp + 0.41, "F.SilkS", 0.15),
        rect(-ox - 0.25, -cy - 0.25, ox + 0.6, cy + 0.25, "F.CrtYd", 0.05),
        *pads, ")", ""])


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("Relay_Omron_G5RL-1A-E", relay_g5rl), ("Fuse_Schurter_UMT-H", fuse_umt_h),
                     ("Mornsun_LD03-23B", ld03_23b), ("LED_SK6812MINI-E_Reverse", sk6812mini_e)):
        emit(name, fn)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
