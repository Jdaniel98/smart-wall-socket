"""
Minimal KiCad 7 schematic writer for the Smart Wall Socket hardware.

The design lives in plain Python (parts, pins, nets). This module turns it into
hierarchical .kicad_sch files with embedded symbols, where every pin is joined
to its net by a label placed on the pin's end. No wires are drawn, so the
drawing cannot disagree with the netlist: verify.py re-reads the netlist that
kicad-cli exports and compares it with the design, net by net.

Coordinates: millimetres, everything on the 1.27 mm (50 mil) grid.
Symbol space has +y up; schematic space has +y down.
"""
from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import dataclass, field

G = 1.27
PIN_LEN = 2.54
FONT = 1.27
CHAR_W = 1.0  # average glyph advance at 1.27 mm font, a little generous


def snap(v: float) -> float:
    return round(round(v / G) * G, 4)


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def new_uuid(seed: str | None = None) -> str:
    # Deterministic UUIDs keep diffs small between regenerations.
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
    etype: str            # input, output, bidirectional, passive, power_in,
                          # power_out, open_collector, tri_state, no_connect
    side: str = "L"       # L or R
    x: float = 0.0        # connection point, symbol space
    y: float = 0.0
    angle: int = 0


@dataclass
class SymDef:
    name: str                     # without library prefix
    kind: str = "box"             # box or a two-pin graphic kind
    ref: str = "U"
    pins: list[Pin] = field(default_factory=list)
    desc: str = ""
    w2: float = 0.0               # half body width
    top: float = 0.0              # y of first pin row
    body_top: float = 0.0
    body_bot: float = 0.0
    show_pin_names: bool = True

    @property
    def lib_id(self) -> str:
        return "sws:" + self.name

    def pin_by_num(self, num: str) -> Pin:
        for p in self.pins:
            if num in p.nums:
                return p
        raise KeyError(f"{self.name}: no pin {num}")


TWO_PIN = {"R", "C", "CP", "L", "D", "DS", "DZ", "TVS", "F", "RV", "NTC", "LED", "TCO", "SH"}


def box(name: str, left, right, ref="U", desc="") -> SymDef:
    """left/right: lists of (numbers, name, etype); numbers may be 'a,b,c'."""
    s = SymDef(name=name, kind="box", ref=ref, desc=desc)
    n = max(len(left), len(right), 1)
    s.top = snap((n - 1) * G)
    ln = max([len(p[1]) for p in left] + [0])
    rn = max([len(p[1]) for p in right] + [0])
    w = (ln + rn) * CHAR_W + 3 * G
    s.w2 = max(5.08, math.ceil(w / 2 / 2.54) * 2.54)
    s.body_top = s.top + 2.54
    s.body_bot = -s.top - 2.54
    for side, lst in (("L", left), ("R", right)):
        for i, (nums, pname, et) in enumerate(lst):
            y = s.top - i * 2.54
            if side == "L":
                x, ang = -s.w2 - PIN_LEN, 0
            else:
                x, ang = s.w2 + PIN_LEN, 180
            s.pins.append(Pin(nums=[t.strip() for t in str(nums).split(",")], name=pname,
                              etype=et, side=side, x=x, y=y, angle=ang))
    return s


def two_pin(name: str, kind: str, ref: str, n1="1", n2="2", desc="") -> SymDef:
    s = SymDef(name=name, kind=kind, ref=ref, desc=desc, show_pin_names=False)
    s.w2 = 2.54
    s.top = 0
    s.body_top = 1.905
    s.body_bot = -1.905
    s.pins = [Pin([n1], "~", "passive", "L", -5.08, 0, 0),
              Pin([n2], "~", "passive", "R", 5.08, 0, 180)]
    return s


def one_pin(name: str, ref: str, desc="") -> SymDef:
    s = SymDef(name=name, kind="TP", ref=ref, desc=desc, show_pin_names=False)
    s.w2 = 1.27
    s.body_top = 1.27
    s.body_bot = -1.27
    s.pins = [Pin(["1"], "~", "passive", "L", -2.54, 0, 0)]
    return s


def _stroke(w=0.254):
    return f"(stroke (width {w}) (type default))"


