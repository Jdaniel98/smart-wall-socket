"""
Single-sheet schematic writer: each block in a titled frame, parts placed in
rows, nets drawn as real wires by a small grid router, rails shown with power
symbols, signals that leave a block shown with flag labels.

All geometry is on the 1.27 mm grid ("cells", schematic orientation, y down).
Anything the router cannot draw falls back to labels, which are electrically
identical; verify.py checks the exported netlist either way.
"""
from __future__ import annotations

import heapq
import json
import math
import os
import textwrap

from kicad_gen import (CHAR_W, FONT, G, PWR_FLAG_LIB, Part, Project, SymDef, new_uuid,
                       power_lib_text, power_value_pos, q, sym_lib_text)

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
OUT_OF = {0: (-1, 0), 180: (1, 0), 270: (0, -1), 90: (0, 1)}


def mm(c: int) -> float:
    return round(c * G, 4)


def cells(v_mm: float) -> int:
    return int(math.ceil(v_mm / G - 1e-6))


def axis(d):
    return "h" if d[1] == 0 else "v"


# --------------------------------------------------------------------------
# Placed items
# --------------------------------------------------------------------------

class Placed:
    def __init__(self, part: Part, sym: SymDef, ox: int, oy: int):
        self.part, self.sym, self.ox, self.oy = part, sym, ox, oy

    def terms(self):
        out = []
        for pin in self.sym.pins:
            c = (self.ox + round(pin.x / G), self.oy - round(pin.y / G))
            out.append((pin, c, OUT_OF[pin.angle]))
        return out

    def body_cells(self):
        x0, y0, x1, y1 = self.sym.bbox()
        cs = set()
        for x in range(self.ox + math.floor(x0 / G), self.ox + math.ceil(x1 / G) + 1):
            for y in range(self.oy - math.ceil(y1 / G), self.oy - math.floor(y0 / G) + 1):
                cs.add((x, y))
        for pin, c, d in self.terms():
            n = 2 if self.sym.kind != "TP" else 1
            for k in range(1, n + 1):
                cs.add((c[0] - d[0] * k, c[1] - d[1] * k))
        return cs

    def texts(self):
        """(prop, text, x_mm, y_mm, justify) for Reference and Value."""
        s, p = self.sym, self.part
        val = p.value + (" (DNP)" if p.dnp else "")
        X, Y = mm(self.ox), mm(self.oy)
        if s.kind == "box":
            x0, y0, x1, y1 = s.bbox()
            return [("Reference", p.ref, X, Y - y1 - 1.6, "center"),
                    ("Value", val, X, Y - y0 + 1.6, "center")]
        if s.variant in ("V", "VR"):
            return [("Reference", p.ref, X + 2.2, Y - 0.9, "left"),
                    ("Value", val, X + 2.2, Y + 0.9, "left")]
        return [("Reference", p.ref, X, Y - 2.8, "center"),
                ("Value", val, X, Y + 2.8, "center")]

    def text_cells(self):
        cs = set()
        for _, t, x, y, j in self.texts():
            w = len(t) * CHAR_W
            xa = x - w / 2 if j == "center" else x
            for cx in range(math.floor(xa / G), math.ceil((xa + w) / G) + 1):
                for cy in range(math.floor((y - 0.8) / G), math.ceil((y + 0.8) / G) + 1):
                    cs.add((cx, cy))
        return cs


