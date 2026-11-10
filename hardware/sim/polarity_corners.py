#!/usr/bin/env python3
"""Worst-case corners for the polarity check. Each corner pushes the peak voltage
toward the threshold that would misclassify that wiring case."""
import json, sys
from polarity import run

topo = sys.argv[1] if len(sys.argv) > 1 else "E"
HOT_LEAK = 15.0  # extra uA at 3 V reverse on top of the model's own leakage at 85 C (pessimistic)

def lo(vm, ven, karm, tj, leak):   # push peak DOWN
    return dict(vm=vm, ven=ven, cf=0.95, karm=karm, r17=19.8e3, r20=20.2e3, r21=0.95e6,
                v33=3.366, vos=0.007, tj=tj, leak_uA=leak)
def hi(vm, ven, karm, tj, leak):   # push peak UP
    return dict(vm=vm, ven=ven, cf=1.0, karm=karm, r17=20.2e3, r20=19.8e3, r21=1.05e6,
                v33=3.234, vos=-0.007, tj=tj, leak_uA=leak)

cases = []
# correct wiring must stay A=1 B=1 (peak pushed down; positive ven = earth offset in phase with neutral)
for vm in (185, 207):
    for ven in (0, 10, 30):
        for karm in (1.0, 1.2):
            for tj, leak in ((25, 0), (85, 0), (85, HOT_LEAK)):
                cases.append(("correct", "correct", lo(vm, ven, karm, tj, leak)))
# swapped must stay A=0 B=0 (peak pushed up by earth-neutral offset)
for ven in (5, 10, 20, 30, 50):
    for karm in (0.8, 1.0):
        for tj in (25, 85):
            cases.append(("swapped", "swapped", hi(253, ven, karm, tj, 0)))
# no earth must read A=0 B=1: high corner tests bit A, low corner tests bit B
for vm in (253, 265):
    for karm, kA, kB in ((0.8, 0.98, 1.02), (1.0, 0.98, 1.02)):
        c = hi(vm, 0, karm, 25, 0); c.update(kA=kA, kB=kB)
        cases.append(("noearth", "noearth", c))
for vm in (185, 207):
    for karm, kA, kB in ((1.2, 1.02, 0.98), (1.0, 1.02, 0.98)):
        for tj, leak in ((25, 0), (85, 0), (85, HOT_LEAK)):
            c = lo(vm, 0, karm, tj, leak); c.update(kA=kA, kB=kB)
            cases.append(("noearth", "noearth", c))

res = []
for want, w, kw in cases:
    r = run(topo, w, **kw)
    ok = r["cls"] == want
    res.append(dict(want=want, got=r["cls"], ok=ok, pk=round(r["pkavg"], 3), **{k: kw[k] for k in ("vm", "ven", "karm", "tj", "leak_uA")}))
    if not ok:
        print("FAIL", res[-1])
for want in ("correct", "swapped", "noearth"):
    sub = [r for r in res if r["want"] == want]
    pks = [r["pk"] for r in sub]
    print(f"{topo} {want:8s} {sum(r['ok'] for r in sub)}/{len(sub)} pass, peak {min(pks):.3f} to {max(pks):.3f} V")
json.dump(res, open(f"polarity_corners_{topo}.json", "w"), indent=1)
