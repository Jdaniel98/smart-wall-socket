#!/usr/bin/env python3
"""
Safe-side 5 V rail: does it hold up when a relay pulls in during a Wi-Fi transmit
burst, with the light lines on?

LD03-23B05R2 model: regulated current source, PI loop (crossover fc), output clamped
at the over-current limit 0.66 A (>=110 % of 600 mA). Mornsun gives no transient
figures for this part, so fc is swept. Load regulation 1 % at full load sets Kp.
Rear board: C18 1u, C19 150u (ESR swept), C22 10u, relays K1/K2 (62.5 ohm, L swept),
XC6206 + ISO7761 side 2 (5 mA).
J4: 2 + 2 pins, 50 mohm round trip. Front board: C101 22u, C102 10u, TLV62569 3.3 V
buck as a constant-power load (eta 0.88), light lines on LED_5V.

ESP32-C6-MINI-1 peak currents (Espressif datasheet, 3.3 V): 802.11b 20.5 dBm 382 mA,
RX 78-82 mA. SK6812MINI-E: 12 mA per colour, 4 LEDs -> 148 mA at full white.

Pass: relay coil voltage stays above must-operate with margin (3.5 V at 23 C, 4.35 V
at 85 C coil), front +5V stays above 3.6 V (buck dropout and SK6812 minimum 3.7 V).
"""
import itertools, json, math, re, subprocess

P_RX = 3.3 * 0.090 / 0.88   # W at the buck input: RX + touch/NFC/misc
P_TX = 3.3 * 0.390 / 0.88   # W: 802.11b 1 Mbps at 20.5 dBm


def netlist(fc=2e3, esr=0.2, lcoil=0.1, led=0.148, both=False, hold_d=0.6, tx_ms=12.0):
    c_tot = 193e-6
    wc = 2 * math.pi * fc
    kp = wc * c_tot
    ki = kp * wc / 5
    i_hold = hold_d * (hold_d * 5.0 - (1 - hold_d) * 0.3) / 62.5   # average supply current of a held coil
    t0 = 5e-3
    s = ["5V rail", "* (title)",
         # LD03: PI current command, opto pole at 5 fc, clamp 0..0.66 A
         "Verr err 0 0",
         "Bp p 0 V = 5.0 - v(o5)",
         f"Bint 0 i1 I = {ki} * v(p) * (1 - u(v(i1)-0.66)*u(v(p))) * (1 - u(-v(i1))*u(-v(p)))",
         "Ci i1 0 1",
         f"Bcmd c 0 V = {kp}*v(p) + v(i1)",
         f"Rpl c cf 1", f"Cpl cf 0 {1 / (5 * wc)}",
         "Bld 0 o5 I = min(max(v(cf), 0), 0.66)",
         "Bmon im 0 V = min(max(v(cf), 0), 0.66)",
        "Blim lim 0 V = u(v(im) - 0.655)",
         # rear board caps
         "C18 o5 0 1u",
         "C19 o5 c19 150u", f"Resr c19 0 {esr}",
         "C22 o5 0 10u",
         "Iiso o5 0 5m",
         # relay 1 already held (PWM average), relay 2 pulls in at t0 (and relay 1 too if both)
         f"Ihold o5 0 {0 if both else i_hold}",
         f"S2 o5 k2 g2 0 SW", f"Vg2 g2 0 PULSE(0 1 {t0} 1u 1u 0.05 1)",
         f"Lk2 k2 k2r {lcoil}", "Rk2 k2r 0 62.5",
         f"Dk2 0 k2 DFW",
    ]
    if both:
        s += ["S1 o5 k1 g2 0 SW", f"Lk1 k1 k1r {lcoil}", "Rk1 k1r 0 62.5", "Dk1 0 k1 DFW"]
    s += [
        # J4 and front board
        "Rj o5 f5 0.05",
        "C101 f5 0 22u", "C102 f5 0 10u",
        # buck: constant power, TX burst starts with the pull-in
        f"Bbuck f5 0 I = ({P_RX} + {P_TX - P_RX}*v(tx)) / max(v(f5), 2.5)",
        f"Vtx tx 0 PULSE(0 1 {t0} 2u 2u {tx_ms * 1e-3} 1)",
        # light lines: SK6812 PWM at 1.2 kHz, full white = constant
        f"Iled f5 0 {led}",
        ".model SW SW(VT=0.5 VH=0.1 RON=0.05 ROFF=1e9)",
        ".model DFW D(IS=1e-6 N=1.1 RS=0.1)",
        f".ic v(o5)=4.96 v(f5)=4.95 v(c19)=4.96 v(i1)={0.005 + (0 if both else i_hold) + P_RX / 4.95 + led:.4f} v(cf)={0.005 + (0 if both else i_hold) + P_RX / 4.95 + led:.4f}",
        ".tran 2u 40m 0 5u UIC",
        ".control", "run",
        "meas tran v5pre FIND v(o5) AT=4.9m",
        "meas tran v5min MIN v(o5) from=5m to=25m",
        "meas tran f5min MIN v(f5) from=5m to=25m",
        "meas tran ipk MAX v(im) from=5m to=40m",
        "meas tran tlim INTEG v(lim) from=5m to=40m",
        ".endc", ".end"]
    return "\n".join(s) + "\n", i_hold


def run(**kw):
    net, i_hold = netlist(**kw)
    p = subprocess.run(["ngspice", "-b", "/dev/stdin"], input=net, capture_output=True, text=True)
    g = lambda k: float(re.search(rf"^{k}\s*=\s*([-\d.e+]+)", p.stdout, re.M).group(1))
    return {k: g(k) for k in ("v5pre", "v5min", "f5min", "ipk", "tlim")} | {"i_hold": i_hold}


if __name__ == "__main__":
    rows = []
    print("fc kHz  ESR  Lcoil  LEDs mA  pull-in  | 5V before  5V min (coil)  front min  LD03 peak  time at limit")
    for fc, esr, lc, led, both in itertools.product((1e3, 3e3), (0.1, 0.3), (0.05, 0.2), (0.037, 0.148), (False, True)):
        r = run(fc=fc, esr=esr, lcoil=lc, led=led, both=both)
        rows.append(dict(fc=fc, esr=esr, lcoil=lc, led=led, both=both, **r))
        print(f"{fc/1e3:5.0f}  {esr:4.1f}  {lc:5.2f}  {led*1e3:6.0f}   {'both' if both else 'one '}   |"
              f"  {r['v5pre']:6.3f}     {r['v5min']:6.3f}       {r['f5min']:6.3f}    {r['ipk']*1e3:5.0f} mA   {r['tlim']*1e3:5.2f} ms")
    json.dump(rows, open("power5v_results.json", "w"), indent=1)
