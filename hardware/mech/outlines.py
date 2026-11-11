"""EVT1 board outlines v0.1, built from params.py into KiCad 7 boards.

Writes hardware/evt1/rear/sws-rear.kicad_pcb and hardware/evt1/front/sws-front.kicad_pcb with:
  Edge.Cuts   board outline, notches, outlet cutouts, antenna notch
  H1-H4       2.7 mm mounting holes (KiCad MountingHole footprint)
  rule areas  no copper around the mounting holes and beside the ESP32 antenna; no B-side
              footprints on the front board over the LD03
  User.1      mechanical: carrier envelopes, contact pins, fixing screws, frame posts, terminal, tall parts
  User.2      zoning v0: the safe island and the 8 mm band around it (rear)
  User.3      height limits (front B side)
  Cmts.User   fab notes and status
No parts are placed and nothing is routed: that is the placement step. Re-running this
overwrites both board files, so run it only before placement starts.

    python3 hardware/mech/outlines.py
"""

import os
import sys

import pcbnew
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OX, OY = 100.0, 100.0          # KiCad origin offset: board centre at (100, 100) mm
FP_LIB = "/usr/share/kicad/footprints/MountingHole.pretty"
L = dict(edge=pcbnew.Edge_Cuts, mech=pcbnew.User_1, zone=pcbnew.User_2, height=pcbnew.User_3,
         cmts=pcbnew.Cmts_User, fsilk=pcbnew.F_SilkS)


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    """Global (y up) to KiCad (y down, offset)."""
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY - y))


def rrect(w, h, r, x=0.0, y=0.0):
    return box(x - w / 2 + r, y - h / 2 + r, x + w / 2 - r, y + h / 2 - r).buffer(r, quad_segs=8)


def rect(x0, y0, x1, y1):
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def add_poly(board, poly, layer, width=0.1):
    for ring in [poly.exterior, *poly.interiors]:
        cs = list(ring.coords)
        for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pt(x0, y0))
            s.SetEnd(pt(x1, y1))
            s.SetLayer(layer)
            s.SetWidth(mm(width))
            board.Add(s)


def add_outline(board, shape):
    """Edge.Cuts: every ring of the (multi)polygon becomes a closed cut."""
    for poly in getattr(shape, "geoms", [shape]):
        add_poly(board, poly, L["edge"], 0.05)


def add_text(board, txt, x, y, layer, size=1.2, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * (0.2 if bold else 0.12)))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)


def rule_area(board, poly, layers, name, copper=True, footprints=False, pads=None):
    zn = pcbnew.ZONE(board)
    zn.SetIsRuleArea(True)
    zn.SetZoneName(name)
    ls = pcbnew.LSET()
    for la in layers:
        ls.AddLayer(la)
    zn.SetLayerSet(ls)
    zn.SetDoNotAllowCopperPour(copper)
    zn.SetDoNotAllowTracks(copper)
    zn.SetDoNotAllowVias(copper)
    zn.SetDoNotAllowPads(copper if pads is None else pads)
    zn.SetDoNotAllowFootprints(footprints)
    o = zn.Outline()
    o.NewOutline()
    for x, y in list(poly.exterior.coords)[:-1]:
        o.Append(mm(OX + x), mm(OY - y))
    board.Add(zn)


def holes(board, positions, keepout_d, layers):
    for i, (x, y) in enumerate(positions, 1):
        fp = pcbnew.FootprintLoad(FP_LIB, "MountingHole_2.7mm_M2.5")
        fp.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_2.7mm_M2.5"))
        fp.SetReference(f"H{i}")
        fp.SetValue("M2.5 nylon")
        fp.SetPosition(pt(x, y))
        board.Add(fp)
        rule_area(board, Point(x, y).buffer(keepout_d / 2, quad_segs=8), layers, f"hole H{i}", pads=False)


def new_board(layers):
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(layers)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    en = b.GetEnabledLayers()
    for la in (pcbnew.User_1, pcbnew.User_2, pcbnew.User_3):
        en.AddLayer(la)
    b.SetEnabledLayers(en)
    b.SetLayerName(pcbnew.User_1, "Mech")
    b.SetLayerName(pcbnew.User_2, "Zoning")
    b.SetLayerName(pcbnew.User_3, "HeightLimits")
    return b


def notes(board, lines, x, y):
    for i, line in enumerate(lines):
        add_text(board, line, x, y - i * 2.2, L["cmts"], 1.2, bold=(i == 0))


# ----------------------------------------------------------------------------------------------
def rear_shape():
    R = P.REAR
    w, h = R["w"].v, R["h"].v
    nd, nh = R["notch"].v
    s = rrect(w, h, R["corner_r"].v)
    for sgn in (-1, 1):
        s = s.difference(rect(sgn * (w / 2 - nd), -nh / 2, sgn * (w / 2 + 1), nh / 2))
    return s


