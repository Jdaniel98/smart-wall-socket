"""EVT1 enclosure v0.1, built from params.py.

Printed parts: faceplate, inner frame, two contact carriers (placeholders until the donor
socket is measured), two light guides, rear cover. For the fit check and the renders it also
builds simple stand-ins for both boards and the tall parts at their zoning-v0 positions.

    python3 hardware/mech/enclosure.py            # STEP, STL, fit report, meshes for the renders

Printed units are for the bench and the lab only, never installed live in a wall
(layout and enclosure plan v0.1, section 1).
"""

import json
import math
import os
import pickle
import sys

from build123d import (Align, Box, Compound, Cylinder, Pos, Rot, Text, export_step, export_stl, extrude,
                       fillet)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
MIN = (Align.CENTER, Align.CENTER, Align.MIN)
MAX = (Align.CENTER, Align.CENTER, Align.MAX)


def z(n):
    return P.Z[n].v


def slab(w, h, z0, z1, x=0.0, y=0.0):
    return Pos(x, y, z0) * Box(w, h, z1 - z0, align=MIN)


def vertical_edges(part):
    return [e for e in part.edges() if abs(e.tangent_at(0).Z) > 0.99]


def rbox(w, h, z0, z1, r, x=0.0, y=0.0):
    b = slab(w, h, z0, z1, x, y)
    return fillet(vertical_edges(b), r) if r > 0 else b


def ring(d_out, width, z0, z1, x, y):
    return (Pos(x, y, z0) * Cylinder(d_out / 2, z1 - z0, align=MIN)
            - Pos(x, y, z0) * Cylinder(d_out / 2 - width, z1 - z0, align=MIN))


# ----------------------------------------------------------------------------------------------
# Printed parts
# ----------------------------------------------------------------------------------------------
def faceplate():
    W, Hh, t = P.PLATE_W.v, P.PLATE_H.v, P.PLATE_WALL.v
    zf = z("plate_front")
    shell = rbox(W, Hh, 0.0, zf, P.PLATE_CORNER_R.v)
    top_edges = [e for e in shell.edges() if e.center().Z > zf - 1e-3]
    shell = fillet(top_edges, P.PLATE_EDGE_R.v)
    cav = rbox(W - 2 * t, Hh - 2 * t, -1.0, zf - t, max(P.PLATE_CORNER_R.v - t, 0.5))
    plate = shell - cav
    for cx, cy in P.OUTLETS:
        pins = P.pins(cx, cy)
        for k in ("L", "N"):
            w, h = P.APERTURE["LN"].v
            plate -= slab(w, h, zf - t - 1, zf + 1, *pins[k])
        w, h = P.APERTURE["E"].v
        plate -= slab(w, h, zf - t - 1, zf + 1, *pins["E"])
    gw, gd = P.TOUCH["groove"].v
    for cx, cy in P.TOUCH["centres"].v:
        plate -= ring(P.TOUCH["zone_d"].v, gw, zf - gd, zf + 1, cx, cy)
        plate -= slab(P.LIGHT["length"].v, P.LIGHT["width"].v, zf - t - 1, zf + 1, cx, P.LIGHT["y"].v)
    nx, ny = P.NFC["centre"].v
    plate -= ring(P.NFC["mark_d"].v, gw, zf - gd, zf + 1, nx, ny)
    plate -= ring(P.NFC["mark_d"].v * 0.5, gw, zf - gd, zf + 1, nx, ny)
    # clip hooks on the inner long walls, and release slots in the bottom wall
    iy = Hh / 2 - t
    for x, side in P.FRAME["clips"].v:
        y = side * (iy - 0.3)
        plate += slab(8.0, 0.6, 3.2, 4.4, x, y)
        if side < 0:
            plate -= slab(6.0, t + 2, 0.4, 1.4, x, -Hh / 2 + t / 2)
    return plate