class BlockLayout:
    """Places and routes one block in local cell coordinates."""

    def __init__(self, block, rails: dict, external: set, bus_name: str):
        self.block, self.rails, self.external = block, rails, external
        self.placed: list[Placed] = []
        self.blocked: set = set()
        self.term: dict = {}         # cell -> net
        self.term_dir: dict = {}     # cell -> outward dir (pins only)
        self.occ: dict = {}          # cell -> {net: set(axes)}
        self.nodes: dict = {}        # cell -> set(nets)
        self.segs: list = []         # [net, (x1,y1), (x2,y2)]
        self.labels: list = []       # (net, cell, angle)
        self.powers: list = []       # (net, cell)
        self.ncs: list = []          # cells
        self.bounds = None
        self.failed = []

    # ---------------- placement ----------------
    def _variant(self, p: Part) -> SymDef:
        s = p.sym
        if not hasattr(s, "variants"):
            return s
        n1, n2 = (p.conn.get(pin.nums[0]) for pin in s.pins[:2])
        r1, r2 = self.rails.get(n1), self.rails.get(n2)
        if r1 == "rail" or r2 == "gnd":
            return s.variants["V"]      # pin 1 on top
        if r2 == "rail" or r1 == "gnd":
            return s.variants["VR"]     # pin 2 on top
        return s.variants["H"]

    def place(self):
        parts = self.block.parts
        var = {p.ref: self._variant(p) for p in parts}
        # chains of horizontal two-pin parts joined by private two-pin nets
        tcount = {}
        for p in parts:
            for pin in p.sym.pins:
                n = p.conn.get(pin.nums[0])
                if n and n != "NC":
                    tcount[n] = tcount.get(n, 0) + 1
        horiz = {p.ref for p in parts if var[p.ref].variant == "H" and hasattr(p.sym, "variants")}
        link = {}
        for n, c in tcount.items():
            if c != 2 or n in self.external or n in self.rails:
                continue
            ends = [(p.ref, k) for p in parts for k, v in p.conn.items() if v == n]
            if len(ends) == 2 and all(r in horiz for r, _ in ends) and ends[0][0] != ends[1][0]:
                (a, ka), (b, kb) = ends
                link.setdefault(a, []).append((b, ka, kb))
                link.setdefault(b, []).append((a, kb, ka))
        byref = {p.ref: p for p in parts}
        seen, units = set(), []
        for p in parts:
            if p.ref in seen:
                continue
            if p.ref in link and len(link[p.ref]) <= 2:
                # walk to one end of the chain
                start, prev = p.ref, None
                while True:
                    nxt = [l for l in link[start] if l[0] != prev and len(link.get(l[0], [])) <= 2]
                    if len(link[start]) == 1 or not nxt or start in seen:
                        break
                    prev, start = start, nxt[0][0]
                    if start == p.ref:
                        break
                chain, cur, prev, left_pin = [], start, None, None
                while cur and cur not in seen:
                    seen.add(cur)
                    outs = [l for l in link.get(cur, []) if l[0] != prev]
                    right_pin = outs[0][1] if outs else None
                    # choose orientation: link to previous on the left
                    s = byref[cur].sym
                    first, second = (pin.nums[0] for pin in s.pins[:2])
                    if left_pin is not None:
                        v = "H" if left_pin == first else "HR"
                    elif right_pin is not None:
                        v = "H" if right_pin == second else "HR"
                    else:
                        v = "H"
                    chain.append((byref[cur], s.variants[v]))
                    if not outs:
                        break
                    prev, (cur, _, left_pin) = cur, outs[0]
                    if cur in seen:
                        break
                units.append(chain)
            else:
                seen.add(p.ref)
                units.append([(p, var[p.ref])])

        # order units by connectivity, biggest part first
        def unit_nets(u):
            return {n for p, _ in u for n in p.conn.values() if n and n != "NC" and n not in self.rails}
        def rail_only(u):
            return all(n in self.rails for p, _ in u for n in p.conn.values() if n and n != "NC")
        rail_units = [u for u in units if rail_only(u)]
        units = [u for u in units if not rail_only(u)] or rail_units[:1]
        rail_units = [u for u in rail_units if u not in units]
        units.sort(key=lambda u: -max(len(s.pins) for _, s in u))
        order, rest = [units[0]], units[1:]
        while rest:
            have = set().union(*(unit_nets(u) for u in order))
            rest.sort(key=lambda u: -len(unit_nets(u) & have))
            order.append(rest.pop(0))

        # decoupling capacitors go straight after the IC whose supply they share
        for ru in rail_units:
            rn = {n for p, _ in ru for n in p.conn.values() if n in self.rails}
            at = len(order)
            for i, u in enumerate(order):
                if any(s.kind == "box" and rn <= {p.conn.get(pp.nums[0]) for pp in s.pins} for p, s in u):
                    at = i + 1
                    while at < len(order) and rail_only(order[at]):
                        at += 1
                    break
            order.insert(at, ru)
        self._rail_only = rail_only

        # unit geometry
        def unit_place(u, x, y):
            """Place a unit with its top-left corner at (x, y); return its extent."""
            items, cx = [], x
            for p, s in u:
                x0, y0, x1, y1 = s.bbox()
                pins = [pp.x for pp in s.pins] + [x0, x1]
                left = math.floor(min(pins) / G)
                right = math.ceil(max(pins) / G)
                tw = max(len(p.value) + (6 if p.dnp else 0), len(p.ref)) * CHAR_W / G
                if s.variant in ("V", "VR"):
                    right = max(right, 2 + math.ceil(tw))
                else:
                    half = math.ceil(tw / 2)
                    left, right = min(left, -half), max(right, half)
                tops = [pp.y for pp in s.pins] + [y1]
                bots = [pp.y for pp in s.pins] + [y0]
                top = math.ceil(max(tops) / G) + 3
                bot = math.ceil(-min(bots) / G) + 3
                items.append((p, s, left, right, top, bot))
            height = max(t + b for *_, t, b in items)
            top_max = max(t for *_, t, b in items)
            out = []
            for p, s, left, right, top, bot in items:
                ox = cx - left
                oy = y + top_max
                out.append(Placed(p, s, ox, oy))
                cx = ox + right + 2
            return out, cx - x, height

        def flow(units, x0, limit=None):
            """Place units in rows starting at x0; return placements and total width."""
            if not units:
                return [], 0
            geo, area = [], 0
            for u in units:
                _, w, h = unit_place(u, 0, 0)
                geo.append((w, h))
                area += (w + 10) * (h + 6)
            wmax = max(w for w, _ in geo)
            row_w = limit or max(wmax, min(110, max(45, int(math.sqrt(area) * 1.4))))
            row_w = max(row_w, wmax)
            out, x, y, rh, right = [], x0, 0, 0, x0
            for u, (w, h) in zip(units, geo):
                if x > x0 and x + w > x0 + row_w:
                    x, y, rh = x0, y + rh + 6, 0
                pl, w, h = unit_place(u, x, y)
                out += pl
                right = max(right, x + w)
                x += w + 10
                rh = max(rh, h)
            return out, right - x0

        main = order[0]
        if len(main) == 1 and len(main[0][1].pins) >= 8:
            # big part in the middle; parts that hang off its left pins go on its left
            mp, ms = main[0]
            pl, mw, mh = unit_place(main, 0, 0)
            self.placed += pl
            lnets = {mp.conn.get(pp.nums[0]) for pp in ms.pins if pp.side == "L"} - set(self.rails)
            rnets = {mp.conn.get(pp.nums[0]) for pp in ms.pins if pp.side == "R"} - set(self.rails)
            side = {}
            pside = next((pp.side for pp in ms.pins if self.rails.get(mp.conn.get(pp.nums[0])) == "rail"), "R")
            for u in order[1:]:
                if rail_only(u):
                    side[id(u)] = pside
                    continue
                un = unit_nets(u)
                l, r = len(un & lnets), len(un & rnets)
                if l != r:
                    side[id(u)] = "L" if l > r else "R"
                else:
                    near = [side[id(v)] for v in order[1:] if id(v) in side and unit_nets(v) & un]
                    side[id(u)] = near[0] if near else "R"
            left = [u for u in order[1:] if side[id(u)] == "L"]
            right = [u for u in order[1:] if side[id(u)] == "R"]
            pr, _ = flow(right, mw + 14)
            self.placed += pr
            pl_, wl = flow(left, 0, limit=60)
            for p in pl_:
                p.ox -= wl + 14
            self.placed += pl_
        else:
            p_, _ = flow(order, 0)
            self.placed += p_

        # obstacles and terminals
        for pl in self.placed:
            self.blocked |= pl.body_cells() | pl.text_cells()
        xs = [c[0] for pl in self.placed for c in pl.body_cells() | pl.text_cells()]
        ys = [c[1] for pl in self.placed for c in pl.body_cells() | pl.text_cells()]
        self.bounds = (min(xs) - 14, min(ys) - 8, max(xs) + 14, max(ys) + 8)
        for pl in self.placed:
            for pin, c, d in pl.terms():
                net = pl.part.conn.get(pin.nums[0])
                if net is None or net == "NC":
                    if net == "NC" and pin.etype != "no_connect":
                        self.ncs.append(c)
                    self.blocked.add(c)
                    continue
                self.blocked.discard(c)
                self.term[c] = net
                self.term_dir[c] = d

    # ---------------- helpers ----------------
    def free(self, c, allow_net=None):
        if c in self.blocked:
            return False
        if c in self.term and self.term[c] != allow_net:
            return False
        o = self.occ.get(c)
        if o and any(n != allow_net for n in o):
            return False
        x0, y0, x1, y1 = self.bounds
        return x0 <= c[0] <= x1 and y0 <= c[1] <= y1

    def _add_seg(self, net, a, b):
        if a == b:
            return
        self.segs.append([net, a, b])
        ax = "h" if a[1] == b[1] else "v"
        for c in _cells_between(a, b):
            self.occ.setdefault(c, {}).setdefault(net, set()).add(ax)
        for c in (a, b):
            self.nodes.setdefault(c, set()).add(net)

    def _split_at(self, net, c):
        for s in self.segs:
            n, a, b = s
            if n == net and c in _cells_between(a, b) and c not in (a, b):
                s[2] = c
                self.segs.append([net, c, b])
                self.nodes.setdefault(c, set()).add(net)
                return

    def commit(self, net, path):
        """path: list of cells; commit as merged segments, splitting at a mid-wire end."""
        if len(path) < 2:
            return
        end = path[-1]
        if end in self.occ and net in self.occ[end] and net not in self.nodes.get(end, set()):
            self._split_at(net, end)
        if path[0] in self.occ and net in self.occ[path[0]] and net not in self.nodes.get(path[0], set()):
            self._split_at(net, path[0])
        start = path[0]
        for i in range(1, len(path) - 1):
            d1 = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
            d2 = (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
            if d1 != d2:
                self._add_seg(net, start, path[i])
                start = path[i]
        self._add_seg(net, start, end)

    # ---------------- router ----------------
    def astar(self, net, start, targets):
        sdir = self.term_dir.get(start)
        tx = [t[0] for t in targets]
        ty = [t[1] for t in targets]
        bx0, bx1, by0, by1 = min(tx), max(tx), min(ty), max(ty)

        def h(c):
            dx = max(bx0 - c[0], 0, c[0] - bx1)
            dy = max(by0 - c[1], 0, c[1] - by1)
            return dx + dy

        x0, y0, x1, y1 = self.bounds
        openq = [(h(start), 0, start, None)]
        best = {(start, None): 0}
        prev = {}
        n_exp = 0
        while openq:
            f, g, c, din = heapq.heappop(openq)
            if g > best.get((c, din), 1e9):
                continue
            if c in targets and c != start:
                path = [c]
                k = (c, din)
                while k in prev:
                    k = prev[k]
                    path.append(k[0])
                return path[::-1]
            n_exp += 1
            if n_exp > 200000:
                return None
            for d in DIRS:
                if din is None and sdir is not None and d != sdir:
                    continue
                if din is not None and d == (-din[0], -din[1]):
                    continue
                b = (c[0] + d[0], c[1] + d[1])
                if not (x0 <= b[0] <= x1 and y0 <= b[1] <= y1):
                    continue
                bend = din is not None and d != din
                if bend:
                    o = self.occ.get(c, {})
                    if any(n != net for n in o):
                        continue
                if b in self.blocked:
                    continue
                if b in self.term:
                    if self.term[b] != net or b not in targets:
                        continue
                    if b in self.term_dir and d != (-self.term_dir[b][0], -self.term_dir[b][1]):
                        continue
                cost = 1 + (4 if bend else 0)
                o = self.occ.get(b, {})
                bad = False
                for n, axes in o.items():
                    if n == net:
                        continue
                    if axis(d) in axes or n in self.nodes.get(b, set()):
                        bad = True
                        break
                    cost += 6
                if bad:
                    continue
                if b in targets and o and net not in o and b not in self.term:
                    continue
                ng = g + cost
                if ng < best.get((b, d), 1e9):
                    best[(b, d)] = ng
                    prev[(b, d)] = (c, din)
                    heapq.heappush(openq, (ng + h(b), ng, b, d))
        return None

    def route(self):
        nets = {}
        for c, n in self.term.items():
            if n not in self.rails:
                nets.setdefault(n, []).append(c)
        comps = {}

        def span(n):
            cs = nets[n]
            return (max(x for x, _ in cs) - min(x for x, _ in cs)) + (max(y for _, y in cs) - min(y for _, y in cs))

        for n in sorted(nets, key=span):
            ts = nets[n]
            if len(ts) < 2:
                comps[n] = [[ts[0]]]
                continue
            tree = {ts[0]}
            groups = [[ts[0]]]
            pending = ts[1:]
            while pending:
                pending.sort(key=lambda t: min(abs(t[0] - c[0]) + abs(t[1] - c[1]) for c in tree))
                t = pending.pop(0)
                path = self.astar(n, t, tree)
                if path is None:
                    groups.append([t])
                    self.failed.append((n, t))
                    continue
                self.commit(n, path)
                tree |= set(path)
                groups[0].append(t)
            comps[n] = groups
        self.comps = comps

    # ---------------- power symbols, labels ----------------
    def _power_area(self, c, d, net):
        n = math.ceil((len(net) * CHAR_W + 4.0) / G)
        half = max(2, math.ceil(len(net) * CHAR_W / 2 / G) + 1)
        if d in ((0, 1), (0, -1)):
            return {(c[0] + i, c[1] + d[1] * j) for i in range(-half, half + 1) for j in range(1, 6)}
        return {(c[0] + d[0] * i, c[1] + j) for i in range(1, n + 1) for j in (-1, 0, 1)}

    def place_powers(self):
        names = {(0, -1): "up", (0, 1): "down", (1, 0): "right", (-1, 0): "left"}
        for c, net in sorted(((c, n) for c, n in self.term.items() if n in self.rails), key=lambda t: (t[0][1], t[0][0])):
            d = self.term_dir[c]
            for k in range(0, 12):
                end = (c[0] + d[0] * k, c[1] + d[1] * k)
                path = [(c[0] + d[0] * i, c[1] + d[1] * i) for i in range(k + 1)]
                area = self._power_area(end, d, net)
                if all(self.free(p) for p in path[1:]) and all(self.free(a) for a in area):
                    break
            else:
                end, path, area = c, [c], set()
            self.commit(net, path)
            self.powers.append((net, end, names[d]))
            self.blocked |= area
            self.term.setdefault(end, net)

    def _label_area(self, c, d, net):
        n = math.ceil((len(net) * CHAR_W + 3.0) / G) + 1
        return {(c[0] + d * i, c[1] + j) for i in range(1, n + 1) for j in (-1, 0, 1)}

    def attach_label(self, net, cells_):
        cands = []
        pins = [c for c in cells_ if c in self.term_dir]
        wires = [c for c in self.occ if net in self.occ[c] and c in cells_]
        for c in pins + wires:
            if c in self.term_dir:
                d = self.term_dir[c]
                if d[1] == 0:
                    for k in range(1, 14):
                        cands.append((k, [(c[0] + d[0] * i, c[1]) for i in range(k + 1)], d[0]))
                else:
                    for k in (1, 2, 3):
                        for s in (1, -1):
                            for j in range(1, 10):
                                p = [(c[0], c[1] + d[1] * i) for i in range(k + 1)]
                                p += [(c[0] + s * i, c[1] + d[1] * k) for i in range(1, j + 1)]
                                cands.append((k + j + 1, p, s))
            else:
                axes = self.occ[c][net]
                if "h" in axes:
                    continue
                for s in (1, -1):
                    for k in range(2, 14):
                        cands.append((k + 2, [(c[0] + s * i, c[1]) for i in range(k + 1)], s))
        cands.sort(key=lambda t: t[0])
        for _, path, s in cands:
            if not all(self.free(p) for p in path[1:]):
                continue
            area = self._label_area(path[-1], s, net)
            if all(self.free(a) for a in area):
                self.commit(net, path)
                self.labels.append((net, path[-1], 0 if s > 0 else 180))
                self.blocked |= area
                return
        # fallback: label on the first cell, electrically fine
        c = cells_[0]
        d = self.term_dir.get(c, (1, 0))
        self.labels.append((net, c, 0 if d[0] >= 0 else 180))

    def labels_pass(self):
        for n, groups in self.comps.items():
            if n in self.external or len(groups) > 1:
                for g in groups:
                    cells_ = list(g)
                    # include the wire cells of this component
                    if len(groups) == 1:
                        cells_ += [c for c in self.occ if n in self.occ[c]]
                    self.attach_label(n, cells_)

    def run(self):
        self.place()
        self.place_powers()
        self.route()
        self.labels_pass()

    def extent(self):
        xs, ys = [], []
        for pl in self.placed:
            for c in pl.body_cells() | pl.text_cells():
                xs.append(c[0])
                ys.append(c[1])
        for _, a, b in self.segs:
            xs += [a[0], b[0]]
            ys += [a[1], b[1]]
        for c in self.blocked:
            xs.append(c[0])
            ys.append(c[1])
        return min(xs), min(ys), max(xs), max(ys)


def _cells_between(a, b):
    if a[1] == b[1]:
        s = 1 if b[0] >= a[0] else -1
        return [(x, a[1]) for x in range(a[0], b[0] + s, s)]
    s = 1 if b[1] >= a[1] else -1
    return [(a[0], y) for y in range(a[1], b[1] + s, s)]


# --------------------------------------------------------------------------
# Sheet
# --------------------------------------------------------------------------

PAPERS = [("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841)]


def write_project(proj: Project, outdir: str, date: str, rev: str):
    os.makedirs(outdir, exist_ok=True)
    root = new_uuid(proj.name + "/root")
    path = f"/{root}"

    # nets used in more than one block are flagged with labels
    use = {}
    for sh in proj.sheets:
        for bi, b in enumerate(sh.blocks):
            for p in b.parts:
                for n in p.conn.values():
                    if n and n != "NC":
                        use.setdefault(n, set()).add(id(b))
    external = {n for n, s in use.items() if len(s) > 1}

    layouts = []
    for sh in proj.sheets:
        col = []
        for b in sh.blocks:
            bl = BlockLayout(b, proj.rails, external, sh.name)
            bl.run()
            col.append(bl)
        layouts.append(col)

    # frame geometry per column
    gap = 6
    col_specs = []
    for col in layouts:
        widths = []
        for bl in col:
            x0, y0, x1, y1 = bl.extent()
            widths.append(x1 - x0 + 5)
        col_specs.append(max(widths + [60]))

    frames = []   # (bl, frame_x, frame_y, w, h, dx, dy, title_lines)
    X = 16
    page_h = 0
    for ci, (col, cw) in enumerate(zip(layouts, col_specs)):
        Y = 28
        for bl in col:
            x0, y0, x1, y1 = bl.extent()
            chars = int(cw * G / (CHAR_W * 1.02))
            notes = []
            for para in bl.block.notes.split("\n"):
                notes += textwrap.wrap(para, chars) or [""]
            head = 4 + 2 * len(notes) + 2
            h = (y1 - y0) + head + 4
            dx = X + 2 - x0 + ((cw - (x1 - x0 + 5)) // 2)
            dy = Y + head - y0
            frames.append((bl, X, Y, cw, h, dx, dy, notes))
            Y += h + gap
        page_h = max(page_h, Y)
        X += cw + 10
    page_w = X + 6

    # board notes and ERC flags in a final frame under the shortest column
    xs_ = [16]
    for cw in col_specs[:-1]:
        xs_.append(xs_[-1] + cw + 10)
    bottoms = [max([f[2] + f[4] for f in frames if f[1] == x] + [28]) + gap for x in xs_]
    nci = min(range(len(xs_)), key=lambda i: bottoms[i])
    nfx, nfy, nfw = xs_[nci], bottoms[nci], col_specs[nci]
    nnotes = []
    for para in proj.root_notes.split("\n"):
        nnotes += textwrap.wrap(para, int(nfw * G / CHAR_W)) or [""]
    nflags = [n for sh in proj.sheets for n in sh.flags]
    nfh = 4 + 2 * len(nnotes) + (14 if nflags else 2)
    page_h = max(page_h, nfy + nfh + 2)
    total_w_mm, total_h_mm = mm(page_w) + 10, mm(page_h) + 42
    paper = ("User", max(420, math.ceil(total_w_mm / 10) * 10), max(297, math.ceil(total_h_mm / 10) * 10))

    L = [f"(kicad_sch (version 20230121) (generator eeschema)", f"  (uuid {root})"]
    if paper[0] == "User":
        L.append(f'  (paper "User" {paper[1]} {paper[2]})')
    else:
        L.append(f'  (paper "{paper[0]}")')
    L.append(f'  (title_block (title {q(proj.title)}) (date "{date}") (rev "{rev}") (company "Aether Labs") '
             f'(comment 1 "Smart Wall Socket. DRAFT for engineering review, not a release.") (comment 2 {q(proj.warning)}))')

    # library symbols
    syms, pwr = {}, {}
    for col in layouts:
        for bl in col:
            for pl in bl.placed:
                syms[pl.sym.name] = pl.sym
            for n, _, d in bl.powers:
                pwr[(n, d)] = proj.rails[n]
    for sh in proj.sheets:
        for n in sh.flags:
            st = proj.rails.get(n, "rail")
            pwr[(n, "up" if st == "rail" else "down")] = st
    L.append("  (lib_symbols")
    for s in syms.values():
        L.append(sym_lib_text(s))
    pwr_ids = {}
    for (n, d), style in sorted(pwr.items()):
        txt, lid = power_lib_text(n, style, d)
        pwr_ids[(n, d)] = lid
        L.append(txt)
    L.append(PWR_FLAG_LIB)
    L.append("  )")

    def T(txt, x, y, size=1.27, bold=False, just="left top"):
        b = " bold" if bold else ""
        return (f'  (text {q(txt)} (at {x:.4f} {y:.4f} 0) (effects (font (size {size} {size}){b}) '
                f'(justify {just})) (uuid {new_uuid()}))')

    # column headers and barrier
    X = 16
    col_x = []
    for ci, (sh, cw) in enumerate(zip(proj.sheets, col_specs)):
        col_x.append(X)
        L.append(T(sh.name.upper(), mm(X), mm(20), 2.54, True))
        if sh.title:
            L.append(T(sh.title, mm(X), mm(23.5), 1.5))
        X += cw + 10
    if proj.barrier_after is not None:
        bx = mm(col_x[proj.barrier_after + 1] - 5)
        L.append(f'  (polyline (pts (xy {bx} {mm(18)}) (xy {bx} {mm(page_h)})) (stroke (width 0.6) (type dash)) (uuid {new_uuid()}))')
        L.append(T("REINFORCED BARRIER, 8 mm", bx + 1, mm(page_h) + 1, 1.8, True))

    pwr_n = [0]

    def power_sym(net, x, y, d=None):
        pwr_n[0] += 1
        ref = f"#PWR{pwr_n[0]:03d}"
        style = proj.rails.get(net, "rail")
        d = d or ("up" if style == "rail" else "down")
        (vx, vy), just = power_value_pos(style, d)
        jj = "" if just == "center" else f" (justify {just})"
        return "\n".join([
            f'  (symbol (lib_id {q(pwr_ids[(net, d)])}) (at {x:.4f} {y:.4f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {new_uuid()})',
            f'    (property "Reference" "{ref}" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) hide))',
            f'    (property "Value" {q(net)} (at {x + vx:.4f} {y - vy:.4f} 0) (effects (font (size 1.27 1.27)){jj}))',
            f'    (property "Footprint" "" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) hide))',
            f'    (property "Datasheet" "" (at {x:.4f} {y:.4f} 0) (effects (font (size 1.27 1.27)) hide))',
            f'    (pin "1" (uuid {new_uuid()}))',
            f'    (instances (project {q(proj.name)} (path {q(path)} (reference "{ref}") (unit 1))))',
            "  )"])

    tinted = {id(b) for sh in proj.sheets if sh.tint for b in sh.blocks}
    for (bl, fx, fy, w, h, dx, dy, notes) in frames:
        fill = "(fill (type color) (color 214 92 64 0.10))" if id(bl.block) in tinted else "(fill (type none))"
        L.append(f'  (rectangle (start {mm(fx)} {mm(fy)}) (end {mm(fx + w)} {mm(fy + h)}) '
                 f'(stroke (width 0.35) (type default)) {fill} (uuid {new_uuid()}))')
        L.append(T(bl.block.title.upper(), mm(fx + 1), mm(fy + 1), 1.8, True))
        if any(notes):
            L.append(T("\n".join(notes), mm(fx + 1), mm(fy + 4), 1.27))
        for pl in bl.placed:
            p, s = pl.part, pl.sym
            X, Y = mm(pl.ox + dx), mm(pl.oy + dy)
            dnp = "yes" if p.dnp else "no"
            u = new_uuid(f"{proj.name}/{p.ref}")
            L.append(f'  (symbol (lib_id {q(s.lib_id)}) (at {X} {Y} 0) (unit 1) (in_bom {"no" if (p.dnp or p.virtual) else "yes"}) '
                     f'(on_board yes) (dnp {dnp}) (uuid {u})')
            for prop, txt, tx, ty, j in pl.texts():
                jj = "" if j == "center" else " (justify left)"
                L.append(f'    (property {q(prop)} {q(txt)} (at {tx + mm(dx):.4f} {ty + mm(dy):.4f} 0) '
                         f'(effects (font (size {FONT} {FONT})){jj}))')
            for prop, v in (("Footprint", p.footprint), ("Datasheet", "~"), ("LCSC", p.lcsc), ("MPN", p.mpn),
                            ("Manufacturer", p.mfr), ("Notes", p.note)):
                L.append(f'    (property {q(prop)} {q(v)} (at {X} {Y} 0) (effects (font (size {FONT} {FONT})) hide))')
            for pin in s.pins:
                for num in pin.nums:
                    L.append(f'    (pin {q(num)} (uuid {new_uuid(f"{proj.name}/{p.ref}/{num}")}))')
            L.append(f'    (instances (project {q(proj.name)} (path {q(path)} (reference {q(p.ref)}) (unit 1))))')
            L.append("  )")
        for net, a, b in bl.segs:
            L.append(f'  (wire (pts (xy {mm(a[0] + dx)} {mm(a[1] + dy)}) (xy {mm(b[0] + dx)} {mm(b[1] + dy)})) '
                     f'(stroke (width 0) (type default)) (uuid {new_uuid()}))')
        # junctions where three or more connections meet
        deg = {}
        for net, a, b in bl.segs:
            for c in (a, b):
                deg[c] = deg.get(c, 0) + 1
        for c in bl.term:
            if c in deg:
                deg[c] += 1
        for c, k in deg.items():
            if k >= 3:
                L.append(f'  (junction (at {mm(c[0] + dx)} {mm(c[1] + dy)}) (diameter 0) (color 0 0 0 0) (uuid {new_uuid()}))')
        for net, c, d in bl.powers:
            L.append(power_sym(net, mm(c[0] + dx), mm(c[1] + dy), d))
        for net, c, ang in bl.labels:
            x, y = mm(c[0] + dx), mm(c[1] + dy)
            just = "left" if ang == 0 else "right"
            L.append(f'  (global_label {q(net)} (shape passive) (at {x} {y} {ang}) (fields_autoplaced) '
                     f'(effects (font (size {FONT} {FONT})) (justify {just})) (uuid {new_uuid()}) '
                     f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide)))')
        for c in bl.ncs:
            L.append(f"  (no_connect (at {mm(c[0] + dx)} {mm(c[1] + dy)}) (uuid {new_uuid()}))")

    # notes and ERC power flags below the last column
    fx, fy, fw, notes, flags, fh = nfx, nfy, nfw, nnotes, nflags, nfh
    L.append(f'  (rectangle (start {mm(fx)} {mm(fy)}) (end {mm(fx + fw)} {mm(fy + fh)}) '
             f'(stroke (width 0.35) (type default)) (fill (type none)) (uuid {new_uuid()}))')
    L.append(T("BOARD NOTES", mm(fx + 1), mm(fy + 1), 1.8, True))
    L.append(T("\n".join(notes), mm(fx + 1), mm(fy + 4), 1.27))
    for i, n in enumerate(flags):
        x = mm(fx + 6 + i * 16)
        y = mm(fy + fh - 6)
        style = proj.rails.get(n, "rail")
        L.append(power_sym(n, x, y))
        yf = y + (-2.54 if style == "gnd" else 2.54)
        L.append(f'  (wire (pts (xy {x} {y}) (xy {x} {yf:.4f})) (stroke (width 0) (type default)) (uuid {new_uuid()}))')
        ref = f"#FLG{i + 1:02d}"
        L.append(f'  (symbol (lib_id "power:PWR_FLAG") (at {x} {yf:.4f} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {new_uuid(proj.name + ref)})')
        L.append(f'    (property "Reference" "{ref}" (at {x} {yf:.4f} 0) (effects (font (size 1.27 1.27)) hide))')
        L.append(f'    (property "Value" "PWR_FLAG" (at {x} {yf - 3.81:.4f} 0) (effects (font (size 1.27 1.27)) hide))')
        L.append(f'    (property "Footprint" "" (at {x} {yf:.4f} 0) (effects (font (size 1.27 1.27)) hide))')
        L.append(f'    (property "Datasheet" "~" (at {x} {yf:.4f} 0) (effects (font (size 1.27 1.27)) hide))')
        L.append(f'    (pin "1" (uuid {new_uuid()}))')
        L.append(f'    (instances (project {q(proj.name)} (path {q(path)} (reference "{ref}") (unit 1))))')
        L.append("  )")
    if flags:
        L.append(T("ERC power flags", mm(fx + 1), mm(fy + fh - 12), 1.27))

    L.append('  (sheet_instances (path "/" (page "1")))')
    L.append(")")

    with open(os.path.join(outdir, proj.name + ".kicad_sch"), "w") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(outdir, proj.name + ".kicad_pro"), "w") as f:
        json.dump({"meta": {"filename": proj.name + ".kicad_pro", "version": 1},
                   "sheets": [[root, ""]]}, f, indent=2)
    with open(os.path.join(outdir, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (lib (name "sws")(type "KiCad")(uri "${KIPRJMOD}/../lib/sws.kicad_sym")(options "")(descr "Aether Labs Smart Wall Socket symbols"))\n)\n')
    with open(os.path.join(outdir, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (lib (name "sws")(type "KiCad")(uri "${KIPRJMOD}/../lib/sws.pretty")(options "")(descr "Placeholder footprints, drawn at layout"))\n)\n')
    failed = sum(len(bl.failed) for col in layouts for bl in col)
    return paper[0], failed, list(syms.values())
