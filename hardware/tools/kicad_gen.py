"""
Design objects and symbol definitions for the Smart Wall Socket schematics.

Symbols are generated, not taken from the KiCad libraries, so their pin
positions are known exactly. Two-pin parts come in four variants (pin 1 left,
pin 2 left, pin 1 top, pin 2 top) so the layout can turn them without using
KiCad's symbol rotation.

Coordinates: millimetres on the 1.27 mm grid. Symbol space has +y up.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

G = 1.27
PIN_LEN = 2.54
FONT = 1.27
CHAR_W = 1.0  # average glyph advance at a 1.27 mm font, a little generous


def snap(v: float) -> float:
    return round(round(v / G) * G, 4)


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def new_uuid(seed: str | None = None) -> str:
    if seed is None:
        return str(uuid.uuid4())
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "aetherlabs/sws/" + seed))


# --------------------------------------------------------------------------
# Symbols
# --------------------------------------------------------------------------

@dataclass
class Pin:
    nums: list[str]       # several numbers = stacked pins at one position
    name: str
    etype: str
    side: str = "L"       # L, R, T, B
    x: float = 0.0        # connection point, symbol space
    y: float = 0.0
    angle: int = 0        # KiCad pin angle: 0 points right (pin on the left side)


@dataclass
class SymDef:
    name: str
    kind: str = "box"
    ref: str = "U"
    pins: list[Pin] = field(default_factory=list)
    desc: str = ""
    w2: float = 0.0
    top: float = 0.0
    body_top: float = 0.0
    body_bot: float = 0.0
    show_pin_names: bool = True
    prims: list = field(default_factory=list)   # graphics primitives
    variant: str = "H"                          # H, HR, V, VR for two-pin parts
    base: "SymDef | None" = None

    @property
    def lib_id(self) -> str:
        return "sws:" + self.name

    def bbox(self):
        """Body extent in symbol space (x0, y0, x1, y1), pins excluded."""
        if self.kind == "box":
            return (-self.w2, self.body_bot, self.w2, self.body_top)
        xs, ys = [], []
        for p in self.prims:
            for (x, y) in _prim_points(p):
                xs.append(x)
                ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys))


def _prim_points(p):
    t = p[0]
    if t == "poly":
        return p[1]
    if t == "rect":
        return [p[1], p[2]]
    if t == "arc":
        return [p[1], p[2], p[3]]
    if t == "circle":
        (cx, cy), r = p[1], p[2]
        return [(cx - r, cy - r), (cx + r, cy + r)]
    return []


def box(name: str, left, right, ref="U", desc="") -> SymDef:
    s = SymDef(name=name, kind="box", ref=ref, desc=desc)
    n = max(len(left), len(right), 1)
    s.top = snap((n - 1) * G)
    ln = max([len(p[1]) for p in left] + [0])
    rn = max([len(p[1]) for p in right] + [0])
    w = (ln + rn) * CHAR_W + 3 * G
    s.w2 = max(5.08, math.ceil(w / 2 / 2.54) * 2.54)
    s.body_top = s.top + 2.54
    s.body_bot = -s.top - 2.54
    s.prims = [("rect", (-s.w2, s.body_top), (s.w2, s.body_bot), "background")]
    for side, lst in (("L", left), ("R", right)):
        for i, (nums, pname, et) in enumerate(lst):
            y = s.top - i * 2.54
            x, ang = (-s.w2 - PIN_LEN, 0) if side == "L" else (s.w2 + PIN_LEN, 180)
            s.pins.append(Pin([t.strip() for t in str(nums).split(",")], pname, et, side, x, y, ang))
    return s


def _two_pin_prims(k: str) -> list:
    g = []
    line = lambda *pts: g.append(("poly", list(pts), "none"))
    if k in ("R", "F", "RV", "NTC", "SH", "TCO"):
        g.append(("rect", (-2.54, 0.889), (2.54, -0.889), "none"))
        if k == "F":
            line((-2.54, 0), (2.54, 0))
        if k in ("RV", "NTC"):
            line((-2.032, -1.524), (1.524, 1.524), (2.286, 1.524))
        if k == "SH":
            line((-1.27, 0.889), (-1.27, 1.778))
            line((1.27, 0.889), (1.27, 1.778))
    if k == "TCO":
        g.clear()
        line((-2.54, 0), (-0.762, 0), (0.762, 1.016))
        line((0.762, 0), (2.54, 0))
        g.append(("rect", (-2.032, 1.524), (2.032, -0.635), "none"))
    elif k in ("C", "CP"):
        line((-2.54, 0), (-0.508, 0))
        line((0.508, 0), (2.54, 0))
        line((-0.508, 1.778), (-0.508, -1.778))
        if k == "C":
            line((0.508, 1.778), (0.508, -1.778))
        else:
            g.append(("arc", (1.016, 1.778), (0.508, 0), (1.016, -1.778)))
            line((-1.778, 1.524), (-1.778, 0.508))
            line((-2.286, 1.016), (-1.27, 1.016))
    elif k == "L":
        for i in range(4):
            x0 = -2.54 + i * 1.27
            g.append(("arc", (x0 + 1.27, 0), (x0 + 0.635, 0.635), (x0, 0)))
    elif k in ("D", "DS", "DZ", "TVS", "LED"):
        line((-2.54, 0), (-1.27, 0))
        line((1.27, 0), (2.54, 0))
        g.append(("poly", [(1.27, 1.27), (1.27, -1.27), (-1.27, 0), (1.27, 1.27)], "none"))
        if k == "DS":
            line((-0.762, 1.016), (-0.762, 1.27), (-1.27, 1.27), (-1.27, -1.27), (-1.778, -1.27), (-1.778, -1.016))
        elif k in ("DZ", "TVS"):
            line((-0.762, 1.27), (-1.27, 1.27), (-1.27, -1.27), (-1.778, -1.27))
        else:
            line((-1.27, 1.27), (-1.27, -1.27))
    return g


def two_pin(name: str, kind: str, ref: str, n1="1", n2="2", desc="") -> SymDef:
    s = SymDef(name=name, kind=kind, ref=ref, desc=desc, show_pin_names=False)
    s.prims = _two_pin_prims(kind)
    s.pins = [Pin([n1], "~", "passive", "L", -5.08, 0, 0),
              Pin([n2], "~", "passive", "R", 5.08, 0, 180)]
    s.w2, s.body_top, s.body_bot = 2.54, 1.905, -1.905
    s.variants = {"H": s}
    for v in ("HR", "V", "VR"):
        s.variants[v] = _variant(s, v)
    return s


_XF = {
    "HR": (lambda x, y: (-x, y), {0: 180, 180: 0}),
    "V": (lambda x, y: (y, -x), {0: 270, 180: 90}),
    "VR": (lambda x, y: (-y, x), {0: 90, 180: 270}),
}


def _variant(s: SymDef, v: str) -> SymDef:
    f, amap = _XF[v]
    t = SymDef(name=f"{s.name}_{v}", kind=s.kind, ref=s.ref, desc=s.desc, show_pin_names=False,
               variant=v, base=s)
    for p in s.prims:
        if p[0] == "poly":
            t.prims.append(("poly", [f(*pt) for pt in p[1]], p[2]))
        elif p[0] == "rect":
            t.prims.append(("rect", f(*p[1]), f(*p[2]), p[3]))
        elif p[0] == "arc":
            t.prims.append(("arc", f(*p[1]), f(*p[2]), f(*p[3])))
    for p in s.pins:
        x, y = f(p.x, p.y)
        ang = amap[p.angle]
        side = {0: "L", 180: "R", 270: "T", 90: "B"}[ang]
        t.pins.append(Pin(list(p.nums), p.name, p.etype, side, x, y, ang))
    return t


def one_pin(name: str, ref: str, desc="") -> SymDef:
    s = SymDef(name=name, kind="TP", ref=ref, desc=desc, show_pin_names=False)
    s.prims = [("circle", (0.635, 0), 0.635), ("poly", [(-1.27, 0), (0, 0)], "none")]
    s.w2, s.body_top, s.body_bot = 1.27, 1.27, -1.27
    s.pins = [Pin(["1"], "~", "passive", "L", -2.54, 0, 0)]
    return s


def _stroke(w=0.254):
    return f"(stroke (width {w}) (type default))"


def _prim_text(p) -> str:
    t = p[0]
    if t == "poly":
        return ("(polyline (pts " + " ".join(f"(xy {x:.4f} {y:.4f})" for x, y in p[1]) +
                f") {_stroke()} (fill (type {p[2]})))")
    if t == "rect":
        return f"(rectangle (start {p[1][0]:.4f} {p[1][1]:.4f}) (end {p[2][0]:.4f} {p[2][1]:.4f}) {_stroke()} (fill (type {p[3]})))"
    if t == "arc":
        return (f"(arc (start {p[1][0]:.4f} {p[1][1]:.4f}) (mid {p[2][0]:.4f} {p[2][1]:.4f}) "
                f"(end {p[3][0]:.4f} {p[3][1]:.4f}) {_stroke()} (fill (type none)))")
    if t == "circle":
        return f"(circle (center {p[1][0]:.4f} {p[1][1]:.4f}) (radius {p[2]}) {_stroke()} (fill (type none)))"
    raise ValueError(t)


def sym_lib_text(s: SymDef, indent="    ", lib_name: str | None = None) -> str:
    name = lib_name or s.lib_id
    if s.kind == "box":
        head = f"(symbol {q(name)} (pin_names (offset 0.762)) (in_bom yes) (on_board yes)"
    else:
        head = f"(symbol {q(name)} (pin_numbers hide) (pin_names (offset 0.254) hide) (in_bom yes) (on_board yes)"
    x0, y0, x1, y1 = s.bbox()
    out = [head,
           f'  (property "Reference" {q(s.ref)} (at 0 {y1 + 1.27:.4f} 0) (effects (font (size {FONT} {FONT}))))',
           f'  (property "Value" {q(s.name)} (at 0 {y0 - 1.27:.4f} 0) (effects (font (size {FONT} {FONT}))))',
           f'  (property "Footprint" "" (at 0 0 0) (effects (font (size {FONT} {FONT})) hide))',
           f'  (property "Datasheet" "~" (at 0 0 0) (effects (font (size {FONT} {FONT})) hide))']
    if s.desc:
        out.append(f'  (property "ki_description" {q(s.desc)} (at 0 0 0) (effects (font (size {FONT} {FONT})) hide))')
    short = s.name
    out.append(f'  (symbol {q(short + "_0_1")}')
    for p in s.prims:
        out.append("    " + _prim_text(p))
    out.append("  )")
    out.append(f'  (symbol {q(short + "_1_1")}')
    for p in s.pins:
        for i, num in enumerate(p.nums):
            et = p.etype if (i == 0 or p.etype == "no_connect") else "passive"
            length = PIN_LEN if s.kind != "TP" else 1.27
            out.append(f'    (pin {et} line (at {p.x:.4f} {p.y:.4f} {p.angle}) (length {length})'
                       f' (name {q(p.name)} (effects (font (size {FONT} {FONT}))))'
                       f' (number {q(num)} (effects (font (size {FONT} {FONT})))))')
    out.append("  )")
    out.append(")")
    return "\n".join(indent + l for l in out)


POWER_EXT = {"rail": 2.286, "gnd": 2.286, "hot": 2.794}
_PXF = {"up": lambda x, y: (x, y), "down": lambda x, y: (x, -y),
        "right": lambda x, y: (y, x), "left": lambda x, y: (-y, x)}


def power_value_pos(style: str, d: str):
    """Value text offset (symbol space, y up) and justification for a power symbol."""
    e = POWER_EXT[style] + 1.6
    return {"up": ((0, e), "center"), "down": ((0, -e), "center"),
            "right": ((e - 0.6, 0), "left"), "left": ((-e + 0.6, 0), "right")}[d]


def power_lib_text(net: str, style: str, d: str = "up", indent="    "):
    """Power symbol pointing in direction d, whose hidden pin makes a global net named `net`."""
    short = "PWR_" + "".join(c if c.isalnum() else "_" for c in net) + "_" + d
    if style == "hot":
        prims = [[(0, 0), (0, 1.27)], [(-1.524, 1.27), (1.524, 1.27), (0, 2.794), (-1.524, 1.27)]]
        fills = ["none", "outline"]
    elif style == "gnd":
        prims = [[(0, 0), (0, 1.27)], [(-1.524, 1.27), (1.524, 1.27)], [(-0.889, 1.778), (0.889, 1.778)],
                 [(-0.254, 2.286), (0.254, 2.286)]]
        fills = ["none"] * 4
    else:
        prims = [[(0, 0), (0, 1.27)], [(-0.762, 1.27), (0, 2.286), (0.762, 1.27), (-0.762, 1.27)]]
        fills = ["none", "outline"]
    f = _PXF[d]
    g = ["(polyline (pts " + " ".join("(xy %.4f %.4f)" % f(x, y) for x, y in pts) +
         f") (stroke (width 0.254) (type default)) (fill (type {fl})))" for pts, fl in zip(prims, fills)]
    (vx, vy), just = power_value_pos(style, d)
    jj = "" if just == "center" else f" (justify {just})"
    out = [f"(symbol {q('pwr:' + short)} (power) (pin_names (offset 0)) (in_bom yes) (on_board yes)",
           f'  (property "Reference" "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'  (property "Value" {q(net)} (at {vx:.4f} {vy:.4f} 0) (effects (font (size 1.27 1.27)){jj}))',
           f'  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'  (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f"  (symbol {q(short + '_0_1')}"] + ["    " + x for x in g] + ["  )",
           f"  (symbol {q(short + '_1_1')}",
           f'    (pin power_in line (at 0 0 90) (length 0) hide (name {q(net)} (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))',
           "  )", ")"]
    return "\n".join(indent + l for l in out), "pwr:" + short


PWR_FLAG_LIB = """    (symbol "power:PWR_FLAG" (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom yes) (on_board yes)
      (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PWR_FLAG_0_0"
        (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
      )
      (symbol "PWR_FLAG_0_1"
        (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))
      )
    )"""


# --------------------------------------------------------------------------
# Design objects
# --------------------------------------------------------------------------

@dataclass
class Part:
    ref: str
    sym: SymDef
    value: str
    conn: dict
    footprint: str = ""
    lcsc: str = ""
    mpn: str = ""
    mfr: str = ""
    note: str = ""
    dnp: bool = False
    verified: str = ""


@dataclass
class Block:
    title: str
    notes: str
    parts: list[Part]


@dataclass
class Sheet:
    """One column of blocks on the board's single sheet."""
    name: str
    file: str
    title: str
    blocks: list[Block]
    flags: list[str] = field(default_factory=list)   # nets that get a PWR_FLAG


@dataclass
class Project:
    name: str
    title: str
    sheets: list[Sheet]
    root_notes: str = ""
    warning: str = ""
    rails: dict = field(default_factory=dict)        # net -> "gnd" or "rail"
    barrier_after: int | None = None                 # draw the barrier after this column


def write_symbol_library(symdefs: list[SymDef], path: str):
    L = ['(kicad_symbol_lib (version 20220914) (generator kicad_gen_py)']
    for s in sorted(symdefs, key=lambda s: s.name):
        L.append(sym_lib_text(s, indent="  ", lib_name=s.name))
    L.append(")")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