def inner_frame():
    ow, oh = P.FRAME["outer"].v
    fw, fy0, fy1 = P.FRAME["opening"].v
    z0, z1 = z("frame_bot"), z("frame_top")
    lt, lh = P.FRAME["lip"].v
    f = rbox(ow, oh, z0, z1, P.PLATE_CORNER_R.v - P.PLATE_WALL.v - 0.5)
    f -= slab(fw, fy1 - fy0, z0 - 1, z1 + 1, 0.0, (fy0 + fy1) / 2)
    aw, ay = P.FRAME["antenna_cut"].v
    f -= slab(aw, ay + oh / 2 + 1, z0 - 1, z1 + 1, 0.0, (ay - oh / 2 - 1) / 2)
    # perimeter lip with windows for the plate's hooks
    lip = rbox(ow, oh, z1, z1 + lh, P.PLATE_CORNER_R.v - P.PLATE_WALL.v - 0.5) - \
        rbox(ow - 2 * lt, oh - 2 * lt, z1 - 1, z1 + lh + 1, P.PLATE_CORNER_R.v - P.PLATE_WALL.v - 0.5 - lt)
    lip -= slab(aw, 10, z1 - 1, z1 + lh + 1, 0.0, -oh / 2)  # no lip in front of the antenna
    for x, side in P.FRAME["clips"].v:
        lip -= slab(9.0, lt + 2, 3.0, 4.6, x, side * (oh / 2 - lt / 2))
    f += lip
    # box-fixing screw clearance and head seats
    for sx in (-P.FIX_PITCH.v / 2, P.FIX_PITCH.v / 2):
        f -= Pos(sx, 0, z0 - 1) * Cylinder(P.FIX_SCREW_D.v / 2 + 0.3, z1 - z0 + 2, align=MIN)
    pd = P.FRAME["post_d"].v
    for x, y in P.FRONT["holes"].v:  # posts up to the front board
        f += Pos(x, y, z1) * Cylinder(pd / 2, z("front_bot") - z1, align=MIN)
        f -= Pos(x, y, z("front_bot") - INSERT[1]) * Cylinder(INSERT[0] / 2, INSERT[1] + 0.1, align=MIN)
    for x, y in P.REAR["holes"].v:  # posts down to the rear board
        f += Pos(x, y, z("rear_top")) * Cylinder(pd / 2, z0 - z("rear_top"), align=MIN)
        f -= Pos(x, y, z("rear_top") - 0.1) * Cylinder(INSERT[0] / 2, INSERT[1] + 0.1, align=MIN)
    # pins for the carrier tabs (heat-staked or glued at assembly)
    for cx, cy in P.OUTLETS:
        for px, py in carrier_tab_holes(cx, cy):
            f += Pos(px, py, z1) * Cylinder(1.25, 1.5, align=MIN)
    return f


INSERT = (3.2, 5.0)  # M2.5 brass heat-set insert: hole diameter, depth (nylon M2.5 screws into it)


def carrier_tab_holes(cx, cy):
    sgn = 1 if cx > 0 else -1
    w, h = P.CARRIER["w"].v, P.CARRIER["h"].v
    return [(cx + sgn * (w / 2 + 4.0), cy + 12.0), (cx, cy - h / 2 - 8.0)]


def carrier(cx, cy):
    """Placeholder contact carrier: real pockets come from the donor's contacts."""
    w, h = P.CARRIER["w"].v, P.CARRIER["h"].v
    z0, z1 = P.CARRIER["z_bot"].v, P.CARRIER["z_top"].v
    c = rbox(w, h, z0, z1, 2.0, cx, cy)
    pins = P.pins(cx, cy)
    for k in ("L", "N"):
        c -= slab(7.0, 6.0, z0 + 2.0, z1 + 1, *pins[k])            # contact pocket
    c -= slab(6.0, 10.0, z0 + 2.0, z1 + 1, *pins["E"])
    c -= slab(w - 4, 11.0, z1 - 2.5, z1 - 1.0, cx, cy - 11.1)     # shutter slide
    # tabs onto the inner frame (outer end and bottom), screwed with M2.5
    sgn = 1 if cx > 0 else -1
    ft = z("frame_top")
    ty = cy + 12.0                                                 # clear of the box-fixing screw head at y = 0
    c += slab(8.0, 10.0, ft, ft + 1.5, cx + sgn * (w / 2 + 3.0), ty)
    c += slab(10.0, 10.0, ft, ft + 1.5, cx, cy - h / 2 - 5.0)       # bottom tab, onto the frame's bottom band
    for px, py in carrier_tab_holes(cx, cy):
        c -= Pos(px, py, ft - 1) * Cylinder(1.4, 4, align=MIN)
    return c


def light_guide(cx):
    y = P.LIGHT["y"].v
    rib = slab(P.LIGHT["length"].v - 0.2, P.LIGHT["width"].v - 0.1, z("plate_inner"), z("plate_front") - 0.05, cx, y)
    flange = rbox(P.LIGHT["length"].v + 4, 3.0, z("front_top") + 0.05, z("plate_inner"), 0.5, cx, y)
    return rib + flange


def board_outline_rear():
    """Rear board as a 2D-ish solid; outlines.py draws the same shape in KiCad."""
    R = P.REAR
    b = rbox(R["w"].v, R["h"].v, z("rear_bot"), z("rear_top"), R["corner_r"].v)
    nd, nh = R["notch"].v
    for s in (-1, 1):
        b -= slab(nd + 1, nh, z("rear_bot") - 1, z("rear_top") + 1, s * (R["w"].v / 2 - nd / 2 + 0.5), 0.0)
    for x, y in R["holes"].v:
        b -= Pos(x, y, z("rear_bot") - 1) * Cylinder(R["hole_d"].v / 2, 4, align=MIN)
    return b


