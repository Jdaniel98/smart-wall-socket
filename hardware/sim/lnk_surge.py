#!/usr/bin/env python3
"""
Alternative to the KP3310: LNK3204 half-wave buck. Surge check of its input stage.
N_F --RF (fusible)-- D (2 x M7) -- C_bulk (+ L_pi + C_bulk2) -- L_BUS, MOV 561K across N_F/L_BUS.
The surge arrives at the crest of 253 V mains (bulk pre-charged to 358 V), the worst case.
Pass: bulk (= LNK drain) peak well below the 725 V MOSFET rating.
"""
import itertools, re, subprocess

def run(kv, rf, cb):
    u = kv * 1000.0 / 0.93124
    net = f"""LNK surge
* (title)
Cc c 0 7.76u IC={u}
Rs1 c 0 14.8
Rm c m 1.05
Lr m g 9.74u
Rs2 g 0 23.3
Vmains g nf 0
Rb nf mv 0.15
Bmov mv 0 I = 1e-3*sgn(v(mv))*pow(abs(v(mv))/560, 20.2)
RF nf a {rf}
D1 a b DM7
D2 b c1 DM7
C1 c1 0 {cb}u IC=358
Lpi c1 c2 1m
C2 c2 0 {cb}u IC=358
Rload c2 0 40k
.model DM7 D(IS=1n N=1.8 RS=0.1 BV=2000 IBV=5u CJO=8p TT=2u)
.tran 0.05u 300u UIC
.control
run
meas tran vb1 MAX v(c1)
meas tran vb2 MAX v(c2)
let p = (v(nf)-v(a))^2/{rf}
meas tran erf INTEG p
.endc
.end
"""
    out = subprocess.run(["ngspice", "-b", "/dev/stdin"], input=net, capture_output=True, text=True).stdout
    g = lambda k: float(re.search(rf"^{k}\s*=\s*([-\d.e+]+)", out, re.M).group(1))
    return g("vb1"), g("vb2"), g("erf")

if __name__ == "__main__":
    print("kV  RF(ohm)  C(uF)  bulk1 peak  bulk2 peak  RF energy")
    for kv, rf, cb in itertools.product((2, 4), (10, 22, 47), (2.2, 4.7)):
        a, b, e = run(kv, rf, cb)
        print(f"{kv:>2}  {rf:>6}  {cb:>5}  {a:9.0f} V  {b:9.0f} V  {e*1000:7.0f} mJ")