def front_shape():
    F = P.FRONT
    s = rrect(F["w"].v, F["h"].v, F["corner_r"].v)
    m = F["cutout_margin"].v
    cuts = [rrect(P.CARRIER["w"].v + 2 * m, P.CARRIER["h"].v + 2 * m, F["cutout_r"].v, cx, cy) for cx, cy in P.OUTLETS]
    cuts += [Point(sx, 0).buffer(F["access_d"].v / 2, quad_segs=8) for sx in (-P.FIX_PITCH.v / 2, P.FIX_PITCH.v / 2)]
    s = s.difference(unary_union(cuts))
    ex, _ = P.ESP32["centre"].v
    ew, _ = P.ESP32["size"].v
    al, am = P.ESP32["antenna_len"].v, P.ESP32["notch_margin"].v
    s = s.difference(rect(ex - ew / 2 - am, -F["h"].v / 2 - 1, ex + ew / 2 + am, -F["h"].v / 2 + al))
    return s


def mech_common(board):
    """Carrier envelopes, pin centres and fixing screws, the same on both boards."""
    for cx, cy in P.OUTLETS:
        x0, y0, x1, y1 = P.carrier_box(cx, cy)
        add_poly(board, rect(x0, y0, x1, y1), L["mech"])
        for k, (px, py) in P.pins(cx, cy).items():
            add_poly(board, Point(px, py).buffer(0.8, quad_segs=4), L["mech"])
            add_text(board, k, px + 1.2, py + 0.5, L["mech"], 1.0)
        add_text(board, "CARRIER (DONOR)", x0 + 1, y1 - 1.5, L["mech"], 1.0)
    for sx in (-P.FIX_PITCH.v / 2, P.FIX_PITCH.v / 2):
        add_poly(board, Point(sx, 0).buffer(P.FIX_HEAD_D.v / 2, quad_segs=8), L["mech"])
        add_text(board, "M3.5 box screw", sx - 6, -5.5, L["mech"], 0.9)


def build_rear():
    b = new_board(2)
    shape = rear_shape()
    add_outline(b, shape)
    holes(b, P.REAR["holes"].v, P.REAR["hole_keepout_d"].v, [pcbnew.F_Cu, pcbnew.B_Cu])
    mech_common(b)
    rt = P.Z["rear_top"].v
    for name, (w, h) in (("ld03", (25.4, 25.4)), ("k1", (29.0, 12.7)), ("k2", (29.0, 12.7)), ("j4", (6.54, 21.9))):
        x, y, _ = P.PLACE[name].v
        add_poly(b, rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2), L["mech"])
        add_text(b, name.upper(), x - w / 2 + 0.8, y + h / 2 - 1.6, L["mech"], 1.0)
    x, y, _ = P.PLACE["terminal"].v
    add_poly(b, rect(x - 16.5, y - 5.5, x + 16.5, y + 5.5), L["mech"])
    add_text(b, "TERMINAL L N E (B side, top entry)", x - 16, y + 7, L["mech"], 1.0)
    x, y, _ = P.PLACE["u5"].v
    add_poly(b, rect(x - 5.15, y - 3.75, x + 5.15, y + 3.75), L["mech"])
    add_poly(b, rect(x - 0.5, y - 4.5, x + 0.5, y + 4.5), L["mech"])
    add_text(b, "U5 (B side), 1 mm slot", x - 5, y + 5, L["mech"], 0.9)
    # zoning v0
    island = Polygon(P.SAFE_ISLAND.v)
    add_poly(b, island, L["zone"], 0.2)
    band = island.buffer(P.HOT_SAFE.v, join_style=2).intersection(shape)
    add_poly(b, band, L["zone"], 0.1)
    add_text(b, "SAFE (SELV) island, zoning v0", -11.5, -31.5, L["zone"], 1.1, bold=True)
    add_text(b, "outer line: 8 mm from the island. No hot copper inside it.", -11.5, -33.0, L["zone"], 0.8)
    add_text(b, "HOT (mains-referenced)", -62, -16, L["zone"], 1.1, bold=True)
    add_text(b, "everywhere outside the island", -62, -17.6, L["zone"], 0.8)
    notes(b, [
        "SWS rear board EVT1, outline v0.1 (DRAFT FOR REVIEW, not a release)",
        f"2 layers, 2 oz copper, 1.6 mm FR-4. {P.REAR['w'].v:.0f} x {P.REAR['h'].v:.0f} mm. Generated from hardware/mech/params.py",
        f"Top face at z = {rt} mm (16 mm behind the wall). Tall parts on F side; B side <= {P.H['b_side_max'].v} mm except the terminal",
        "Hot to safe >= 8 mm creepage and clearance (reinforced). L to N >= 3 mm, slots where they converge",
        "Carrier envelopes and contact pads are placeholders until the donor socket is measured",
    ], -64, -38)
    return b