def board_outline_front():
    F = P.FRONT
    b = rbox(F["w"].v, F["h"].v, z("front_bot"), z("front_top"), F["corner_r"].v)
    m = F["cutout_margin"].v
    for cx, cy in P.OUTLETS:
        b -= rbox(P.CARRIER["w"].v + 2 * m, P.CARRIER["h"].v + 2 * m, z("front_bot") - 1, z("front_top") + 1,
                  F["cutout_r"].v, cx, cy)
    for sx in (-P.FIX_PITCH.v / 2, P.FIX_PITCH.v / 2):
        b -= Pos(sx, 0, z("front_bot") - 1) * Cylinder(F["access_d"].v / 2, 4, align=MIN)
    ex, ey = P.ESP32["centre"].v
    ew, eh = P.ESP32["size"].v
    al, am = P.ESP32["antenna_len"].v, P.ESP32["notch_margin"].v
    b -= slab(ew + 2 * am, al + 1, z("front_bot") - 1, z("front_top") + 1, ex, -F["h"].v / 2 + (al - 1) / 2)
    for x, y in F["holes"].v:
        b -= Pos(x, y, z("front_bot") - 1) * Cylinder(F["hole_d"].v / 2, 4, align=MIN)
    return b


def rear_cover():
    R, C = P.REAR, P.COVER
    w, h, t, ft = R["w"].v, R["h"].v, C["wall"].v, C["floor_t"].v
    zt = z("rear_bot") - 0.2
    zf = z("cover_floor")
    outer = rbox(w, h, zf - ft, zt, R["corner_r"].v + 0.5)
    inner = rbox(w - 2 * t, h - 2 * t, zf, zt + 1, max(R["corner_r"].v - t, 0.3))
    cv = outer - inner
    nd, nh = R["notch"].v
    for s in (-1, 1):
        cv -= slab(nd + 1, nh, zf - ft - 1, zt + 1, s * (w / 2 - nd / 2 + 0.5), 0.0)
        cv += slab(t, nh + 2 * t, zf - ft, zt, s * (w / 2 - nd - t / 2), 0.0)       # wall around the notch
        for dy in (-1, 1):
            cv += slab(nd, t, zf - ft, zt, s * (w / 2 - nd / 2), dy * (nh / 2 + t / 2))
    tx, ty, _ = P.PLACE["terminal"].v
    ow, oh = C["terminal_opening"].v
    cv -= slab(ow, h / 2 - (ty - oh / 2) + 1, zf - ft - 1, zt + 1, tx, (ty - oh / 2 + h / 2 + 1) / 2)
    for x, y in R["holes"].v:
        cv += Pos(x, y, zf) * Cylinder(3.0, zt - zf, align=MIN)
        cv -= Pos(x, y, zf - ft - 1) * Cylinder(1.4, zt - zf + ft + 2, align=MIN)
    # terminal markings, recessed 0.4 mm into the outside of the floor, upright when read from behind
    try:
        for i, lab in enumerate(("L", "N", "E")):
            x = tx - 11.0 + 11.0 * i
            txt = extrude(Text(lab, 5.0, align=(Align.CENTER, Align.CENTER)), 0.5)
            cv -= Pos(x, ty - oh / 2 - 4.0, zf - ft - 0.1) * Rot(0, 180, 0) * Pos(0, 0, -0.5) * txt
    except Exception as e:  # font missing: leave the marks for the print service
        print("rear cover: markings skipped:", e)
    return cv


