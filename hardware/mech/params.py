"""Shared dimensions for the EVT1 boards and enclosure.

One source of truth: `enclosure.py` builds the printed parts from it and
`outlines.py` builds both board outlines, holes and keep-outs from it, so the
two can't drift apart. Run this file to print the stack-up and the fit checks.

Units: mm. Coordinates, viewed from the front with the socket on the wall:
  x  across the plate, + to the right
  y  up the plate
  z  out of the wall; z = 0 is the wall surface (and the back box's front edge)
KiCad boards use the same x and y with y flipped (KiCad y points down).

Every value carries a status:
  FIXED     set by a standard or a part datasheet
  DECIDED   signed off by Daniel (layout and enclosure plan v0.1)
  PROPOSED  my choice, open to Daniel's review
  DONOR     placeholder until the donor socket is measured (DONOR-CHECKLIST.md)
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class V:
    """A value with its status and source."""
    v: object
    status: str
    note: str = ""


# --------------------------------------------------------------------------------------
# Envelope
# --------------------------------------------------------------------------------------
PLATE_W = V(146.0, "FIXED", "standard twin-socket outline (spec v0.1)")
PLATE_H = V(86.0, "FIXED", "standard twin-socket outline (spec v0.1)")
PLATE_PROUD = V(9.0, "DECIDED", "front face 9 mm from the wall (spec v0.1)")
PLATE_WALL = V(2.0, "PROPOSED", "front and side wall thickness")
PLATE_CORNER_R = V(6.0, "PROPOSED", "plan-view corner radius")
PLATE_EDGE_R = V(1.5, "DECIDED", "edge radius (spec v0.1)")

FIX_PITCH = V(120.6, "FIXED", "BS 4662 fixing centres; screws at x = +/-60.3, y = 0")
FIX_SCREW_D = V(3.5, "FIXED", "M3.5 box-fixing screw")
FIX_HEAD_D = V(6.8, "PROPOSED", "screw head diameter allowance")
FIX_SCREW_LEN = V(25.0, "PROPOSED", "fixing screw length; tip at z = 2 - 25 = -23")

BOX_DEPTH = V(35.0, "DECIDED", "2-gang 35 mm back box")
BOX_OPENING = V((130.0, 70.0), "PROPOSED",
                "design envelope inside the box: smallest box seen is ABB 132 x 72; MK steel is 135 x 75")

# --------------------------------------------------------------------------------------
# Depth stack-up (z of each surface)
# --------------------------------------------------------------------------------------
Z = dict(
    plate_front=V(9.0, "DECIDED"),
    plate_inner=V(7.0, "PROPOSED", "plate_front - PLATE_WALL"),
    front_top=V(6.4, "PROPOSED", "front board F side, 0.6 mm under the plate"),
    front_bot=V(4.8, "PROPOSED", "front board B side (1.6 mm board)"),
    frame_top=V(2.0, "PROPOSED", "inner frame, 2 mm thick, sits on the wall"),
    frame_bot=V(0.0, "PROPOSED"),
    rear_top=V(-16.0, "PROPOSED", "rear board F side; tall parts stand on it"),
    rear_bot=V(-17.6, "PROPOSED", "rear board B side (1.6 mm board)"),
    cover_floor=V(-22.0, "PROPOSED", "rear cover floor, 4.4 mm under the board for B-side parts"),
    box_back=V(-35.0, "DECIDED"),
)
FRONT_T = V(1.6, "DECIDED", "front board 1.6 mm, 4 layers")
REAR_T = V(1.6, "PROPOSED", "rear board 1.6 mm, 2 layers, 2 oz")

# Tallest parts (FIXED from datasheets) and the front board's B-side parts
H = dict(
    ld03=V(17.6, "FIXED", "Mornsun current table (2021 datasheet: 16.0)"),
    relay=V(15.7, "FIXED", "G5RL-1A-E body height"),
    terminal=V(11.0, "PROPOSED", "3-way mains terminal block on the rear board's B side"),
    esp32=V(2.4, "FIXED", "ESP32-C6-MINI-1, on the front board's B side"),
    fpc=V(2.56, "FIXED", "TE 1-84952-4 height above board"),
    b_side_max=V(3.5, "PROPOSED", "tallest part allowed on the rear board's B side outside the terminal"),
)

# --------------------------------------------------------------------------------------
# Outlets (BS 1363)
# --------------------------------------------------------------------------------------
OUTLET_PITCH = V(68.0, "PROPOSED", "typical twin socket; confirm against the donor (A4)")
OUTLET_Y = V(4.0, "PROPOSED", "outlet reference point above the plate centre line; donor A5")
OUTLETS = [(-OUTLET_PITCH.v / 2, OUTLET_Y.v), (OUTLET_PITCH.v / 2, OUTLET_Y.v)]
# Outlet reference point: halfway between the L-N centre line and the earth centre.
PIN_OFFSETS = dict(  # (dx, dy) from the outlet reference point; viewed from the front, L is lower right
    L=V((11.1, -11.1), "FIXED", "pin centres 22.2 apart; L lower right (BS 1363)"),
    N=V((-11.1, -11.1), "FIXED"),
    E=V((0.0, 11.1), "FIXED", "earth 22.2 above the L-N line"),
)
PIN_LEN = dict(LN=V(17.7, "FIXED", "L and N pins"), E=V(22.7, "FIXED", "earth pin, 22.3-22.7 by source"))
APERTURE = dict(  # (w, h) of the faceplate apertures
    LN=V((7.4, 4.8), "DONOR", "pin 6.35 x 4.0 plus clearance"),
    E=V((4.8, 8.8), "DONOR", "pin 4.0 x 8.0 plus clearance"),
)
# Contact carrier envelope around each outlet: all mains metal of the outlet is inside it.
CARRIER = dict(
    w=V(34.0, "DONOR"), h=V(36.0, "DONOR"),
    z_bot=V(-16.0, "DONOR", "stands on the rear board"),
    z_top=V(6.5, "DONOR", "0.5 mm under the plate's inner face"),
)
CONTACT_PAD = dict(  # rear-board landing of each contact tail (slot plus pad), at the pin position
    LN=V((5.5, 2.4, 3.9, 0.8), "DONOR", "pad w, pad h, slot w, slot h"),
    E=V((2.4, 5.5, 0.8, 3.9), "DONOR"),
)

# --------------------------------------------------------------------------------------
# Insulation (design targets, confirmed by the lab; spec v0.1)
# --------------------------------------------------------------------------------------
HOT_SAFE = V(8.0, "DECIDED", "reinforced: creepage and clearance, hot side to safe side")
L_N = V(3.0, "DECIDED", "live to neutral copper")
SLOT_W = V(1.0, "PROPOSED", "routed barrier slot width")

# --------------------------------------------------------------------------------------
# Rear board (2 layers, 2 oz)
# --------------------------------------------------------------------------------------
REAR = dict(
    w=V(128.0, "PROPOSED"), h=V(68.0, "PROPOSED"), corner_r=V(1.0, "PROPOSED"),
    notch=V((10.7, 14.0), "PROPOSED", "fixing-screw notch at each end: depth from the edge x height"),
    holes=V([(-58.0, 29.0), (58.0, 29.0), (-58.0, -29.0), (58.0, -29.0)], "PROPOSED",
            "2.7 mm holes, nylon M2.5 screws into the inner frame's posts"),
    hole_d=V(2.7, "PROPOSED"), hole_keepout_d=V(6.0, "PROPOSED", "no copper: nylon screw head 4.5 + 0.75"),
)

# Zoning v0 (PROPOSED): one T-shaped safe island in the middle, the hot side everywhere else.
# Why: the concept renders stood both relays under the LD03 in the centre strip. That leaves no
# corridor 16 mm wide (8 mm each side) to carry the LD03's 5 V and the relay coil drives to a safe
# zone, so the relays lie in the bottom strip instead, coil ends toward the island.
SAFE_ISLAND = V([  # polygon, x/y in board coordinates (= global)
    (-24.0, -34.0), (24.0, -34.0), (24.0, -18.0), (12.0, -18.0), (12.0, 13.0),
    (-12.0, 13.0), (-12.0, -18.0), (-24.0, -18.0)], "PROPOSED",
    "bottom bar 8 mm from the relay contact pads and the outlet contacts; stem 8 mm from both outlets' contacts")
PLACE = dict(  # anchor positions used for keep-outs, the fit model and the render (all PROPOSED)
    ld03=V((0.0, 21.0, 270), "PROPOSED", "AC pins up (hot), DC pins down into the island; rotation in degrees"),
    k1=V((-26.5, -27.4, 180), "PROPOSED", "body centre; lying in the bottom strip, coil end at x = -12 toward the island"),
    k2=V((26.5, -27.4, 0), "PROPOSED", "mirror of K1"),
    j4=V((0.0, -5.0, 90), "PROPOSED",
         "FFC connector in the island stem, pin row along y, opening toward +x. Lengthwise (pin row along x) it is 25 mm over its pads and the stem is 24"),
    terminal=V((-38.0, 27.0, 0), "PROPOSED", "B side, top left, top entry; clear of the LD03's AC pins"),
    u5=V((-17.15, 4.0, 0), "PROPOSED",
         "B side, straddling the stem's left edge: safe pins at x = -12, hot pins under the left carrier (free on the B side), "
         "1 mm slot under it. On the F side there is no room: the carrier, the LD03 or the relays sit on every edge of the island"),
)

# --------------------------------------------------------------------------------------
# Front board (4 layers, SELV)
# --------------------------------------------------------------------------------------
FRONT = dict(
    w=V(136.0, "PROPOSED"), h=V(76.0, "PROPOSED"), corner_r=V(2.0, "PROPOSED"),
    cutout_margin=V(HOT_SAFE.v, "DECIDED", "outlet cutout = carrier envelope + 8 mm all round"),
    cutout_r=V(3.0, "PROPOSED"),
    access_d=V(9.0, "PROPOSED", "fixing-screw access, merged into the cutouts"),
    holes=V([(-63.0, 33.0), (63.0, 33.0), (-63.0, -33.0), (63.0, -33.0)], "PROPOSED",
            "2.7 mm holes onto the inner frame's posts"),
    hole_d=V(2.7, "PROPOSED"), hole_keepout_d=V(6.0, "PROPOSED"),
)
ESP32 = dict(
    centre=V((0.0, -29.7), "PROPOSED", "B side, bottom centre, antenna toward -y at the board edge"),
    size=V((13.2, 16.6), "FIXED"), antenna_len=V(4.1, "FIXED", "16.6 - 12.5 (MINI-1U body without antenna)"),
    notch_margin=V(3.0, "PROPOSED", "board cut away below and beside the antenna (Espressif guideline)"),
)
J101 = V((0.0, -5.0, 90), "PROPOSED", "B side, same x, y and rotation as J4, so pin n meets pin n through a Type A FFC")
TOUCH = dict(
    centres=V([(x, -30.0) for x, _ in OUTLETS], "PROPOSED", "one zone under each outlet"),
    zone_d=V(20.0, "DECIDED", "20 mm zone on the plate (spec v0.1)"),
    electrode=V((20.0, 14.0, 5.0), "PROPOSED", "w, h, and the gap left for the light line through the middle"),
    groove=V((0.4, 0.2), "PROPOSED", "recessed ring on the plate: width, depth (spec: 0.2 mm)"),
)
LIGHT = dict(
    length=V(20.0, "PROPOSED"), width=V(0.6, "PROPOSED", "thin-walled translucent strip (spec v0.1)"),
    y=V(-30.0, "PROPOSED", "through the middle of each touch zone"),
    led_dx=V(6.0, "PROPOSED", "two SK6812MINI-E per outlet at x = centre +/- 6"),
)
NFC = dict(centre=V((0.0, 17.0), "PROPOSED"), coil=V((15.0, 22.0), "PROPOSED", "on the centre bridge"),
           mark_d=V(8.0, "PROPOSED", "recessed mark on the plate"))

# --------------------------------------------------------------------------------------
# Inner frame (EVT: printed FR PC/ABS; DVT: steel) and rear cover
# --------------------------------------------------------------------------------------
FRAME = dict(
    outer=V((141.0, 81.0), "PROPOSED", "fits the plate cavity with 0.5 mm all round"),
    opening=V((108.0, -19.0, 35.0), "PROPOSED", "width, bottom y, top y: clears the carriers, the LD03 and the FFC"),
    lip=V((1.5, 3.0), "PROPOSED", "perimeter wall for the plate's clips: thickness (1.5 mm for V-0), height"),
    clips=V([(-40.0, 1), (40.0, 1), (-40.0, -1), (40.0, -1)], "PROPOSED", "x, top (+1) or bottom (-1) edge"),
    post_d=V(6.4, "PROPOSED", "1.6 mm wall around the 3.2 mm insert hole"),
    antenna_cut=V((22.0, -30.0), "PROPOSED", "no frame plastic below y = -30 across x = +/-11"),
)
COVER = dict(
    wall=V(1.5, "PROPOSED"), floor_t=V(1.6, "PROPOSED"),
    terminal_opening=V((35.0, 13.0), "PROPOSED", "the terminal block protrudes through the floor"),
)

# --------------------------------------------------------------------------------------
# Derived values
# --------------------------------------------------------------------------------------
def z(name):
    return Z[name].v


def carrier_box(cx, cy):
    """(x0, y0, x1, y1) of a carrier envelope."""
    w, h = CARRIER["w"].v, CARRIER["h"].v
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def pins(cx, cy):
    return {k: (cx + o.v[0], cy + o.v[1]) for k, o in PIN_OFFSETS.items()}


def hot_features():
    """Hot copper that must stay HOT_SAFE from the safe island: (name, shapely geometry)."""
    from shapely.geometry import Point, box
    out = []
    for i, (cx, cy) in enumerate(OUTLETS, 1):
        for k, (px, py) in pins(cx, cy).items():
            w, h = CONTACT_PAD["E" if k == "E" else "LN"].v[:2]
            out.append((f"outlet {i} {k} contact pad", box(px - w / 2, py - h / 2, px + w / 2, py + h / 2)))
    for k in ("k1", "k2"):  # relay contact pads: 20.08 and 25.1 mm from the coil pads (footprint)
        x, y, _ = PLACE[k].v
        sgn = 1 if x > 0 else -1
        coil_x = x - sgn * (29.0 / 2 - 2.3)
        for d in (20.08, 25.1):
            for dy in (-3.765, 3.765):
                out.append((f"{k.upper()} contact pad", Point(coil_x + sgn * d, y + dy).buffer(1.4)))
    x, y, _ = PLACE["ld03"].v  # rotated so the AC pins (1, 2) are on the top edge, at the left
    for dx in (-10.16, -5.08):
        out.append(("LD03 AC pin", Point(x + dx, y + 10.16).buffer(1.1)))
    return out


def checks():
    """Fit checks that follow from the numbers above. Returns a list of (name, value, limit, ok)."""
    out = []

    def chk(name, value, limit, ok):
        out.append((name, round(value, 2), limit, ok))

    chk("plate inner face above front board", z("plate_inner") - z("front_top"), ">= 0.5", z("plate_inner") - z("front_top") >= 0.5)
    ld03_top = z("rear_top") + H["ld03"].v
    chk("LD03 top below the frame top", z("frame_top") - ld03_top, ">= 0.3 (frame opening clears it)", True)
    chk("LD03 top to front board B-side parts (ESP32 not over it)", z("front_bot") - H["esp32"].v - ld03_top,
        ">= 0.5", z("front_bot") - H["esp32"].v - ld03_top >= 0.5)
    chk("LD03 top to front board B side (no parts over it)", z("front_bot") - ld03_top, ">= 3.0", z("front_bot") - ld03_top >= 3.0)
    relay_top = z("rear_top") + H["relay"].v
    chk("relay top below the frame", z("frame_bot") - relay_top, ">= 0.3", z("frame_bot") - relay_top >= 0.3)
    e_tip = z("plate_front") - PIN_LEN["E"].v
    chk("earth pin tip above the rear board", e_tip - z("rear_top"), ">= 1.5", e_tip - z("rear_top") >= 1.5)
    ln_tip = z("plate_front") - PIN_LEN["LN"].v
    chk("L/N pin tip above the rear board", ln_tip - z("rear_top"), ">= 1.5", ln_tip - z("rear_top") >= 1.5)
    chk("cable space behind the rear cover", z("cover_floor") - COVER["floor_t"].v - z("box_back"), ">= 10",
        z("cover_floor") - COVER["floor_t"].v - z("box_back") >= 10)
    term_bot = z("rear_bot") - H["terminal"].v
    chk("terminal block above the box back", term_bot - z("box_back"), ">= 5 (wire bend)", term_bot - z("box_back") >= 5)
    screw_tip = z("frame_top") - FIX_SCREW_LEN.v
    chk("fixing screw tip above the box back", screw_tip - z("box_back"), ">= 2", screw_tip - z("box_back") >= 2)
    # plan view
    bw, bh = BOX_OPENING.v
    chk("rear board inside the box envelope (x)", bw / 2 - REAR["w"].v / 2, ">= 0", bw / 2 - REAR["w"].v / 2 >= 0)
    chk("rear board inside the box envelope (y)", bh / 2 - REAR["h"].v / 2, ">= 0", bh / 2 - REAR["h"].v / 2 >= 0)
    for i, (cx, cy) in enumerate(OUTLETS):
        x0, y0, x1, y1 = carrier_box(cx, cy)
        chk(f"carrier {i + 1} inside the box envelope (x)", bw / 2 - max(abs(x0), abs(x1)), ">= 0",
            bw / 2 - max(abs(x0), abs(x1)) >= 0)
    # island to the nearest outlet contact pad edge
    pad_w = CONTACT_PAD["LN"].v[0]
    inner_pad_x = OUTLETS[1][0] + PIN_OFFSETS["N"].v[0] - pad_w / 2
    chk("safe island stem to the nearest contact pad (x)", inner_pad_x - 12.0, f">= {HOT_SAFE.v}", inner_pad_x - 12.0 >= HOT_SAFE.v)
    pad_bot = OUTLET_Y.v + PIN_OFFSETS["L"].v[1] - CONTACT_PAD["LN"].v[1] / 2
    chk("safe island bottom bar to the contact pads (y)", pad_bot - (-18.0), f">= {HOT_SAFE.v}", pad_bot + 18.0 >= HOT_SAFE.v)
    try:
        from shapely.geometry import Polygon
        island = Polygon(SAFE_ISLAND.v)
        worst = min(((island.distance(g), n) for n, g in hot_features()))
        chk(f"safe island to the nearest hot copper ({worst[1]})", worst[0], f">= {HOT_SAFE.v}", worst[0] >= HOT_SAFE.v)
    except ImportError:
        chk("safe island distances (shapely not installed)", 0, "skipped", True)
    return out


if __name__ == "__main__":
    print("Depth stack-up (z, mm):")
    for k, val in sorted(Z.items(), key=lambda kv: -kv[1].v):
        print(f"  {val.v:7.1f}  {k:12s} {val.status:9s} {val.note}")
    print("\nFit checks:")
    bad = 0
    for name, value, limit, ok in checks():
        bad += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {value} (limit {limit})")
    print(f"\n{bad} failing")
    raise SystemExit(1 if bad else 0)
