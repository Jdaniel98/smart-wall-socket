#!/usr/bin/env python3
"""
Generate the EVT1 KiCad projects, the symbol library and the BOMs.

    python3 hardware/tools/gen.py           # writes hardware/evt1/...
    python3 hardware/tools/verify.py        # exports netlists with kicad-cli and checks them
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from kicad_gen import write_symbol_library  # noqa: E402
from layout import write_project  # noqa: E402
import evt1_design as d  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "evt1"))
DATE = "2026-11-10"
REV = "EVT1-draft-E"


def all_parts(proj):
    for sh in proj.sheets:
        for b in sh.blocks:
            for p in b.parts:
                yield sh, b, p


def write_bom(proj, folder):
    groups = {}
    for sh, b, p in all_parts(proj):
        if p.virtual:
            continue
        key = (p.value, p.footprint, p.lcsc, p.mpn, p.mfr, p.dnp, p.verified)
        groups.setdefault(key, []).append(p)

    def refkey(r):
        import re
        m = re.match(r"([A-Z#]+)(\d+)", r)
        return (m.group(1), int(m.group(2))) if m else (r, 0)

    rows = []
    for (val, fp, lcsc, mpn, mfr, dnp, ver), parts in groups.items():
        refs = sorted((p.ref for p in parts), key=refkey)
        notes = "; ".join(sorted({p.note for p in parts if p.note}))
        rows.append(dict(refs=refs, value=val, fp=fp, lcsc=lcsc, mpn=mpn, mfr=mfr, dnp=dnp,
                         ver=ver, qty=len(parts), notes=notes))
    rows.sort(key=lambda r: refkey(r["refs"][0]))

    # JLCPCB assembly format: fitted SMD parts only, placeholders excluded.
    with open(os.path.join(folder, f"{proj.name}-bom-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in rows:
            if r["dnp"] or r["fp"].startswith("sws:"):
                continue
            w.writerow([r["value"], ",".join(r["refs"]), r["fp"].split(":")[-1], r["lcsc"]])

    with open(os.path.join(folder, f"{proj.name}-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Designators", "Value", "MPN", "Manufacturer", "LCSC", "LCSC checked",
                    "Footprint", "Fitted", "Notes"])
        for r in rows:
            chk = {"yes": "yes, 10 Nov 2026", "plan": "in EVT plan, reconfirm"}.get(r["ver"], "")
            if r["lcsc"] and not chk:
                chk = "JLC basic, confirm at order"
            w.writerow([r["qty"], " ".join(r["refs"]), r["value"], r["mpn"], r["mfr"], r["lcsc"] or "to assign",
                        chk, r["fp"], "DNP" if r["dnp"] else "yes", r["notes"]])
    return rows


def main():
    os.makedirs(os.path.join(OUT, "lib"), exist_ok=True)
    syms = {}
    for proj in d.PROJECTS:
        folder = os.path.join(OUT, proj.name.replace("sws-", ""))
        for f in os.listdir(folder) if os.path.isdir(folder) else []:
            if f.endswith(".kicad_sch"):
                os.remove(os.path.join(folder, f))
        paper, failed, used = write_project(proj, folder, DATE, REV)
        rows = write_bom(proj, folder)
        n = sum(r["qty"] for r in rows)
        print(f"{proj.name}: one {paper} sheet, {n} parts, {len(rows)} BOM lines, "
              f"{failed} connections drawn as labels -> {folder}")
        for s in used:
            syms[s.name] = s
    write_symbol_library(list(syms.values()), os.path.join(OUT, "lib", "sws.kicad_sym"))
    print(f"library: {len(syms)} symbols")


if __name__ == "__main__":
    main()