def _graphics(s: SymDef) -> list[str]:
    k = s.kind
    g = []
    line = lambda *pts: g.append("(polyline (pts " + " ".join(f"(xy {x} {y})" for x, y in pts)
                                 + f") {_stroke()} (fill (type none)))")
    if k == "box":
        g.append(f"(rectangle (start {-s.w2} {s.body_top}) (end {s.w2} {s.body_bot}) "
                 f"{_stroke()} (fill (type background)))")
        return g
    if k == "TP":
        g.append(f"(circle (center 0.635 0) (radius 0.635) {_stroke()} (fill (type none)))")
        line((-1.27, 0), (0, 0))
        return g
    # two-pin parts: leads from +-2.54 to the body
    if k in ("R", "F", "RV", "NTC", "SH", "TCO"):
        g.append(f"(rectangle (start -2.54 0.889) (end 2.54 -0.889) {_stroke()} (fill (type none)))")
        if k == "F":
            line((-2.54, 0), (2.54, 0))
        if k in ("RV", "NTC"):
            line((-2.032, -1.524), (1.524, 1.524), (2.286, 1.524))
        if k == "SH":
            line((-1.27, 0.889), (-1.27, 1.778))
            line((1.27, 0.889), (1.27, 1.778))
        if k == "TCO":
            line((-2.54, 0), (-0.635, 0), (0.635, 0.635))
            line((0.635, 0), (2.54, 0))
    elif k in ("C", "CP"):
        line((-2.54, 0), (-0.508, 0))
        line((0.508, 0), (2.54, 0))
        line((-0.508, 1.778), (-0.508, -1.778))
        if k == "C":
            line((0.508, 1.778), (0.508, -1.778))
        else:
            g.append(f"(arc (start 1.016 1.778) (mid 0.508 0) (end 1.016 -1.778) {_stroke()} (fill (type none)))")
            line((-1.778, 1.524), (-1.778, 0.508))
            line((-2.286, 1.016), (-1.27, 1.016))
    elif k == "L":
        for i in range(4):
            x0 = -2.54 + i * 1.27
            g.append(f"(arc (start {x0 + 1.27} 0) (mid {x0 + 0.635} 0.635) (end {x0} 0) "
                     f"{_stroke()} (fill (type none)))")
    elif k in ("D", "DS", "DZ", "TVS", "LED"):
        # cathode on the left (pin 1), anode on the right (pin 2)
        line((-2.54, 0), (-1.27, 0))
        line((1.27, 0), (2.54, 0))
        g.append(f"(polyline (pts (xy 1.27 1.27) (xy 1.27 -1.27) (xy -1.27 0) (xy 1.27 1.27)) "
                 f"{_stroke()} (fill (type none)))")
        if k == "DS":
            line((-0.762, 1.016), (-0.762, 1.27), (-1.27, 1.27), (-1.27, -1.27), (-1.778, -1.27), (-1.778, -1.016))
        elif k in ("DZ", "TVS"):
            line((-0.762, 1.27), (-1.27, 1.27), (-1.27, -1.27), (-1.778, -1.27))
        else:
            line((-1.27, 1.27), (-1.27, -1.27))
        if k == "LED":
            line((-0.508, 1.778), (0.762, 3.048))
            line((0.508, 1.778), (1.778, 3.048))
    return g


def sym_lib_text(s: SymDef, indent="    ") -> str:
    pn = "" if s.show_pin_names else " (pin_names (offset 0.254) hide)"
    pn_num = " (pin_numbers hide)" if s.kind != "box" else ""
    out = [f'(symbol {q(s.lib_id)}{pn_num}{pn if s.kind != "box" else " (pin_names (offset 0.762))"} (in_bom yes) (on_board yes)']
    out.append(f'  (property "Reference" {q(s.ref)} (at 0 {s.body_top + 1.27} 0) (effects (font (size {FONT} {FONT}))))')
    out.append(f'  (property "Value" {q(s.name)} (at 0 {s.body_bot - 1.27} 0) (effects (font (size {FONT} {FONT}))))')
    out.append(f'  (property "Footprint" "" (at 0 0 0) (effects (font (size {FONT} {FONT})) hide))')
    out.append(f'  (property "Datasheet" "~" (at 0 0 0) (effects (font (size {FONT} {FONT})) hide))')
    if s.desc:
        out.append(f'  (property "ki_description" {q(s.desc)} (at 0 0 0) (effects (font (size {FONT} {FONT})) hide))')
    out.append(f'  (symbol {q(s.name + "_0_1")}')
    for gline in _graphics(s):
        out.append("    " + gline)
    out.append("  )")
    out.append(f'  (symbol {q(s.name + "_1_1")}')
    for p in s.pins:
        for i, num in enumerate(p.nums):
            et = p.etype
            if i > 0 and et not in ("no_connect",):
                et = "passive"  # stacked duplicates
            length = PIN_LEN if s.kind == "box" else (2.54 if s.kind != "TP" else 1.27)
            out.append(f'    (pin {et} line (at {p.x} {p.y} {p.angle}) (length {length})'
                       f' (name {q(p.name)} (effects (font (size {FONT} {FONT}))))'
                       f' (number {q(num)} (effects (font (size {FONT} {FONT})))))')
    out.append("  )")
    out.append(")")
    return "\n".join(indent + l for l in out)


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
    conn: dict                      # pin number -> net name or "NC"
    footprint: str = ""
    lcsc: str = ""
    mpn: str = ""
    mfr: str = ""
    note: str = ""
    dnp: bool = False
    verified: str = ""              # "yes" if LCSC number checked this session

    def pin_net(self, num):
        return self.conn.get(num)


