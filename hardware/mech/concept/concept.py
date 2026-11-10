from build123d import *
import numpy as np

def outlet_holes(cx, cy):
    # BS 1363: L/N horizontal slots 22.2 apart, earth vertical slot 22.2 above
    h = []
    for sx in (-11.1, 11.1):
        h.append(Pos(cx+sx, cy-11.1, 0) * Box(7.4, 4.8, 40))
    h.append(Pos(cx, cy+11.1, 0) * Box(4.8, 8.8, 40))
    return h

parts = {}
OX = 34.0; OY = 4.0
# faceplate shell 146x86x9 with rounded edges, hollow
HOLES = [h for cx in (-OX, OX) for h in outlet_holes(cx, OY)]   # built outside the builder
with BuildPart() as fp:
    Box(146, 86, 9, align=(Align.CENTER, Align.CENTER, Align.MIN))
    fillet(fp.edges().filter_by(Axis.Z), 6)
    fillet(fp.faces().sort_by(Axis.Z)[-1].edges(), 1.5)
    with Locations((0, 0, -0.01)):
        Box(142, 82, 7.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    for hcut in HOLES:
        add(hcut, mode=Mode.SUBTRACT)
    for cx in (-OX, OX):
        # touch line: 0.2 mm recessed ring, and light-line slot
        with Locations((cx, OY-27, 9)):
            Box(20, 0.6, 0.4, mode=Mode.SUBTRACT)
parts["faceplate"] = (fp.part, (0.97, 0.97, 0.96))
# light lines (translucent strip, glowing)
for i, cx in enumerate((-OX, OX)):
    parts[f"light{i}"] = (Pos(cx, OY-27, 8.65) * Box(20, 0.6, 0.35), (0.55, 0.85, 1.0))
# front board frame
with BuildPart() as fb:
    Box(136, 76, 1.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for cx in (-OX, OX):
        with Locations((cx, OY, 0)):
            Box(50, 52, 10, mode=Mode.SUBTRACT)
parts["front_board"] = (Pos(0, 0, 4.8) * fb.part, (0.15, 0.35, 0.22))
parts["esp32"] = (Pos(0, -38+8.3, 4.8) * Box(13.2, 16.6, 2.4, align=(Align.CENTER, Align.CENTER, Align.MAX)), (0.75, 0.75, 0.78))
pass
# contact carriers (FR PC/ABS, dark grey) with brass contacts
for i, cx in enumerate((-OX, OX)):
    parts[f"carrier{i}"] = (Pos(cx, OY, -16) * Box(34, 36, 22.6, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.30, 0.30, 0.32))
    for sx, sy, w, hgt in ((-11.1, -11.1, 8, 6), (11.1, -11.1, 8, 6), (0, 11.1, 6, 10)):
        parts[f"contact{i}{sx}"] = (Pos(cx+sx, OY+sy, 6.6) * Box(w, hgt, 0.3, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.85, 0.65, 0.25))
# rear board with lug notches
with BuildPart() as rb:
    Box(128, 68, 1.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sx in (-60.3, 60.3):
        with Locations((sx, 0, 0)):
            Box(14, 14, 10, mode=Mode.SUBTRACT)
parts["rear_board"] = (Pos(0, 0, -17.6) * rb.part, (0.10, 0.30, 0.18))
parts["ld03"] = (Pos(0, 21.3, -16) * Box(25.4, 25.4, 17.6, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.12, 0.12, 0.13))
for sx in (-6.5, 6.5):
    parts[f"relay{sx}"] = (Pos(sx, -14.5, -16) * Box(12.7, 29, 15.7, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.15, 0.25, 0.55))
parts["busbar"] = (Pos(-50, -14, -16) * Box(3, 34, 1.5, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.80, 0.45, 0.25))
# FFC link, 14-way 1.0 mm, with FPC connectors on both boards
parts["ffc"] = (Pos(61, -22, -16) * Box(0.3, 15, 20.8, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.92, 0.92, 0.90))
parts["fpc_rear"] = (Pos(59.5, -22, -16) * Box(4, 18, 2, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.85, 0.82, 0.70))
parts["fpc_front"] = (Pos(62.5, -22, 4.8) * Box(4, 18, 2, align=(Align.CENTER, Align.CENTER, Align.MAX)), (0.85, 0.82, 0.70))
# inner frame (printed FR PC/ABS for EVT), screws to the box lugs at 120.6 mm
with BuildPart() as fr:
    Box(141, 81, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    Box(112, 66, 10, mode=Mode.SUBTRACT)
    with Locations((0, -36, 0)):
        Box(20, 12, 10, mode=Mode.SUBTRACT)          # clear of the ESP32 antenna
    with Locations((61, -22, 0)):
        Box(8, 20, 10, mode=Mode.SUBTRACT)           # FFC pass-through
parts["frame"] = (fr.part, (0.22, 0.22, 0.24))
for sx in (-60.3, 60.3):
    parts[f"screw{sx}"] = (Pos(sx, 0, 2.0) * Cylinder(3.2, 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN)), (0.78, 0.78, 0.80))
# mains terminal block on the back of the rear board (L, N, E), top entry
parts["terminal"] = (Pos(0, 26, -17.6) * Box(33, 11, 11, align=(Align.CENTER, Align.CENTER, Align.MAX)), (0.25, 0.42, 0.30))
for i, sx in enumerate((-11, 0, 11)):
    parts[f"term_screw{i}"] = (Pos(sx, 26, -28.6) * Cylinder(2.2, 0.6, align=(Align.CENTER, Align.CENTER, Align.MAX)), (0.80, 0.80, 0.82))
# back box (steel), drawn without its front so we can see in
with BuildPart() as bx:
    Box(137, 77, 35, align=(Align.CENTER, Align.CENTER, Align.MAX))
    Box(135, 75, 34, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
parts["backbox"] = (bx.part, (0.62, 0.64, 0.66))

import pickle
mesh = {}
for k, (p, col) in parts.items():
    verts, tris = p.tessellate(0.05, 0.3)
    V = np.array([[v.X, v.Y, v.Z] for v in verts]); T = np.array(tris)
    mesh[k] = (V, T, col)
pickle.dump(mesh, open("/tmp/render/mesh.pkl", "wb"))
# STEP of the concept assembly
export_step(Compound([p for p, c in parts.values()]), "/tmp/render/concept_assembly.step")
print("ok", sum(len(m[1]) for m in mesh.values()), "triangles")