def build_front():
    b = new_board(4)
    shape = front_shape()
    add_outline(b, shape)
    holes(b, P.FRONT["holes"].v, P.FRONT["hole_keepout_d"].v,
          [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu])
    mech_common(b)
    # antenna keep-out: beside the notch, all copper layers, no footprints
    F = P.FRONT
    ex, ey = P.ESP32["centre"].v
    ew, eh = P.ESP32["size"].v
    al, am = P.ESP32["antenna_len"].v, P.ESP32["notch_margin"].v
    y_edge = -F["h"].v / 2
    ant = rect(ex - ew / 2 - 2 * am, y_edge, ex + ew / 2 + 2 * am, y_edge + al + 0.5).intersection(shape)
    for poly in getattr(ant, "geoms", [ant]):
        rule_area(b, poly, [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu], "antenna", footprints=True)
    add_poly(b, rect(ex - ew / 2, ey - eh / 2, ex + ew / 2, ey + eh / 2), L["mech"])
    add_text(b, "U101 ESP32-C6-MINI-1 (B side), antenna to the edge", ex - ew / 2, ey + eh / 2 + 1.5, L["mech"], 0.9)
    jx, jy, _ = P.J101.v
    add_poly(b, rect(jx - 3.27, jy - 10.95, jx + 3.27, jy + 10.95), L["mech"])
    add_text(b, "J101 (B side), over J4", jx + 4, jy, L["mech"], 0.9)
    # touch zones, light lines, LEDs, NFC
    for cx, cy in P.TOUCH["centres"].v:
        ew_, eh_, gap_ = P.TOUCH["electrode"].v
        for sgn in (-1, 1):  # electrode in two halves, ganged, with the light line between them
            add_poly(b, rect(cx - ew_ / 2, cy + sgn * gap_ / 2, cx + ew_ / 2, cy + sgn * eh_ / 2), L["mech"])
        ly = P.LIGHT["y"].v
        add_poly(b, rect(cx - P.LIGHT["length"].v / 2, ly - 0.3, cx + P.LIGHT["length"].v / 2, ly + 0.3), L["mech"])
        for s in (-1, 1):
            lx = cx + s * P.LIGHT["led_dx"].v
            add_poly(b, rect(lx - 1.8, ly - 1.6, lx + 1.8, ly + 1.6), L["mech"])
        add_text(b, "touch electrode (F), light line, 2 LEDs (B)", cx - 10, cy - 8.2, L["mech"], 0.7)
    nx, ny = P.NFC["centre"].v
    nw, nh = P.NFC["coil"].v
    add_poly(b, rect(nx - nw / 2, ny - nh / 2, nx + nw / 2, ny + nh / 2), L["mech"])
    add_text(b, "NFC coil", nx - nw / 2 + 0.8, ny + nh / 2 - 1.6, L["mech"], 0.9)
    # height limits on the B side, from the rear board's tall parts
    gap = P.Z["front_bot"].v - (P.Z["rear_top"].v + P.H["ld03"].v)
    x, y, _ = P.PLACE["ld03"].v
    over = rect(x - 13.2, y - 13.2, x + 13.2, y + 13.2).intersection(shape)
    for poly in getattr(over, "geoms", [over]):
        rule_area(b, poly, [pcbnew.B_Cu], "no B-side parts over LD03", copper=False, footprints=True)
        add_poly(b, poly, L["height"])
    add_text(b, f"B side: no parts ({gap:.1f} mm to the LD03 top)", x - 12.5, y - 15, L["height"], 0.9)
    gap_r = P.Z["front_bot"].v - (P.Z["rear_top"].v + P.H["relay"].v)
    for k in ("k1", "k2"):
        x, y, _ = P.PLACE[k].v
        over = rect(x - 15, y - 6.85, x + 15, y + 6.85).intersection(shape)
        for poly in getattr(over, "geoms", [over]):
            add_poly(b, poly, L["height"])
        add_text(b, f"B side <= {gap_r - 0.3:.1f} mm over {k.upper()}", x - 14, y - 5.5, L["height"], 0.7)
    notes(b, [
        "SWS front board EVT1, outline v0.1 (DRAFT FOR REVIEW, not a release)",
        f"4 layers, 1.6 mm. {F['w'].v:.0f} x {F['h'].v:.0f} mm. SELV only. Generated from hardware/mech/params.py",
        "Outlet cutouts = carrier envelope + 8 mm, so all copper here is >= 8 mm from the mains contacts",
        "Antenna: board cut away below the antenna, no copper beside it (Espressif). 15 mm metal clearance is not",
        "possible over a steel box at 9 mm: measure Wi-Fi in a steel box at EVT; fallback ESP32-C6-MINI-1U",
    ], -68, -42)
    return b


def main():
    for name, fn in (("rear", build_rear), ("front", build_front)):
        b = fn()
        path = os.path.join(ROOT, "hardware", "evt1", name, f"sws-{name}.kicad_pcb")
        b.Save(path)
        print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
