#!/usr/bin/env python3
"""
R1 hold-up study: can the KP3310 keep VDD up through R2 at low mains?

The KP3310 datasheet says it draws energy only in the low-voltage part of each
half cycle (power MOSFET on below ~50 V AC) and limits the output at 100-160 mA,
but it gives neither the charge-path current limit nor exactly where the AC
sync is sensed. So the charge path is modelled behaviourally and those two
unknowns are swept:
  I_chg = on * min(Ilim, max(0, (V_drain - VDD) / Ron)),  on = (V_line < Vsync) and (VDD < 7.8 V)
Output: the average current the charge path can deliver into VDD held at 6 V
(a fixed source stands in for the 220 uF store). The hot side needs 8 mA
typical and 15 mA worst case, so delivered current must exceed 15 mA.
"""
import itertools, re, subprocess, json


def run(vrms, r2, ilim, vsync, ron=5.0):
    net = f"""R1 holdup
* (ngspice reading stdin skips the first line; this comment becomes the title)
Vline nf 0 SIN(0 {vrms*1.41421356} 50)
R2 nf ka {r2}
D1a ka kx DM7
D1b kx kd DM7
Cdrain kd 0 50p
Rbl kd 0 1Meg
Bchg kd vdd I = 0.5*(1+tanh(({vsync}-v(nf))/0.5))*{ilim}*tanh(max(v(kd)-v(vdd),0)/({ron}*{ilim}))
Vvdd vdd 0 6
.model DM7 D(IS=1n N=1.8 RS=0.1 BV=2000 IBV=5u CJO=8p TT=2u)
.options reltol=1e-3 method=gear
.tran 5u 200m 0 5u
.control
run
meas tran iavg AVG i(Vvdd) from=100m to=200m
.endc
.end
"""
    out = subprocess.run(["ngspice", "-b", "/dev/stdin"], input=net, capture_output=True, text=True).stdout
    g = lambda k: float(re.search(rf"^{k}\s*=\s*([-\d.e+]+)", out, re.M).group(1))
    return -g("iavg") * 1000.0   # mA into VDD


if __name__ == "__main__":
    rows = []
    for vrms, r2, ilim, vsync in itertools.product((160, 185, 207, 230), (0, 47, 100, 150, 220),
                                                    (0.1, 0.3, 1.0, 3.0), (30, 50)):
        rows.append(dict(vrms=vrms, r2=r2, ilim=ilim, vsync=vsync, ma=run(vrms, max(r2, 0.01), ilim, vsync)))
    json.dump(rows, open("holdup_results.json", "w"), indent=1)
    print(len(rows), "runs")