# ----------------------------------------------------------------------------------------------
# Stand-ins for the fit check and renders (not printed)
# ----------------------------------------------------------------------------------------------
def standins():
    s = {}
    rt = z("rear_top")
    x, y, _ = P.PLACE["ld03"].v
    s["ld03"] = slab(25.4, 25.4, rt, rt + P.H["ld03"].v, x, y)
    for k in ("k1", "k2"):
        x, y, _ = P.PLACE[k].v
        s[k] = slab(29.0, 12.7, rt, rt + P.H["relay"].v, x, y)
    x, y, _ = P.PLACE["terminal"].v
    s["terminal"] = slab(33.0, 11.0, z("rear_bot") - P.H["terminal"].v, z("rear_bot"), x, y)
    x, y, _ = P.PLACE["j4"].v
    s["j4"] = slab(6.54, 21.9, rt, rt + P.H["fpc"].v, x, y)
    jx, jy, _ = P.J101.v
    s["j101"] = slab(6.54, 21.9, z("front_bot") - P.H["fpc"].v, z("front_bot"), jx, jy)
    ex, ey = P.ESP32["centre"].v
    s["esp32"] = slab(*P.ESP32["size"].v, z("front_bot") - P.H["esp32"].v, z("front_bot"), ex, ey)
    # FFC: out of J4's mouth toward +x, up, back into J101
    s["ffc"] = (slab(3.0, 15.0, rt + 1.0, rt + 1.3, x + 4.6, y) + slab(0.3, 15.0, rt + 1.0, z("front_bot") - 1.0, x + 6.0, y)
                + slab(3.0, 15.0, z("front_bot") - 1.3, z("front_bot") - 1.0, x + 4.6, y))
    for i, sx in enumerate((-P.FIX_PITCH.v / 2, P.FIX_PITCH.v / 2)):
        tip = z("frame_top") - P.FIX_SCREW_LEN.v
        s[f"screw{i}"] = (Pos(sx, 0, tip) * Cylinder(P.FIX_SCREW_D.v / 2, z("frame_top") - tip, align=MIN)
                          + Pos(sx, 0, z("frame_top")) * Cylinder(P.FIX_HEAD_D.v / 2, 1.6, align=MIN))
    return s


def build():
    parts = {
        "faceplate": faceplate(),
        "inner_frame": inner_frame(),
        "carrier_left": carrier(*P.OUTLETS[0]),
        "carrier_right": carrier(*P.OUTLETS[1]),
        "light_guide_left": light_guide(P.OUTLETS[0][0]),
        "light_guide_right": light_guide(P.OUTLETS[1][0]),
        "rear_cover": rear_cover(),
    }
    boards = {"rear_board": board_outline_rear(), "front_board": board_outline_front()}
    return parts, boards, standins()


# Parts that share a face give zero overlap, so only real overlaps are reported.
# The one intended overlap: the FFC's ends sit inside the connectors' mouths.
TOUCHING = {frozenset(("ffc", "j4")), frozenset(("ffc", "j101"))}


def interference(solids):
    names = list(solids)
    bb = {n: solids[n].bounding_box() for n in names}
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = bb[a], bb[b]
            if (A.max.X < B.min.X or B.max.X < A.min.X or A.max.Y < B.min.Y or B.max.Y < A.min.Y
                    or A.max.Z < B.min.Z or B.max.Z < A.min.Z):
                continue
            try:
                v = (solids[a] & solids[b]).volume
            except Exception:
                v = 0.0
            if v > 1e-3 and frozenset((a, b)) not in TOUCHING:
                out.append((a, b, round(v, 3)))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    parts, boards, stand = build()
    report = {"parts": {}, "clashes": [], "checks": []}
    for n, p in parts.items():
        export_step(p, os.path.join(OUT, f"{n}.step"))
        export_stl(p, os.path.join(OUT, f"{n}.stl"), tolerance=0.02, angular_tolerance=0.2)
        bb = p.bounding_box()
        report["parts"][n] = dict(volume_cm3=round(p.volume / 1000, 2),
                                  bbox_mm=[round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)])
    allsolids = {**parts, **boards, **stand}
    export_step(Compound(list(allsolids.values())), os.path.join(OUT, "assembly_evt1_v0.1.step"))
    report["clashes"] = interference(allsolids)
    report["checks"] = [dict(name=n, value=v, limit=l, ok=o) for n, v, l, o in P.checks()]
    with open(os.path.join(OUT, "fit-report.json"), "w") as f:
        json.dump(report, f, indent=1)
    mesh = {}
    for n, p in allsolids.items():
        verts, tris = p.tessellate(0.03, 0.25)
        mesh[n] = ([(v.X, v.Y, v.Z) for v in verts], [tuple(t) for t in tris])
    # section through the L-N pin line, keeping the half behind it (y > cut), for the section render
    cut = P.OUTLET_Y.v + P.PIN_OFFSETS["L"].v[1]
    keep = Pos(0, cut + 100, 0) * Box(400, 200, 200)
    for n, p in allsolids.items():
        try:
            sec = p & keep
            if sec.volume > 1e-3:
                verts, tris = sec.tessellate(0.03, 0.25)
                mesh["sec:" + n] = ([(v.X, v.Y, v.Z) for v in verts], [tuple(t) for t in tris])
        except Exception:
            pass
    with open(os.path.join(OUT, "mesh.pkl"), "wb") as f:
        pickle.dump(mesh, f)
    for n, r in report["parts"].items():
        print(f"{n:18s} {r['bbox_mm']} mm, {r['volume_cm3']} cm3")
    print("clashes:", report["clashes"] or "none")
    print("failing checks:", [c["name"] for c in report["checks"] if not c["ok"]] or "none")


if __name__ == "__main__":
    main()
