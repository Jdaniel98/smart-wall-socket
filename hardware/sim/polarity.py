#!/usr/bin/env python3
"""
Polarity and earth check (rear board block 5): does it classify every wiring
case correctly across mains voltage, tolerances, temperature and earth-neutral
offset?

Hot-side ground is L_BUS (node 0). Mains is v(nf) relative to L_BUS.
  correct : L_BUS = live,    N_F = neutral, E = neutral + Ven
  swapped : L_BUS = neutral, N_F = live,    E = neutral + Ven  (= L_BUS + Ven)
  noearth : E floats; optional appliance Y-capacitor from E to N_F or to L_BUS

Two comparator topologies:
  "C" : draft C/D as drawn. Hysteresis R31/R33 (R32/R34) feeds the output back
        into the peak-detector node through 340 k.
  "E" : proposed fix. Signal to IN-, separate threshold dividers on IN+ with the
        hysteresis resistor from the output to the threshold node. Output is
        inverted (low = bit set).

Each run is a 1.5 s transient from cold (C12 discharged, as at power-on).
The classification is read from the comparator outputs at the end.
"""
import itertools, json, re, subprocess, sys

F = 50.0


def netlist(topo, wiring, vm=230.0, ven=0.0, cf=1.0, karm=1.0, kA=1.0, kB=1.0,
            r17=20e3, r20=20e3, r21=1e6, v33=3.3, vos=0.0, leak_uA=0.0,
            ycap=None, tj=25.0, thA=None, thB=None):
    vpk = vm * 2 ** 0.5 * cf
    vepk = ven * 2 ** 0.5
    s = [f"polarity {topo} {wiring}", "* (title)"]
    s.append(f".options temp={tj} reltol=1e-4")
    # mains, relative to L_BUS (= node 0)
    if wiring == "correct":
        s.append(f"Vn nf 0 SIN(0 {-vpk} {F})")          # N - L
        s.append(f"Ve e 0 SIN(0 {-vpk + vepk} {F})")    # E = N + Ven
    elif wiring == "swapped":
        s.append(f"Vn nf 0 SIN(0 {vpk} {F})")           # N_F carries live
        s.append(f"Ve e 0 SIN(0 {vepk} {F})")           # E = true neutral + Ven
    else:  # noearth: E is a floating node
        s.append(f"Vn nf 0 SIN(0 {-vpk} {F})")
        s.append("Rleak_e e 0 1e12")
        if ycap:
            side, c = ycap
            s.append(f"Cy e {'nf' if side == 'N' else '0'} {c}")
    ra = 4e6 * karm * kA
    rb = 4e6 * karm * kB
    s += [
        f"RarmA e pols {ra}", f"R17 pols 0 {r17}",
        f"RarmB e pb2 {rb}", f"R20 pb2 nf {r20}",
        "D2 0 pols DZ51",                       # zener: cathode pols, anode L_BUS
        "D3 pols pk DBAT",                      # BAT54WS: anode pols, cathode pk
        # extra reverse leakage of D3 (from pk to pols when reverse biased)
        f"Bleak pk pols I = {leak_uA * 1e-6} * max(v(pk)-v(pols),0)/3",
        "C12 pk 0 1u IC=0", f"R21 pk 0 {r21}",
        f"V33 v33 0 {v33}",
        "R25 oa v33 10k", "R26 ob v33 10k",
        "R31 pk ina 10k", "R32 pk inb 10k",
    ]
    if topo == "C":
        s += [
            "R22 v33 tha 220k", "R23 tha thb 68k", "R24 thb 0 30k",
            "R33 oa ina 330k", "R34 ob inb 330k",
            # LMV393 open drain: sinks when IN+ (signal) < IN- (threshold)
            f"BcA oa 0 I = v(oa)/30 * 0.5*(1 - tanh((v(ina)-v(tha)-({vos}))/2m))",
            f"BcB ob 0 I = v(ob)/30 * 0.5*(1 - tanh((v(inb)-v(thb)-({vos}))/2m))",
        ]
    else:
        ta, ba, fa = thA or (232e3, 100e3, 2.2e6)
        tb, bb, fb = thB or (324e3, 30e3, 1e6)
        s += [
            f"RtA v33 tha {ta}", f"RbA tha 0 {ba}", f"RfA oa tha {fa}",
            f"RtB v33 thb {tb}", f"RbB thb 0 {bb}", f"RfB ob thb {fb}",
            # signal on IN-, threshold on IN+: sinks when signal > threshold
            f"BcA oa 0 I = v(oa)/30 * 0.5*(1 + tanh((v(ina)-v(tha)-({vos}))/2m))",
            f"BcB ob 0 I = v(ob)/30 * 0.5*(1 + tanh((v(inb)-v(thb)-({vos}))/2m))",
        ]
    s += [
        ".model DBAT D(IS=5.5e-8 N=1.0 RS=2.5 BV=30 IBV=1e-5 CJO=10p EG=0.69 XTI=2)",
        ".model DZ51 D(IS=1e-14 N=1 BV=5.1 IBV=5m RS=10)",
        ".tran 20u 1.5 0 50u UIC",
        ".control", "run",
        "meas tran pkavg AVG v(pk) from=1.3 to=1.5",
        "meas tran pkmin MIN v(pk) from=1.3 to=1.5",
        "meas tran pkmax MAX v(pk) from=1.3 to=1.5",
        "meas tran oamax MAX v(oa) from=1.3 to=1.5",
        "meas tran oamin MIN v(oa) from=1.3 to=1.5",
        "meas tran obmax MAX v(ob) from=1.3 to=1.5",
        "meas tran obmin MIN v(ob) from=1.3 to=1.5",
        ".endc", ".end",
    ]
    return "\n".join(s) + "\n"


def run(topo, wiring, **kw):
    out = subprocess.run(["ngspice", "-b", "/dev/stdin"], input=netlist(topo, wiring, **kw),
                         capture_output=True, text=True).stdout
    g = lambda k: float(re.search(rf"^{k}\s*=\s*([-\d.e+]+)", out, re.M).group(1))
    r = {k: g(k) for k in ("pkavg", "pkmin", "pkmax", "oamax", "oamin", "obmax", "obmin")}

    def bit(vmax, vmin):
        hi, lo = vmax > 2.0, vmin > 2.0
        if vmin > 2.0:
            level = 1
        elif vmax < 1.0:
            level = 0
        else:
            return None  # chattering
        return level if topo == "C" else 1 - level

    a, b = bit(r["oamax"], r["oamin"]), bit(r["obmax"], r["obmin"])
    cls = {(1, 1): "correct", (0, 0): "swapped", (0, 1): "noearth", (1, 0): "invalid"}.get((a, b), "chatter")
    r.update(A=a, B=b, cls=cls)
    return r


if __name__ == "__main__":
    topo = sys.argv[1] if len(sys.argv) > 1 else "C"
    for w in ("correct", "swapped", "noearth"):
        r = run(topo, w)
        print(f"{topo} {w:8s} pk {r['pkavg']:.3f} V  A={r['A']} B={r['B']}  -> {r['cls']}")
