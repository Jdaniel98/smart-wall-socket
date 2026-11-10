# Generic-component visual model of the EVT1 concept. Placement is illustrative, NOT the PCB layout.
import bpy, bmesh, pickle, sys, math, random, json
from mathutils import Vector, Matrix
VIEW = sys.argv[-2]; SAMPLES = int(sys.argv[-1])
mesh = pickle.load(open("/tmp/render/mesh.pkl", "rb"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; S = 0.001; random.seed(7)
EXPL = VIEW == "exploded"
DZ = {"rear": 0, "carrier": 12, "frame": 30, "screw": 44, "front": 50, "face": 74} if EXPL else {k: 0 for k in ("rear", "carrier", "frame", "screw", "front", "face")}

def mat(name, col, rough=0.5, metal=0.0, alpha=1.0, emit=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Alpha"].default_value = alpha
    b.inputs["Coat Weight"].default_value = coat
    if emit: b.inputs["Emission Color"].default_value = (*col, 1); b.inputs["Emission Strength"].default_value = emit
    return m
M = dict(
    pcb=mat("pcb", (0.015, 0.20, 0.05), 0.35, coat=0.25), trace=mat("trace", (0.025, 0.27, 0.08), 0.35, coat=0.25),
    silk=mat("silk", (0.9, 0.9, 0.9), 0.6), tin=mat("tin", (0.8, 0.8, 0.8), 0.25, 1.0), gold=mat("gold", (0.9, 0.65, 0.25), 0.3, 1.0),
    brass=mat("brass", (0.85, 0.6, 0.2), 0.28, 1.0), copper=mat("copper", (0.85, 0.42, 0.22), 0.3, 1.0),
    steel=mat("steel", (0.72, 0.72, 0.74), 0.3, 1.0), alu=mat("alu", (0.85, 0.85, 0.86), 0.35, 1.0),
    ic=mat("ic", (0.025, 0.025, 0.028), 0.45), res=mat("res", (0.03, 0.03, 0.035), 0.5), cap=mat("cap", (0.45, 0.32, 0.2), 0.5),
    blue=mat("blue", (0.02, 0.09, 0.42), 0.35, coat=0.3), mov=mat("mov", (0.03, 0.2, 0.55), 0.5), black=mat("black", (0.02, 0.02, 0.022), 0.45),
    ceramic=mat("ceramic", (0.85, 0.83, 0.78), 0.6), sleeve=mat("sleeve", (0.04, 0.05, 0.12), 0.4), ferrite=mat("ferrite", (0.05, 0.05, 0.055), 0.7),
    tgreen=mat("tgreen", (0.04, 0.32, 0.12), 0.4), beige=mat("beige", (0.82, 0.78, 0.66), 0.5), label=mat("label", (0.88, 0.88, 0.86), 0.6),
    smoke=mat("smoke", (0.04, 0.04, 0.045), 0.15, alpha=0.38), carrier=mat("carrier", (0.05, 0.05, 0.055), 0.2, alpha=0.45),
    face=mat("face", (0.93, 0.93, 0.91), 0.3, alpha=0.5 if EXPL else 1.0), white=mat("white", (0.9, 0.9, 0.88), 0.4),
    led=mat("led", (0.95, 0.95, 0.9), 0.3), light=mat("light", (0.3, 0.7, 1.0), 0.3, emit=5.0), slot=mat("slot", (0.0, 0.0, 0.0), 0.9),
)
def link(o, parent, m):
    sc.collection.objects.link(o); o.data.materials.append(M[m])
    if parent is not None: o.parent = parent
    return o
def B(p, sx, sy, sz, x, y, z0, m, bev=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector(((v.co.x * sx + x) * S, (v.co.y * sy + y) * S, ((v.co.z + 0.5) * sz + z0) * S))
    me = bpy.data.meshes.new("b"); bm.to_mesh(me); bm.free(); o = link(bpy.data.objects.new("b", me), p, m)
    if bev: md = o.modifiers.new("bv", "BEVEL"); md.width = bev * S; md.segments = 3
    return o
def C(p, r, h, x, y, z0, m, axis="Z", seg=40):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    for v in bm.verts:
        cx, cy, cz = v.co.x, v.co.y, v.co.z + h / 2
        if axis == "X": cx, cy, cz = cz - h / 2, cy, cx + r
        if axis == "Y": cx, cy, cz = cx, cz - h / 2, cy + r
        v.co = Vector(((cx + x) * S, (cy + y) * S, (cz + z0) * S))
    for f in bm.faces: f.smooth = len(f.verts) == 4
    me = bpy.data.meshes.new("c"); bm.to_mesh(me); bm.free(); return link(bpy.data.objects.new("c", me), p, m)

PADS = []   # filled per component: (dx, dy, w, h, hole)
def pad(p, dx, dy, w, h, hole=0.0, m="tin"):
    PADS.append((dx, dy, w, h, hole))
    if hole: C(p, w / 2, 0.06, dx, dy, 0, m)
    else: B(p, w, h, 0.05, dx, dy, 0, m)
# ---- generic components (origin at the footprint centre on the board surface) ----
def chip(p, L, W, H, body):
    B(p, L * 0.62, W, H, 0, 0, 0.02, body)
    for s in (-1, 1):
        B(p, L * 0.2, W + 0.04, H + 0.04, s * L * 0.4, 0, 0, "tin", 0.03); pad(p, s * L * 0.45, 0, L * 0.34, W + 0.3)
def r0603(p): chip(p, 1.6, 0.8, 0.45, "res")
def c0603(p): chip(p, 1.6, 0.8, 0.8, "cap")
def c0805(p): chip(p, 2.0, 1.25, 1.1, "cap")
def r1206(p): chip(p, 3.2, 1.6, 0.55, "res")
def shunt(p): chip(p, 6.3, 3.2, 0.7, "alu")
def soic(p, n=8, pitch=1.27, bl=4.9, bw=3.9, h=1.5, span=6.0):
    B(p, bl, bw, h, 0, 0, 0.1, "ic", 0.12); C(p, 0.25, 0.02, -bl / 2 + 0.7, -bw / 2 + 0.7, h + 0.09, "res", seg=16)
    k = n // 2
    for i in range(k):
        x = (i - (k - 1) / 2) * pitch
        for s in (-1, 1):
            B(p, pitch * 0.35, (span - bw) / 2 + 0.2, 0.2, x, s * (bw / 2 + (span - bw) / 4), 0.05, "tin"); pad(p, x, s * (span / 2 - 0.4), pitch * 0.5, 1.5)
def soic8(p): soic(p)
def ssop20(p): soic(p, 20, 0.65, 7.2, 5.3, 1.7, 7.8)
def soic16w(p): soic(p, 16, 1.27, 10.3, 7.5, 2.3, 10.3)
def sot23(p):
    B(p, 2.9, 1.3, 1.0, 0, 0, 0.1, "ic", 0.1)
    for x, s in ((-0.95, -1), (0.95, -1), (0, 1)):
        B(p, 0.4, 0.6, 0.15, x, s * 0.95, 0.03, "tin"); pad(p, x, s * 1.1, 0.6, 0.9)
def sma(p):
    B(p, 4.3, 2.6, 2.2, 0, 0, 0.1, "ic", 0.15); B(p, 0.5, 2.4, 0.03, -1.4, 0, 2.3, "label")
    for s in (-1, 1): B(p, 0.9, 1.5, 1.2, s * 2.3, 0, 0, "tin"); pad(p, s * 2.2, 0, 1.8, 2.0)
def ecap_tht(p):
    C(p, 4.0, 12.0, 0, 0, 0.3, "sleeve"); C(p, 3.6, 0.1, 0, 0, 12.3, "alu"); B(p, 6.5, 0.25, 0.05, 0, 0, 12.4, "sleeve")
    for s in (-1, 1): pad(p, s * 1.75, 0, 1.8, 0, 0.9)
def ecap_smd(p):
    B(p, 6.6, 6.6, 1.2, 0, 0, 0, "black", 0.3); C(p, 3.15, 4.6, 0, 0, 1.2, "alu"); B(p, 2.2, 6.1, 0.03, -1.9, 0, 5.8, "black")
    for s in (-1, 1): pad(p, s * 2.7, 0, 3.0, 1.6)
def ind_radial(p):
    C(p, 4.0, 1.6, 0, 0, 0.3, "ferrite"); C(p, 3.1, 6.6, 0, 0, 1.9, "copper"); C(p, 4.0, 1.6, 0, 0, 8.5, "ferrite")
    for s in (-1, 1): pad(p, s * 2.5, 0, 1.8, 0, 0.9)
def ind_smd(p):
    B(p, 4.0, 4.0, 1.8, 0, 0, 0.05, "ferrite", 0.25)
    for s in (-1, 1): pad(p, s * 1.6, 0, 1.4, 3.6)
def movd(p):
    C(p, 5.5, 4.2, 0, 0, 1.5, "mov", axis="X")
    for s in (-1, 1): C(p, 0.4, 3, 0, s * 3.75, 0, "tin", seg=12); pad(p, 0, s * 3.75, 2.0, 0, 1.0)
def axial(p, m="ceramic", L=10, r=2.3):
    C(p, r, L, 0, 0, 0.6, m, axis="X")
    for s in (-1, 1): C(p, 0.4, 2.2, s * (L / 2 + 1.1), 0, r + 0.2, "tin", axis="X", seg=12); pad(p, s * (L / 2 + 2.0), 0, 2.0, 0, 1.0)
def tco(p): axial(p, "steel", 9, 1.6)
def fuse(p):
    B(p, 9.0, 5.2, 5.2, 0, 0, 0.1, "ceramic", 0.3)
    for s in (-1, 1): B(p, 3.3, 5.35, 5.35, s * 6.05, 0, 0.03, "tin", 0.25); pad(p, s * 6.875, 0, 3.75, 5.6)
def relay(p):
    B(p, 29.0, 12.7, 15.7, 0, 0, 0.3, "blue", 0.6); B(p, 20, 8.5, 0.04, -1, 0, 15.98, "label"); B(p, 14, 1.0, 0.03, -3, 2.0, 16.02, "res"); B(p, 9, 0.7, 0.03, -5.5, -1.5, 16.02, "res")
    for dx, dy, d in ((-12.2, 3.75, 2.2), (-12.2, -3.75, 2.2), (7.8, 3.75, 2.8), (7.8, -3.75, 2.8), (12.8, 3.75, 2.8), (12.8, -3.75, 2.8)): pad(p, dx, dy, d, 0, d * 0.55)
def ld03(p):
    B(p, 25.4, 25.4, 17.6, 0, 0, 0.3, "black", 0.9); B(p, 19, 12, 0.04, 0, 1, 17.88, "label"); B(p, 13, 1.2, 0.03, -1.5, 4, 17.92, "res"); B(p, 16, 0.7, 0.03, 0, 0.5, 17.92, "res"); B(p, 10, 0.7, 0.03, -3, -2, 17.92, "res")
    for dx, dy in ((-10.16, 7.62), (-10.16, 2.54), (10.16, 7.62), (10.16, -2.54)): pad(p, dx, dy, 2.2, 0, 1.2)
def esp32(p):
    B(p, 13.2, 16.6, 0.8, 0, 0, 0.05, "black"); B(p, 11.6, 11.2, 1.55, 0, 2.2, 0.85, "steel", 0.3)
    for i in range(5): B(p, 9.5 - i * 0.2, 0.35, 0.03, 0, -4.6 - i * 0.8, 0.85, "gold")
    for i in range(9):
        for s in (-1, 1): pad(p, s * 6.3, -6.4 + i * 1.5, 1.2, 0.8, m="gold")
def terminal(p):
    B(p, 33, 11, 11, 0, 0, 0, "tgreen", 0.4)
    for sx in (-11, 0, 11):
        C(p, 2.3, 0.4, sx, 0, 11.0, "steel"); B(p, 3.4, 0.6, 0.15, sx, 0, 11.35, "black"); C(p, 2.4, 0.3, sx, 5.36, 2.2, "slot", axis="Y")
        pad(p, sx, 0, 3.4, 0, 1.6)
def fpc(p):
    B(p, 18, 4, 2.0, 0, 0, 0.05, "beige", 0.15); B(p, 16, 1.4, 0.6, 0, 1.1, 2.05, "black", 0.1)
    for i in range(14): pad(p, -6.5 + i, -2.4, 0.55, 1.3)
def led(p): B(p, 3.2, 2.8, 1.78, 0, 0, -1.6, "led", 0.2)
BUILD = dict(r0603=r0603, c0603=c0603, c0805=c0805, r1206=r1206, shunt=shunt, soic8=soic8, ssop20=ssop20, soic16w=soic16w, sot23=sot23, sma=sma,
             ecap_tht=ecap_tht, ecap_smd=ecap_smd, ind_radial=ind_radial, ind_smd=ind_smd, mov=movd, axial=axial, tco=tco, fuse=fuse, relay=relay,
             ld03=ld03, esp32=esp32, terminal=terminal, fpc=fpc, led=led)
RECORD = []; OCC = []
def place(kind, x, y, rot=0, group="rear", zface=-16.0, flip=False, rec=False, occ=0.0):
    global PADS
    PADS = []; e = bpy.data.objects.new(kind, None); sc.collection.objects.link(e)
    BUILD[kind](e)
    e.location = (x * S, y * S, (zface + DZ[group]) * S); e.rotation_euler = (math.pi if flip else 0, 0, math.radians(rot))
    if occ: OCC.append((x, y, occ, zface, flip))
    if rec: RECORD.append(dict(kind=kind, x=x, y=y, rot=rot, pads=PADS))
def static(key, m, group, bev=0.0):
    V, T, c = mesh[key]; dz = DZ[group]
    me = bpy.data.meshes.new(key); me.from_pydata([(x * S, y * S, (z + dz) * S) for x, y, z in V], [], [tuple(int(i) for i in t) for t in T]); me.update()
    return link(bpy.data.objects.new(key, me), None, m)
def G(group):  # empty at the group's exploded height, for loose geometry
    e = bpy.data.objects.new(group, None); sc.collection.objects.link(e); e.location = (0, 0, DZ[group] * S); return e

# ================= rear board, top face (z = -16) =================
static("rear_board", "pcb", "rear"); R = G("rear"); ZT = -16.0
T = lambda *a, **k: place(*a, group="rear", zface=ZT, rec=True, **k)
T("ld03", 0, 21, occ=18); T("relay", -6.5, -14.5, 90, occ=15); T("relay", 6.5, -14.5, 90, occ=15)
B(R, 30, 3, 1.5, -37, -31.6, ZT, "copper", 0.2)                               # shared live bar
T("shunt", -44, -26.3, occ=4); T("shunt", -30, -26.3, occ=4); T("tco", -41, -20.5, occ=8); T("tco", -24.5, -20.5, occ=7)
T("fuse", -58.5, -21.5, 90, occ=8); T("mov", -57.5, 13.5, 0, occ=6.5); T("axial", -57.8, 26.2, 90, occ=7.5)
T("ecap_tht", -46, 28.6, occ=4.6); T("ecap_tht", -36.5, 28.6, occ=4.6); T("ind_radial", -27, 28.6, occ=4.6); T("ind_radial", -17.6, 28.6, occ=4.6)
T("sma", -17.5, -19, 90, occ=3); T("soic8", -18, -28.5, 0, occ=4)
T("ssop20", 21, 28.5, 0, occ=5.5)
for i in range(5): T("r1206", 30.5 + i * 4.3, 31, 0, occ=2.2)
T("soic8", 57.5, 27, 90, occ=4); T("sot23", 57.5, 19.5, 0, occ=2.2); T("sot23", 57.5, 13, 0, occ=2.2)
T("soic16w", 23, -25, 90, occ=7.5); B(R, 1.2, 9.0, 0.06, 23, -25, ZT - 0.02, "slot")
T("sot23", 36, -19.5, occ=2.2); T("sot23", 43, -19.5, occ=2.2); T("sma", 36, -27.5, occ=3.2); T("sma", 44, -27.5, occ=3.2)
T("sot23", 50, -19.5, occ=2.2); T("ecap_smd", 51.5, -28.5, occ=4.8); T("fpc", 60, -22, 90, occ=5)
OCC += [(-60.3, 0, 9, ZT, False), (60.3, 0, 9, ZT, False)]
for cx in (-34, 34):                                                            # outlet zones: silk outline and contact tail slots
    OCC += [(cx + dx, 4 + dy, 6.5, ZT, False) for dx in (-12, -4, 4, 12) for dy in (-13, -4.5, 4.5, 13)]
    for sx, sy, x, y in ((34, 0.25, 0, 18), (34, 0.25, 0, -18), (0.25, 36, 17, 0), (0.25, 36, -17, 0)): B(R, sx, sy, 0.03, cx + x, 4 + y, ZT, "silk")
    for dx, dy, w, h in ((-11.1, -11.1, 5.5, 2.4), (11.1, -11.1, 5.5, 2.4), (0, 11.1, 2.4, 5.5)):
        B(R, w, h, 0.05, cx + dx, 4 + dy, ZT, "tin"); B(R, w - 1.6, h - 1.6, 0.06, cx + dx, 4 + dy, ZT, "slot"); RECORD.append(dict(kind="contact", x=cx + dx, y=4 + dy, rot=0, pads=[(0, 0, w, h, 0)]))
def scatter(n, rects, zface, group, flip=False, rec=False):
    k = 0; tries = 0
    while k < n and tries < 4000:
        tries += 1; x0, y0, x1, y1 = random.choice(rects); x = random.uniform(x0, x1); y = random.uniform(y0, y1)
        if any(z == zface and f == flip and (x - ox) ** 2 + (y - oy) ** 2 < (r + 1.5) ** 2 for ox, oy, r, z, f in OCC): continue
        place(random.choice(["r0603", "c0603", "r0603", "c0603", "c0805"]), x, y, random.choice([0, 90]), group, zface, flip, rec, occ=1.4); k += 1
scatter(46, [(-52, -33, -14, -16), (-63, 8, -52, 33), (-51, 23, -14, 33), (14, 23, 63, 33), (52, 8, 63, 22), (14, -33, 56, -16)], ZT, "rear", rec=True)
# fat mains copper (lighter mask) and thin signal traces: illustrative only
for sx, sy, x, y in ((6, 9, -44, -29), (6, 9, -30, -29), (22, 5, -31, -20.5), (7, 16, -17, -8), (10, 6, -6.5, -31), (10, 6, 6.5, -31), (9, 22, -57.5, 20), (38, 3, -32, 23.5)):
    B(R, sx, sy, 0.03, x, y, ZT, "trace")
for i in range(70):
    a = random.choice(RECORD); b = random.choice(RECORD)
    if "contact" in (a["kind"], b["kind"]): continue
    if a is b or abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) > 30 or (a["x"] < -13) != (b["x"] < -13): continue
    B(R, abs(a["x"] - b["x"]) + 0.25, 0.25, 0.03, (a["x"] + b["x"]) / 2, a["y"], ZT, "trace"); B(R, 0.25, abs(a["y"] - b["y"]) + 0.25, 0.03, b["x"], (a["y"] + b["y"]) / 2, ZT, "trace")
for y in range(-33, 34, 3): B(R, 0.2, 1.6, 0.03, 13.4, y, ZT, "silk")              # barrier marking
# back face: terminal block and passives
place("terminal", 0, 26, 0, "rear", -17.6, True); OCC.append((0, 26, 18, -17.6, True))
scatter(30, [(-60, -32, 60, 18)], -17.6, "rear", True)

# ================= contact carriers with generic brass contacts =================
Cg = G("carrier")
for cx in (-34, 34):
    B(Cg, 34, 36, 21.5, cx, 4, -16, "carrier", 0.8)
    for sx in (-11.1, 11.1):                                                     # L and N: two spring leaves each
        for s in (-1, 1): B(Cg, 7.5, 0.8, 13, cx + sx, 4 - 11.1 + s * 2.3, -9, "brass", 0.15)
        B(Cg, 7.5, 5.4, 0.8, cx + sx, 4 - 11.1, -9.8, "brass"); B(Cg, 3.5, 0.8, 6.3, cx + sx, 4 - 11.1, -16, "brass")
    for s in (-1, 1): B(Cg, 0.8, 9.5, 16, cx + s * 2.3, 4 + 11.1, -10, "brass", 0.15)   # earth
    B(Cg, 5.4, 9.5, 0.8, cx, 15.1, -10.8, "brass"); B(Cg, 0.8, 3.5, 5.3, cx, 15.1, -16, "brass")
    B(Cg, 31, 9.5, 1.6, cx, 4 - 11.1, 3.8, "white", 0.3)                           # shutter
# ================= inner frame and fixing screws =================
static("frame", "smoke", "frame"); Sg = G("screw")
for sx in (-60.3, 60.3):
    C(Sg, 3.4, 1.6, sx, 0, 2.0, "steel"); B(Sg, 4.4, 0.7, 0.4, sx, 0, 3.4, "black"); C(Sg, 1.7, 24, sx, 0, -22, "steel", seg=20)
# ================= front board =================
static("front_board", "pcb", "front"); F = G("front")
for cx in (-34, 34):
    C(F, 6.0, 0.05, cx, -31.2, 6.4, "gold")                                       # touch electrode
    for s in (-1, 1):
        B(F, 3.6, 3.2, 0.06, cx + s * 7.5, -24.3, 6.37, "slot"); place("led", cx + s * 7.5, -24.3, 0, "front", 6.4)
for i in range(5):                                                               # NFC coil
    w, h = 15 - i * 1.4, 26 - i * 1.4
    for sx, sy, x, y in ((w, 0.35, 0, h / 2), (w, 0.35, 0, -h / 2), (0.35, h, w / 2, 0), (0.35, h, -w / 2, 0)): B(F, sx, sy, 0.04, x, 12 + y, 6.4, "gold")
OCC2 = len(OCC)
Fb = lambda *a, **k: place(*a, group="front", zface=4.8, flip=True, **k)
Fb("esp32", 0, -29.6, 180, occ=10); Fb("fpc", 63.5, -22, 90, occ=5); Fb("sot23", 20, -32, occ=2.2); Fb("sot23", -20, -32, occ=2.2)
Fb("soic8", 0, 20, occ=4); Fb("ind_smd", -4, 4, occ=3); Fb("sot23", 3, 4, occ=2.2); Fb("sot23", 3, -6, occ=2.2); Fb("sot23", -4, -6, occ=2.2)
scatter(34, [(-8, -16, 8, 28), (-66, 31, 66, 37), (12, -37, 58, -24), (-58, -37, -12, -24), (-67, -20, -60, 28)], 4.8, "front", True)
# ================= faceplate =================
static("faceplate", "face", "face"); Fa = G("face")
for cx in (-34, 34): B(Fa, 20, 0.6, 0.35, cx, -23, 8.65, "light")

# ================= world, lights, camera =================
zmin = -30.0
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, zmin * S)); bpy.context.object.data.materials.append(mat("ground", (0.93, 0.91, 0.91), 0.55))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.28
def area(loc, energy, size, tgt=(0, 0, 0)):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.data.energy = energy; L.data.size = size
    L.rotation_euler = (Vector(tgt) - L.location).to_track_quat("-Z", "Y").to_euler()
cam = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c", cam); sc.collection.objects.link(co); sc.camera = co
def aim(loc, tgt, lens): co.location = loc; cam.lens = lens; co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
if EXPL:
    area((-0.28, -0.22, 0.5), 2.2, 0.4, (0, 0, 0.03)); area((0.3, 0.1, 0.3), 0.5, 0.5, (0, 0, 0.03))
    aim((0.33, -0.40, 0.40), (0, 0, 0.024), 108); sc.render.resolution_x, sc.render.resolution_y = 1500, 1300
else:  # rear board only, near top-down
    for o in sc.objects:
        if o.type in ("MESH", "EMPTY"):
            root = o
            while root.parent: root = root.parent
            keep = root.name.startswith(("rear", "Plane")) or (root.type == "EMPTY" and abs(root.location.z - ZT * S) < 1e-6) or root.name == "rear_board"
            if root.type == "EMPTY" and root.name == "terminal": keep = True
            o.hide_render = not keep
    area((-0.12, -0.1, 0.35), 1.1, 0.35, (0, 0, -0.016)); area((0.2, 0.12, 0.25), 0.3, 0.4, (0, 0, -0.016))
    aim((0.0, -0.10, 0.36), (0, -0.002, -0.016), 80); sc.render.resolution_x, sc.render.resolution_y = 1600, 1050
sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6; sc.cycles.transparent_max_bounces = 16; sc.view_settings.view_transform = "Standard"
json.dump(RECORD, open("/tmp/rt/rear_top.json", "w"))
sc.render.filepath = f"/tmp/rt/{VIEW}.png"; bpy.ops.render.render(write_still=True); print("done", VIEW, len(sc.objects), "objects")
