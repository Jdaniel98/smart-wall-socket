#!/usr/bin/env python3
"""
Polarity and earth check, proposed scheme F (pulse-width ratio).

Circuit (hot side, L_BUS = node 0):
  Arm A: E -> 2 x 2M (VR37) -> H_POL_S -> 47k -> L_BUS        (R17 20k -> 47k)
  Arm B: E -> 2 x 2M (VR37) -> 47k -> N_F                     (R20 20k -> 47k, keeps arms equal)
  D2 BZT52C5V1 clamp on H_POL_S (unchanged)
  D3 low-leakage silicon diode (BAS116 class) in series, H_POL_S -> H_POL_X; R21 470k H_POL_X -> L_BUS
  C12 removed. R33/R34 removed (no hysteresis on a high-impedance node).
  R31/R32 10k from H_POL_X to the comparator + inputs; thresholds on - inputs from
  one ladder 182k / 100k / 49.9k: TH_A = 1.490 V, TH_B = 0.496 V.
  Outputs (open drain, 10k pull-up) are high while the half-wave is above threshold:
  each bit is a 50 Hz pulse train through the isolator.

Firmware: time the high pulses over 10 mains cycles, convert duty d to the peak at
H_POL_S with   V = (TH / g + Vf) / cos(pi d)    (g = 470k divider gain, Vf nominal),
then divide by the BL0939's measured mains peak:   k = V / (Vrms * sqrt 2).
Ratio to the reference k0:  > 0.68 earthed and correct,  0.33-0.68 no earth,  < 0.33 swapped.
k0 is either the design value or measured per unit at end-of-line test (correct wiring).
"""
import json, math, re, subprocess, sys

F = 50.0
TH_A, TH_B = 3.3 * 149.9 / 331.9, 3.3 * 49.9 / 331.9
RS_NOM, R21_NOM = 47e3, 470e3
G_NOM = R21_NOM / (R21_NOM + RS_NOM * 4e6 / (4e6 + RS_NOM))
VF_NOM = 0.50


def netlist(wiring, vm=230.0, ven=0.0, cf=1.0, karm=1.0, kA=1.0, kB=1.0, rs=47e3, rsb=47e3,
            r21=470e3, v33=3.3, vosA=0.0, vosB=0.0, tj=25.0, ycap=None, smooth="2m", ladder=1.0, soft_zener=False):
    vpk = vm * 2 ** 0.5 * cf
    vepk = ven * 2 ** 0.5
    s = [f"polarity F {wiring}", "* (title)", f".options temp={tj} reltol=1e-4"]
    if wiring == "correct":
        s += [f"Vn nf 0 SIN(0 {-vpk} {F})", f"Ve e 0 SIN(0 {-vpk + vepk} {F})"]
    elif wiring == "swapped":
        s += [f"Vn nf 0 SIN(0 {vpk} {F})", f"Ve e 0 SIN(0 {vepk} {F})"]
    else:
        s += [f"Vn nf 0 SIN(0 {-vpk} {F})", "Rleak_e e 0 1e12"]
        if ycap:
            side, c = ycap
            s.append(f"Cy e {'nf' if side == 'N' else '0'} {c}")
    # ladder tolerance: ladder>1 raises both thresholds by that factor (ratio error)
    rt = 182e3 / ladder
    s += [
        f"RarmA e pols {4e6 * karm * kA}", f"R17 pols 0 {rs}",
        f"RarmB e pb2 {4e6 * karm * kB}", f"R20 pb2 nf {rsb}",
        "D2 0 pols DZ51", "D3 pols x DLL", f"R21 x 0 {r21}",
        f"V33 v33 0 {v33}", "R25 oa v33 10k", "R26 ob v33 10k",
        "R31 x ina 10k", "R32 x inb 10k",
        f"R22 v33 tha {rt}", "R23 tha thb 100k", "R24 thb 0 49.9k",
        f"BcA oa 0 I = v(oa)/30 * 0.5*(1 - tanh((v(ina)-v(tha)-({vosA}))/{smooth}))",
        f"BcB ob 0 I = v(ob)/30 * 0.5*(1 - tanh((v(inb)-v(thb)-({vosB}))/{smooth}))",
        "Bha ha 0 V = u(v(oa)-1.65)", "Bhb hb 0 V = u(v(ob)-1.65)",
        ".model DLL D(IS=1.3e-11 N=1.6 RS=10 BV=85 IBV=1n CJO=2p EG=1.11 XTI=3)",
        # soft knee: about 5 uA at 4 V reverse (typical of 5.1 V zeners); hard knee otherwise
        ".model DZ51 D(IS=1e-14 N=1 BV=5.1 IBV=5m RS=10 NBV=6.15)" if soft_zener else
        ".model DZ51 D(IS=1e-14 N=1 BV=5.1 IBV=5m RS=10)",
        ".tran 10u 0.3 0 20u",
        ".control", "run",
        "meas tran da AVG v(ha) from=0.1 to=0.3",
        "meas tran db AVG v(hb) from=0.1 to=0.3",
        "meas tran xmin MIN v(x) from=0.1 to=0.3",
        "meas tran smax MAX v(pols) from=0.1 to=0.3",
        ".endc", ".end",
    ]
    return "\n".join(s) + "\n"


def sim(wiring, **kw):
    for smooth in ("2m", "10m"):
        out = subprocess.run(["ngspice", "-b", "/dev/stdin"], input=netlist(wiring, smooth=smooth, **kw),
                             capture_output=True, text=True)
        txt = out.stdout + out.stderr
        if "aborted" in txt or "too small" in txt:
            continue
        g = lambda k: float(re.search(rf"^{k}\s*=\s*([-\d.e+]+)", out.stdout, re.M).group(1))
        return {k: g(k) for k in ("da", "db", "xmin", "smax")}
    raise RuntimeError(f"simulation failed: {wiring} {kw}")


def estimate(da, db, vrms_meas):
    """Firmware estimate of k from the two duties (uses nominal constants only)."""
    if da > 0.02:
        v = (TH_A / G_NOM + VF_NOM) / math.cos(math.pi * min(da, 0.499))
    elif db > 0.02:
        v = (TH_B / G_NOM + VF_NOM) / math.cos(math.pi * min(db, 0.499))
    else:
        return 0.0
    return v / (vrms_meas * 2 ** 0.5)


def classify(ratio):
    if ratio > 0.68:
        return "correct"
    if ratio > 0.33:
        return "noearth"
    return "swapped"


if __name__ == "__main__":
    for w in ("correct", "swapped", "noearth"):
        r = sim(w)
        print(w, r)
