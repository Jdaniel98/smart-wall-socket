#!/usr/bin/env python3
"""Worst-case corners for scheme F. Firmware uses nominal constants; k0 is either the
design value or the unit's own value measured at end-of-line (230 V, 25 C, correct wiring)."""
import json
from polarity_f import sim, estimate, classify

def down(**o):  # push the estimated ratio down
    d = dict(cf=0.95, karm=1.2, kA=1.02, kB=0.98, rs=46.53e3, rsb=47.47e3, r21=446.5e3,
             v33=3.366, ladder=1.01, vosA=0.007, vosB=0.007, tj=0.0, meas=1.01)
    d.update(o); return d
def up(**o):    # push it up
    d = dict(cf=1.0, karm=0.8, kA=0.98, kB=1.02, rs=47.47e3, rsb=46.53e3, r21=493.5e3,
             v33=3.234, ladder=0.99, vosA=-0.007, vosB=-0.007, tj=85.0, meas=0.99)
    d.update(o); return d

def unit_k0(c):
    """End-of-line calibration of this unit: same parts, 230 V, 25 C, clean sine, correct wiring."""
    cal = {k: v for k, v in c.items() if k in ("karm", "kA", "kB", "rs", "rsb", "r21", "v33", "ladder", "vosA", "vosB")}
    r = sim("correct", vm=230, cf=1.0, tj=25.0, **cal)
    return estimate(r["da"], r["db"], 230 * c["meas"])

r = sim("correct"); K0_DESIGN = estimate(r["da"], r["db"], 230)

cases = []
for vm in (185, 207, 253, 265):
    for ven in (0, 10, 20, 30):
        cases.append(("correct", "correct", down(vm=vm, ven=ven)))
for ven in (10, 20, 30, 50):
    cases.append(("swapped", "swapped", up(vm=253, ven=ven)))
for vm in (185, 207, 253, 265):
    cases.append(("noearth", "noearth", up(vm=vm)))
    cases.append(("noearth", "noearth", down(vm=vm)))

rows = []
for want, w, c in cases:
    kw = {k: v for k, v in c.items() if k != "meas"}
    r = sim(w, **kw)
    k = estimate(r["da"], r["db"], kw["vm"] * c["meas"])
    kd, ku = k / K0_DESIGN, k / unit_k0(c)
    rows.append(dict(want=want, vm=kw["vm"], ven=kw.get("ven", 0), corner="down" if c["karm"] > 1 else "up",
                     ratio_design=round(kd, 3), ratio_cal=round(ku, 3),
                     ok_design=classify(kd) == want, ok_cal=classify(ku) == want))
    print(rows[-1])
json.dump(rows, open("polarity_f_corners.json", "w"), indent=1)
for want in ("correct", "noearth", "swapped"):
    sub = [x for x in rows if x["want"] == want]
    print(f"{want:8s} design k0: {sum(x['ok_design'] for x in sub)}/{len(sub)}  ratio {min(x['ratio_design'] for x in sub):.2f}-{max(x['ratio_design'] for x in sub):.2f}"
          f"   calibrated: {sum(x['ok_cal'] for x in sub)}/{len(sub)}  ratio {min(x['ratio_cal'] for x in sub):.2f}-{max(x['ratio_cal'] for x in sub):.2f}")
