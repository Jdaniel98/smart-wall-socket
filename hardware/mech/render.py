"""Ray-traced renders of enclosure v0.1 (Blender Cycles), from out/mesh.pkl written by enclosure.py.

    python3 hardware/mech/render.py exploded|assembled|rear|section [samples]
"""
import math
import os
import pickle
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
VIEW = sys.argv[1] if len(sys.argv) > 1 else "exploded"
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 64
mesh = pickle.load(open(os.path.join(HERE, "out", "mesh.pkl"), "rb"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
S = 0.001


def mat(name, col, rough=0.5, metal=0.0, alpha=1.0, emit=0.0, coat=0.0, trans=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Alpha"].default_value = alpha
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Transmission Weight"].default_value = trans
    if emit:
        b.inputs["Emission Color"].default_value = (*col, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


see = VIEW == "exploded"
M = dict(
    faceplate=mat("face", (0.93, 0.93, 0.91), 0.35, alpha=0.45 if see else 1.0),
    inner_frame=mat("frame", (0.05, 0.05, 0.055), 0.25, alpha=0.5 if see else 1.0),
    carrier=mat("carrier", (0.16, 0.16, 0.17), 0.45),
    light=mat("light", (0.35, 0.75, 1.0), 0.2, emit=4.0),
    rear_cover=mat("cover", (0.12, 0.12, 0.13), 0.45),
    board=mat("pcb", (0.015, 0.20, 0.05), 0.35, coat=0.3),
    ld03=mat("ld03", (0.02, 0.02, 0.022), 0.45),
    relay=mat("relay", (0.03, 0.10, 0.45), 0.35, coat=0.3),
    terminal=mat("term", (0.04, 0.32, 0.12), 0.4),
    conn=mat("conn", (0.82, 0.78, 0.66), 0.5),
    esp=mat("esp", (0.75, 0.75, 0.77), 0.3, 1.0),
    ffc=mat("ffc", (0.85, 0.72, 0.35), 0.4),
    steel=mat("steel", (0.72, 0.72, 0.74), 0.3, 1.0),
)


def pick(n):
    n = n.split(":")[-1]
    if n.startswith("carrier"):
        return "carrier"
    if n.startswith("light_guide"):
        return "light"
    if n.endswith("board"):
        return "board"
    if n in ("k1", "k2"):
        return "relay"
    if n in ("j4", "j101"):
        return "conn"
    if n == "esp32":
        return "esp"
    if n.startswith("screw"):
        return "steel"
    return n if n in M else "carrier"


EXPLODE = dict(faceplate=70, light_guide_left=70, light_guide_right=70, front_board=46, j101=46, esp32=46,
               inner_frame=24, screw0=24, screw1=24, carrier_left=12, carrier_right=12, rear_cover=-16)
show = [k for k in mesh if k.startswith("sec:")] if VIEW == "section" else [k for k in mesh if not k.startswith("sec:")]
if VIEW in ("exploded",):
    show = [k for k in show if k not in ("ffc",)]
for k in show:
    V, T = mesh[k]
    dz = EXPLODE.get(k, 0) if VIEW == "exploded" else 0
    me = bpy.data.meshes.new(k)
    me.from_pydata([(x * S, y * S, (zz + dz) * S) for x, y, zz in V], [], [tuple(int(i) for i in t) for t in T])
    me.update()
    o = bpy.data.objects.new(k, me)
    sc.collection.objects.link(o)
    o.data.materials.append(M[pick(k)])

zmin = -60 if VIEW == "exploded" else -40
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, zmin * S))
bpy.context.object.data.materials.append(mat("ground", (0.93, 0.91, 0.91), 0.55))
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.3


def area(loc, energy, size, tgt=(0, 0, 0)):
    bpy.ops.object.light_add(type="AREA", location=loc)
    L = bpy.context.object
    L.data.energy = energy
    L.data.size = size
    L.rotation_euler = (Vector(tgt) - L.location).to_track_quat("-Z", "Y").to_euler()


cam = bpy.data.cameras.new("c")
co = bpy.data.objects.new("c", cam)
sc.collection.objects.link(co)
sc.camera = co


def aim(loc, tgt, lens):
    co.location = loc
    cam.lens = lens
    co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


if VIEW == "exploded":
    area((-0.28, -0.22, 0.5), 2.2, 0.4, (0, 0, 0.02)); area((0.3, 0.1, 0.3), 0.5, 0.5, (0, 0, 0.02))
    aim((0.33, -0.40, 0.40), (0, 0, 0.012), 92); res = (1500, 1400)
elif VIEW == "assembled":
    bpy.data.objects["Plane"].location.z = -0.00002          # the wall: hides everything behind the plate
    area((-0.28, -0.22, 0.5), 2.0, 0.4); area((0.3, 0.1, 0.3), 0.5, 0.5)
    aim((0.20, -0.30, 0.38), (0, 0, 0.0), 95); res = (1600, 1100)
elif VIEW == "rear":
    area((0.25, 0.22, -0.5), 2.0, 0.4); area((-0.3, -0.1, -0.3), 0.6, 0.5)
    bpy.data.objects["Plane"].hide_render = True
    aim((0.22, 0.30, -0.36), (0, 0, -0.012), 95); res = (1600, 1100)
else:  # section, viewed square-on from the cut side
    area((-0.2, -0.35, 0.3), 2.0, 0.5, (0, 0, -0.01)); area((0.25, -0.3, -0.1), 0.6, 0.5, (0, 0, -0.01))
    aim((0.0, -0.42, 0.10), (0, 0, -0.012), 85); res = (1800, 900)
sc.render.resolution_x, sc.render.resolution_y = res
sc.render.engine = "CYCLES"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
sc.cycles.transparent_max_bounces = 16
sc.view_settings.view_transform = "Standard"
os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
sc.render.filepath = os.path.join(HERE, "renders", f"enclosure_v0.1_{VIEW}.png")
bpy.ops.render.render(write_still=True)
print("done", VIEW)
