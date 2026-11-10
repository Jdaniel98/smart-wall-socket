import bpy, pickle, sys, math
from mathutils import Vector
mesh = pickle.load(open("/tmp/render/mesh.pkl","rb"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
S = 0.001  # mm -> m
off = {"faceplate":62,"light0":62,"light1":62,"front_board":40,"esp32":40,"fpc_front":40,"frame":22,"screw-60.3":22,"screw60.3":22,
       "terminal":-14,"term_screw0":-14,"term_screw1":-14,"term_screw2":-14}
def mat(name, col, rough=0.5, metal=0.0, alpha=1.0, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Alpha"].default_value = alpha
    if emit: b.inputs["Emission Color"].default_value = (*col,1); b.inputs["Emission Strength"].default_value = emit
    return m
M = {"pcb": mat("pcb",(0.02,0.22,0.07),0.35), "smoke": mat("smoke",(0.03,0.03,0.035),0.15,alpha=0.42),
     "white": mat("white",(0.9,0.9,0.88),0.35,alpha=0.55), "brass": mat("brass",(0.85,0.6,0.2),0.3,1.0),
     "copper": mat("copper",(0.85,0.4,0.2),0.3,1.0), "steel": mat("steel",(0.7,0.7,0.72),0.3,1.0),
     "black": mat("black",(0.02,0.02,0.022),0.4), "blue": mat("blue",(0.03,0.08,0.35),0.35),
     "carrier": mat("carrier",(0.08,0.08,0.09),0.5), "ffc": mat("ffc",(0.85,0.85,0.8),0.4),
     "light": mat("light",(0.3,0.7,1.0),0.3,emit=6.0), "green": mat("green",(0.05,0.3,0.12),0.4)}
def pick(k):
    if k=="faceplate": return "white"
    if k.endswith("board"): return "pcb"
    if k=="frame": return "smoke"
    if k.startswith("contact"): return "brass"
    if k=="busbar": return "copper"
    if k.startswith(("screw","term_screw","esp")): return "steel"
    if k=="ld03": return "black"
    if k.startswith("relay"): return "blue"
    if k.startswith("carrier"): return "carrier"
    if k.startswith(("ffc","fpc")): return "ffc"
    if k.startswith("light"): return "light"
    if k=="terminal": return "green"
    return "black"
for k,(V,T,c) in mesh.items():
    if k=="backbox": continue
    dz = off.get(k, 8 if k.startswith(("carrier","contact")) else 0)
    me = bpy.data.meshes.new(k); me.from_pydata([((x)*S,(y)*S,(z+dz)*S) for x,y,z in V],[],[tuple(int(i) for i in t) for t in T]); me.update()
    o = bpy.data.objects.new(k, me); sc.collection.objects.link(o); o.data.materials.append(M[pick(k)])
# ground + lights
bpy.ops.mesh.primitive_plane_add(size=4, location=(0,0,-0.048)); g = bpy.context.object; g.data.materials.append(mat("g",(0.92,0.9,0.9),0.6))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value=(1,1,1,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.45
bpy.ops.object.light_add(type='AREA', location=(-0.25,-0.2,0.45)); L = bpy.context.object; L.data.energy=2.2; L.data.size=0.35
L.rotation_euler = (Vector((0,0,0.02))-L.location).to_track_quat('-Z','Y').to_euler()
cam = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c",cam); sc.collection.objects.link(co); sc.camera = co
co.location = (0.36,-0.42,0.36); cam.lens = 70
co.rotation_euler = (Vector((0,0,0.016))-co.location).to_track_quat('-Z','Y').to_euler()
sc.render.engine='CYCLES'; sc.cycles.samples=int(sys.argv[-1]) if sys.argv[-1].isdigit() else 48
try: sc.cycles.use_denoising=True
except Exception as e: print(e)
sc.cycles.max_bounces=6; sc.cycles.transparent_max_bounces=12
sc.render.resolution_x=1400; sc.render.resolution_y=1050; sc.view_settings.view_transform='Standard'
sc.render.filepath="/tmp/render/5_exploded_cycles.png"; bpy.ops.render.render(write_still=True); print("done")
