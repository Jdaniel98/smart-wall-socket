#!/usr/bin/env python3
"""
R1 surge study: IEC 61000-4-5 combination wave (2 ohm) applied L-N to the
rear board's electronics feed, sweeping R2, the drain TVS and the MOV.

Circuit (hot side, L_BUS = 0 V reference):
  N_F --RV1-- L_BUS                       (MOV after F1; F1 does not open in 50 us)
  N_F --R2-- KP_A --D1(M7)--> KP_D --D7(TVS)-- L_BUS
                              KP_D --(KP3310 drain, off: 50 pF)-- L_BUS
The LD03 branch (12 R + module input) is left out, which is conservative:
it would take some surge current away from RV1.

Models (stated assumptions, not vendor SPICE models):
  MOV 561K: I = 1 mA * (V/560)^20.2 (fits 560 V @ 1 mA and 925 V @ 25 A) + 0.15 ohm bulk.
  MOV 471K: I = 1 mA * (V/470)^20.6 (470 V @ 1 mA, 775 V @ 25 A) + 0.15 ohm bulk.
  TVS: breakdown at VBR max with the dynamic resistance implied by its datasheet
       clamp (Vc at Ipp, 10/1000 us).
  D1: two M7 in series (2000 V) so the negative-surge reverse voltage can be read directly.
"""
import itertools, re, subprocess, sys, json

U_PER_KV = 1000.0 / 0.93124  # charge voltage per kV of open-circuit peak (cwg_check.cir: 931.2 V per 1000 V)

MOVS = {"561K": (560, 20.2), "471K": (470, 20.6)}
TVS = {  # name: (VBR max, dynamic R from datasheet clamp)
    "SMCJ400A": (494, (648 - 494) / 2.3),
    "3.0SMCJ400A": (494, (648 - 494) / 4.6),
    "5.0SMDJ400A": (494, (648 - 494) / 7.7),
}


def run(kv, pol, r2, tvs, mov):
    vbr, rd = TVS[tvs]
    v1, a = MOVS[mov]
    u = pol * kv * U_PER_KV
    net = f"""R1 surge study
* surge
Cc c 0 7.76u IC={u}
Rs1 c 0 14.8
Rm c m 1.05
Lr m g 9.74u
Rs2 g 0 23.3
Rsrc g nf 1m
* MOV between N_F (nf) and L_BUS (0), with bulk resistance
Rb nf mv 0.15
Vimov mv mv2 0
Bmov mv2 0 I = 1e-3*sgn(v(mv2))*pow(abs(v(mv2))/{v1}, {a})
Cmov nf 0 400p
R2 nf ka {r2}
D1 ka kd DM7
Vitvs kd kt 0
Dtvs 0 kt DTVS
Cdrain kd 0 50p
Rleak kd 0 10Meg
.model DM7 D(IS=1n N=1.8 RS=0.1 BV=2000 IBV=5u CJO=8p TT=2u)
.model DTVS D(IS=1e-12 N=1 RS={rd:.3f} BV={vbr} IBV=1m CJO=1n)
.tran 0.02u 120u UIC
.control
run
let vmov = abs(v(nf))
let vd1r = v(kd)-v(ka)
let itv = i(Vitvs)
let imv = abs(i(Vimov))
let ptvs = i(Vitvs)*v(kd)
meas tran vmov_pk MAX vmov
meas tran vdrain_pk MAX v(kd)
meas tran vd1rev_pk MAX vd1r
meas tran itvs_pk MAX itv
meas tran itvs_min MIN itv
meas tran imov_pk MAX imv
meas tran etvs INTEG ptvs
let pr2 = (v(nf)-v(ka))^2/{r2}
meas tran er2 INTEG pr2
.endc
.end
"""
    out = subprocess.run(["ngspice", "-b", "/dev/stdin"], input=net, capture_output=True, text=True).stdout
    vals = {}
    for k in ("vmov_pk", "vdrain_pk", "vd1rev_pk", "itvs_pk", "itvs_min", "imov_pk", "etvs", "er2"):
        m = re.search(rf"^{k}\s*=\s*([-\d.e+]+)", out, re.M)
        vals[k] = float(m.group(1)) if m else float("nan")
    return vals


if __name__ == "__main__":
    rows = []
    for kv, pol, r2, tvs, mov in itertools.product((1, 2, 4), (1, -1), (47, 100, 150, 220),
                                                   TVS, MOVS):
        v = run(kv, pol, r2, tvs, mov)
        rows.append(dict(kv=kv, pol="+" if pol > 0 else "-", r2=r2, tvs=tvs, mov=mov, **v))
    json.dump(rows, open("surge_results.json", "w"), indent=1)
    print(len(rows), "runs")
