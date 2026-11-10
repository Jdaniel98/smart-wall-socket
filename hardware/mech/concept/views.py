import sys; sys.path.insert(0,"/tmp/render")
from rast import *
import numpy as np
# wall plane quad as a mesh
wall=(np.array([[-600,-400,-0.02],[600,-400,-0.02],[600,400,-0.02],[-600,400,-0.02]]),np.array([[0,1,2],[0,2,3]]),(0.90,0.89,0.86),(0,0,0),1)
keys=list(mesh)
# 1 assembled on the wall
render([wall]+[get(k) for k in keys if k!="backbox"], eye=(-150,70,260), tgt=(0,0,0), out="/tmp/render/1_assembled.png")
# 2 exploded (box hidden)
off={"frame":(0,0,26),"screw-60.3":(0,0,26),"screw60.3":(0,0,26),"fpc_front":(0,0,42),"faceplate":(0,0,70),"light0":(0,0,70),"light1":(0,0,70),"front_board":(0,0,42),"esp32":(0,0,42),
     "carrier0":(0,0,14),"carrier1":(0,0,14)}
objs=[]
for k in keys:
    if k=="backbox": continue
    o=off.get(k,(0,0,0))
    if k.startswith("contact"): o=(0,0,14)
    objs.append(get(k,o))
render(objs, eye=(-210,150,230), tgt=(0,0,15), out="/tmp/render/2_exploded.png", fov=34)
# 3 inside the back box: faceplate and front board removed
render([get(k) for k in keys if k in ("backbox","rear_board","ld03","busbar","ffc","fpc_rear","frame") or k.startswith(("relay","carrier","contact","screw"))],
       eye=(-120,140,170), tgt=(0,0,-15), out="/tmp/render/3_in_box.png", fov=34)

# 4 back view: what the electrician sees (box hidden)
render([get(k) for k in keys if k!="backbox"], eye=(150,110,-230), tgt=(0,0,-8), out="/tmp/render/4_back.png", fov=34, back=True)
