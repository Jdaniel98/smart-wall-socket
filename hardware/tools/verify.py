#!/usr/bin/env python3
"""
Check the generated schematics against the design data.

1. kicad-cli exports each project's netlist; every pin must land on exactly
   the net the design says, and every intended no-connect must be unconnected.
2. Electrical rules that matter here, run on the design data:
   - no net with a single pin (a typo in a net name shows up here)
   - every power input is on a net with a power output or a PWR_FLAG
   - no two outputs on one net
   - only the four barrier parts (U5, PS1, K1, K2) touch both MAINS and SAFE nets
   - the ESP32 pads match the firmware GPIO map
Exit status is non-zero on any error.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evt1_design as d  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "evt1"))
MAINS_FIXED = {"L_BUS", "N_IN", "E_IN", "N_F", "N_R", "L_OUT1", "L_OUT2", "+3V3_HOT"}
BARRIER_PARTS = {"U5", "PS1", "K1", "K2"}

errors, warnings = [], []


def is_mains(net):
    return net in MAINS_FIXED or net.startswith("H_")


def parts(proj):
    for sh in proj.sheets:
        for b in sh.blocks:
            for p in b.parts:
                yield p


def expected(proj):
    """net -> set of (ref, pin), plus the set of (ref, pin) meant to be unconnected."""
    nets, nc = {}, set()
    for p in parts(proj):
        for pin in p.sym.pins:
            net = p.conn.get(pin.nums[0])
            for num in pin.nums:
                if net is None or net == "NC":
                    nc.add((p.ref, num))
                else:
                    nets.setdefault(net, set()).add((p.ref, num))
    return nets, nc


def export_netlist(proj):
    folder = os.path.join(OUT, proj.name.replace("sws-", ""))
    sch = os.path.join(folder, proj.name + ".kicad_sch")
    out = os.path.join(tempfile.mkdtemp(), proj.name + ".net")
    r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, sch],
                       capture_output=True, text=True)
    if r.returncode != 0:
        errors.append(f"{proj.name}: kicad-cli failed: {r.stderr.strip()}")
        return None
    return open(out).read()


def parse_netlist(txt):
    nets = {}
    comps = set(re.findall(r'\(comp \(ref "([^"]+)"\)', txt))
    for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', txt, re.S):
        name, body = m.group(1), m.group(2)
        nodes = set(re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body))
        nets[name] = nodes
    return comps, nets


def norm(name):
    # local labels come out as /Sheet Name/NET; global labels as NET
    return name.rsplit("/", 1)[-1] if name.startswith("/") else name


def check_netlist(proj):
    txt = export_netlist(proj)
    if txt is None:
        return
    comps, got = parse_netlist(txt)
    exp, nc = expected(proj)
    refs = {p.ref for p in parts(proj)}
    if not refs <= comps:
        errors.append(f"{proj.name}: components missing from netlist: {sorted(refs - comps)}")
    bad_refs = [c for c in comps if "?" in c]
    if bad_refs:
        errors.append(f"{proj.name}: unannotated references {bad_refs}")
    got_norm = {}
    for name, nodes in got.items():
        nodes = {n for n in nodes if not n[0].startswith("#")}
        if name.startswith("unconnected-") or name.startswith("Net-("):
            for n in nodes:
                if n not in nc:
                    errors.append(f"{proj.name}: {n} is unconnected in the drawing but on a net in the design")
            continue
        got_norm.setdefault(norm(name), set()).update(nodes)
    for net, nodes in exp.items():
        g = got_norm.get(net)
        if g is None:
            errors.append(f"{proj.name}: net {net} missing from netlist")
        elif g != nodes:
            errors.append(f"{proj.name}: net {net} differs: missing {sorted(nodes - g)}, extra {sorted(g - nodes)}")
    for net in got_norm:
        if net not in exp:
            errors.append(f"{proj.name}: unexpected net {net}: {sorted(got_norm[net])}")
    print(f"{proj.name}: netlist has {len(comps)} components, {len(got_norm)} named nets; "
          f"design has {len(exp)} nets")


def check_rules(proj):
    exp, _ = expected(proj)
    flags = {n for sh in proj.sheets for n in sh.flags}
    types = {}
    for p in parts(proj):
        for pin in p.sym.pins:
            net = p.conn.get(pin.nums[0])
            if net and net != "NC":
                types.setdefault(net, []).append((p.ref, pin.name, pin.etype))
    for net, nodes in exp.items():
        if len(nodes) < 2:
            errors.append(f"{proj.name}: net {net} has one pin only: {sorted(nodes)}")
    for net, lst in types.items():
        kinds = [t for _, _, t in lst]
        if "power_in" in kinds and "power_out" not in kinds and net not in flags:
            errors.append(f"{proj.name}: net {net} has power inputs but no source or PWR_FLAG")
        outs = [r for r, _, t in lst if t in ("output", "power_out")]
        if len(outs) > 1 and net not in ("GND",):
            errors.append(f"{proj.name}: net {net} has several outputs: {outs}")
    for p in parts(proj):
        nets = {n for n in p.conn.values() if n and n != "NC"}
        m = {n for n in nets if is_mains(n)}
        s = nets - m
        if m and s and p.ref not in BARRIER_PARTS:
            errors.append(f"{proj.name}: {p.ref} bridges MAINS {sorted(m)} and SAFE {sorted(s)}")
        if p.ref in BARRIER_PARTS and not (m and s):
            warnings.append(f"{proj.name}: barrier part {p.ref} does not bridge as expected")


def check_gpio():
    esp = next(p for p in parts(d.FRONT) if p.ref == "U102")
    for pad, gpio in d.ESP_PAD_TO_GPIO.items():
        net = esp.conn.get(pad)
        if d.GPIO_MAP.get(net) != gpio:
            errors.append(f"GPIO map: pad {pad} is GPIO{gpio} on net {net}, map says {d.GPIO_MAP.get(net)}")


def check_b2b():
    rear = next(p for p in parts(d.REAR) if p.ref == "J4")
    front = next(p for p in parts(d.FRONT) if p.ref == "J101")
    if rear.conn != front.conn:
        errors.append("B2B header pin maps differ between boards")
    for pin, net in rear.conn.items():
        if is_mains(net):
            errors.append(f"B2B pin {pin} carries a mains net {net}")


def main():
    for proj in d.PROJECTS:
        check_rules(proj)
        check_netlist(proj)
    check_gpio()
    check_b2b()
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
