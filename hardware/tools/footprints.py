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
Imported (not generated): ESP32-C6-MINI-1 from espressif/kicad-libraries (CC-BY-SA 4.0 with
the KiCad design exception), see sws.pretty/README.md.
"""
import os, uuid

OUT = os.path.join(os.path.dirname(__file__), "..", "evt1", "lib", "sws.pretty")


def u():
    return str(uuid.uuid4())


def line(x1, y1, x2, y2, layer, w=0.12):
    return (f'  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}") (tstamp {u()}))')


def rect(x1, y1, x2, y2, layer, w=0.12):
    return "\n".join([line(x1, y1, x2, y1, layer, w), line(x2, y1, x2, y2, layer, w),
                      line(x2, y2, x1, y2, layer, w), line(x1, y2, x1, y1, layer, w)])


def pad_tht(num, x, y, drill, size, shape="circle"):
    return (f'  (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {size:.2f} {size:.2f}) '
            f'(drill {drill:.2f}) (layers "*.Cu" "*.Mask") (tstamp {u()}))')


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


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "Relay_Omron_G5RL-1A-E.kicad_mod"), "w") as f:
        f.write(relay_g5rl())
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