@dataclass
class Block:
    title: str
    notes: str
    parts: list[Part]


@dataclass
class Sheet:
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
    warning: str = ""               # second title-block comment


# --------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------

PAPERS = [("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594)]


def _label_len(net: str, is_global: bool) -> float:
    return len(net) * CHAR_W + (3.81 if is_global else 1.27)


class Writer:
    def __init__(self, proj: Project, outdir: str, date: str, rev: str):
        self.p = proj
        self.out = outdir
        self.date = date
        self.rev = rev
        self.root_uuid = new_uuid(proj.name + "/root")
        # nets used on more than one sheet become global labels
        uses: dict[str, set] = {}
        for sh in proj.sheets:
            for b in sh.blocks:
                for part in b.parts:
                    for n in part.conn.values():
                        if n and n != "NC":
                            uses.setdefault(n, set()).add(sh.file)
            for n in sh.flags:
                uses.setdefault(n, set()).add(sh.file)
        self.global_nets = {n for n, s in uses.items() if len(s) > 1}

    # ---- sheets ---------------------------------------------------------
    def _syms(self, sheet: Sheet) -> list[SymDef]:
        seen = {}
        for b in sheet.blocks:
            for part in b.parts:
                seen[part.sym.name] = part.sym
        return list(seen.values())

    def _layout(self, sheet: Sheet):
        """Place parts in rows, block by block. Returns placements, texts and paper."""
        for paper, pw, ph in PAPERS:
            margin = 15.24
            usable_w = pw - 2 * margin
            x0, y = margin, margin + 10.16
            placements, texts = [], []
            ok = True
            for b in sheet.blocks:
                texts.append((x0, y, b.title, 2.0, True))
                y += 3.81
                if b.notes:
                    texts.append((x0, y, b.notes, 1.27, False))
                    y += 2.1 * (b.notes.count("\n") + 1) + 1.27
                x = x0
                row_h = 0.0
                y += 5.08
                for part in b.parts:
                    s = part.sym
                    lw = rw = 0.0
                    for pin in s.pins:
                        net = part.conn.get(pin.nums[0])
                        if not net or net == "NC":
                            continue
                        L = _label_len(net, net in self.global_nets)
                        if pin.side == "L":
                            lw = max(lw, L)
                        else:
                            rw = max(rw, L)
                    body_w = 2 * (s.w2 + PIN_LEN)
                    cell_w = lw + body_w + rw + 5.08
                    h_above = s.body_top + 3.81
                    h_below = -s.body_bot + 3.81
                    cell_h = h_above + h_below + 2.54
                    if x + cell_w > x0 + usable_w and x > x0:
                        x = x0
                        y += row_h
                        row_h = 0.0
                    cx = snap(x + lw + s.w2 + PIN_LEN)
                    cy = snap(y + h_above)
                    placements.append((part, cx, cy))
                    x += cell_w
                    row_h = max(row_h, cell_h)
                y += row_h + 5.08
            if y > ph - margin - 25:  # leave room for the title block
                ok = False
            if ok:
                return paper, placements, texts
        raise RuntimeError(f"sheet {sheet.name} does not fit on A1")

    def _sheet_path(self, idx: int) -> tuple[str, str]:
        sh_uuid = new_uuid(f"{self.p.name}/sheet/{self.p.sheets[idx].file}")
        return sh_uuid, f"/{self.root_uuid}/{sh_uuid}"

    def write_sheet(self, idx: int) -> str:
        sheet = self.p.sheets[idx]
        sh_uuid, path = self._sheet_path(idx)
        paper, placements, texts = self._layout(sheet)
        L = []
        L.append(f'(kicad_sch (version 20230121) (generator eeschema)')
        L.append(f'  (uuid {new_uuid(self.p.name + "/" + sheet.file)})')
        L.append(f'  (paper "{paper}")')
        L.append(self._title_block(sheet.title))
        L.append("  (lib_symbols")
        for s in self._syms(sheet):
            L.append(sym_lib_text(s))
        if sheet.flags:
            L.append(PWR_FLAG_LIB)
        L.append("  )")
        for (tx, ty, txt, size, bold) in texts:
            b = " bold" if bold else ""
            L.append(f'  (text {q(txt)} (at {snap(tx)} {snap(ty)} 0) (effects (font (size {size} {size}){b}) (justify left top)) (uuid {new_uuid()}))')
        nc_points = []
        for part, cx, cy in placements:
            L.append(self._symbol_instance(part, cx, cy, path))
            for pin in part.sym.pins:
                net = part.conn.get(pin.nums[0])
                px, py = snap(cx + pin.x), snap(cy - pin.y)
                if net is None:
                    if pin.etype == "no_connect":
                        continue
                    raise RuntimeError(f"{part.ref} pin {pin.nums[0]} ({pin.name}) has no net; use 'NC'")
                if net == "NC":
                    if pin.etype != "no_connect":
                        nc_points.append((px, py))
                    continue
                L.append(self._label(net, px, py, pin.side))
        for (px, py) in nc_points:
            L.append(f"  (no_connect (at {px} {py}) (uuid {new_uuid()}))")
        # PWR_FLAGs in the bottom-left corner, each on a short labelled stub
        fx = 20.32
        fy = snap({"A4": 210, "A3": 297, "A2": 420, "A1": 594}[paper] - 20.32)
        for i, net in enumerate(sheet.flags):
            x = snap(fx + i * 25.4)
            ref = f"#FLG0{idx + 1}{i + 1:02d}"
            L.append(f'  (symbol (lib_id "power:PWR_FLAG") (at {x} {fy} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {new_uuid(self.p.name + ref)})')
            L.append(f'    (property "Reference" "{ref}" (at {x} {fy - 1.905} 0) (effects (font (size 1.27 1.27)) hide))')
            L.append(f'    (property "Value" "PWR_FLAG" (at {x} {fy - 3.81} 0) (effects (font (size 1.27 1.27))))')
            L.append(f'    (property "Footprint" "" (at {x} {fy} 0) (effects (font (size 1.27 1.27)) hide))')
            L.append(f'    (property "Datasheet" "~" (at {x} {fy} 0) (effects (font (size 1.27 1.27)) hide))')
            L.append(f'    (pin "1" (uuid {new_uuid()}))')
            L.append(f'    (instances (project {q(self.p.name)} (path {q(path)} (reference "{ref}") (unit 1))))')
            L.append("  )")
            L.append(self._label(net, x, fy, "R"))
        L.append(")")
        return "\n".join(L) + "\n"

    def _title_block(self, title: str) -> str:
        return (f'  (title_block (title {q(title)}) (date "{self.date}") (rev "{self.rev}") '
                f'(company "Aether Labs") (comment 1 "Smart Wall Socket. DRAFT for engineering review, not a release.") '
                f'(comment 2 {q(self.p.warning)}))')

    def _symbol_instance(self, part: Part, cx: float, cy: float, path: str) -> str:
        s = part.sym
        dnp = "yes" if part.dnp else "no"
        bom = "no" if part.dnp else "yes"
        u = new_uuid(f"{self.p.name}/{part.ref}")
        ry = snap(cy - s.body_top - 1.27)
        vy = snap(cy - s.body_bot + 2.54)
        val = part.value + (" (DNP)" if part.dnp else "")
        props = [
            ("Reference", part.ref, cx, ry, False),
            ("Value", val, cx, vy, False),
            ("Footprint", part.footprint, cx, cy, True),
            ("Datasheet", "~", cx, cy, True),
            ("LCSC", part.lcsc, cx, cy, True),
            ("MPN", part.mpn, cx, cy, True),
            ("Manufacturer", part.mfr, cx, cy, True),
            ("Notes", part.note, cx, cy, True),
        ]
        L = [f'  (symbol (lib_id {q(s.lib_id)}) (at {cx} {cy} 0) (unit 1) (in_bom {bom}) (on_board yes) (dnp {dnp}) (uuid {u})']
        for name, v, x, y, hide in props:
            h = " hide" if hide else ""
            L.append(f'    (property {q(name)} {q(v)} (at {x} {y} 0) (effects (font (size {FONT} {FONT})){h}))')
        for pin in s.pins:
            for num in pin.nums:
                L.append(f'    (pin {q(num)} (uuid {new_uuid(f"{self.p.name}/{part.ref}/{num}")}))')
        L.append(f'    (instances (project {q(self.p.name)} (path {q(path)} (reference {q(part.ref)}) (unit 1))))')
        L.append("  )")
        return "\n".join(L)

    def _label(self, net: str, x: float, y: float, side: str) -> str:
        ang = 180 if side == "L" else 0
        just = "right" if side == "L" else "left"
        if net in self.global_nets:
            return (f'  (global_label {q(net)} (shape passive) (at {x} {y} {ang}) (fields_autoplaced) '
                    f'(effects (font (size {FONT} {FONT})) (justify {just})) (uuid {new_uuid()}) '
                    f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide)))')
        return (f'  (label {q(net)} (at {x} {y} {ang}) (fields_autoplaced) '
                f'(effects (font (size {FONT} {FONT})) (justify {just} bottom)) (uuid {new_uuid()}))')

    def write_root(self) -> str:
        L = [f'(kicad_sch (version 20230121) (generator eeschema)',
             f'  (uuid {self.root_uuid})', '  (paper "A3")', self._title_block(self.p.title),
             "  (lib_symbols)"]
        x, y = 25.4, 38.1
        for i, sh in enumerate(self.p.sheets):
            sh_uuid, _ = self._sheet_path(i)
            w, h = 76.2, 25.4
            L.append(f'  (sheet (at {x} {y}) (size {w} {h}) (fields_autoplaced) (stroke (width 0.1524) (type solid)) '
                     f'(fill (color 0 0 0 0.0000)) (uuid {sh_uuid})')
            L.append(f'    (property "Sheetname" {q(sh.name)} (at {x} {snap(y - 0.635)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))')
            L.append(f'    (property "Sheetfile" {q(sh.file)} (at {x} {snap(y + h + 0.635)} 0) (effects (font (size 1.27 1.27)) (justify left top)))')
            L.append(f'    (instances (project {q(self.p.name)} (path "/{self.root_uuid}" (page "{i + 2}"))))')
            L.append("  )")
            x += 91.44
            if x > 330:
                x = 25.4
                y += 45.72
        if self.p.root_notes:
            L.append(f'  (text {q(self.p.root_notes)} (at 25.4 {snap(y + 45.72)} 0) (effects (font (size 1.27 1.27)) (justify left top)) (uuid {new_uuid()}))')
        L.append('  (sheet_instances (path "/" (page "1")))')
        L.append(")")
        return "\n".join(L) + "\n"

    def write_all(self):
        os.makedirs(self.out, exist_ok=True)
        with open(os.path.join(self.out, self.p.name + ".kicad_sch"), "w") as f:
            f.write(self.write_root())
        for i, sh in enumerate(self.p.sheets):
            with open(os.path.join(self.out, sh.file), "w") as f:
                f.write(self.write_sheet(i))
        pro = {"meta": {"filename": self.p.name + ".kicad_pro", "version": 1},
               "sheets": [[self.root_uuid, ""]] + [[self._sheet_path(i)[0], sh.name] for i, sh in enumerate(self.p.sheets)]}
        with open(os.path.join(self.out, self.p.name + ".kicad_pro"), "w") as f:
            json.dump(pro, f, indent=2)
        with open(os.path.join(self.out, "sym-lib-table"), "w") as f:
            f.write('(sym_lib_table\n  (lib (name "sws")(type "KiCad")(uri "${KIPRJMOD}/../lib/sws.kicad_sym")(options "")(descr "Aether Labs Smart Wall Socket symbols"))\n)\n')
        with open(os.path.join(self.out, "fp-lib-table"), "w") as f:
            f.write('(fp_lib_table\n  (lib (name "sws")(type "KiCad")(uri "${KIPRJMOD}/../lib/sws.pretty")(options "")(descr "Placeholder footprints, drawn at layout"))\n)\n')


def write_symbol_library(symdefs: list[SymDef], path: str):
    """Project library so the symbols can be edited and reused in KiCad."""
    L = ['(kicad_symbol_lib (version 20220914) (generator kicad_gen_py)']
    for s in sorted(symdefs, key=lambda s: s.name):
        txt = sym_lib_text(s, indent="  ")
        L.append(txt.replace(q(s.lib_id), q(s.name), 1))
    L.append(")")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
