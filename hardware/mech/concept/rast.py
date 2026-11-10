import numpy as np, pickle, sys
from PIL import Image, ImageFilter
mesh = pickle.load(open("/tmp/render/mesh.pkl","rb"))

def look(eye, tgt, up=(0,1,0)):
    eye=np.array(eye,float); f=np.array(tgt,float)-eye; f/=np.linalg.norm(f)
    r=np.cross(f,up); r/=np.linalg.norm(r); u=np.cross(r,f)
    return eye, np.stack([r,u,-f])

def render(objs, eye, tgt, W=1600, H=1000, fov=30, ss=2, bg=(246,246,244), out="r.png", up=(0,1,0)):
    W2,H2=W*ss,H*ss
    E,R=look(eye,tgt,up)
    fpx=(H2/2)/np.tan(np.radians(fov/2))
    zb=np.full((H2,W2),np.inf); img=np.zeros((H2,W2,3)); img[:]=np.array(bg)/255
    nb=np.zeros((H2,W2,3)); idb=np.full((H2,W2),-1)
    L1=np.array([-0.4,0.6,0.7]);L1/=np.linalg.norm(L1)
    L2=np.array([0.6,-0.2,0.5]);L2/=np.linalg.norm(L2)
    oid=0
    for V,T,col,off,alpha in objs:
        oid+=1
        Vw=V+np.array(off); Vc=(Vw-E)@R.T; z=-Vc[:,2]
        px=W2/2+fpx*Vc[:,0]/z; py=H2/2-fpx*Vc[:,1]/z
        for t in T:
            a,b,c=t
            if min(z[a],z[b],z[c])<=1: continue
            n=np.cross(Vw[b]-Vw[a],Vw[c]-Vw[a]); nn=np.linalg.norm(n)
            if nn==0: continue
            n/=nn
            if np.dot(n,E-Vw[a])<0: n=-n
            x0=int(max(0,np.floor(min(px[a],px[b],px[c])))); x1=int(min(W2-1,np.ceil(max(px[a],px[b],px[c]))))
            y0=int(max(0,np.floor(min(py[a],py[b],py[c])))); y1=int(min(H2-1,np.ceil(max(py[a],py[b],py[c]))))
            if x1<x0 or y1<y0: continue
            xs,ys=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
            d=(py[b]-py[c])*(px[a]-px[c])+(px[c]-px[b])*(py[a]-py[c])
            if abs(d)<1e-9: continue
            w0=((py[b]-py[c])*(xs-px[c])+(px[c]-px[b])*(ys-py[c]))/d
            w1=((py[c]-py[a])*(xs-px[c])+(px[a]-px[c])*(ys-py[c]))/d
            w2=1-w0-w1
            m=(w0>=-1e-6)&(w1>=-1e-6)&(w2>=-1e-6)
            if not m.any(): continue
            iz=w0/z[a]+w1/z[b]+w2/z[c]; zz=1/iz
            sub=zb[y0:y1+1,x0:x1+1]
            m&=zz<sub
            if not m.any(): continue
            sh=0.32+0.55*max(0,n@L1)+0.22*max(0,n@L2)
            spec=0.12*max(0,n@((L1+(E-Vw[a])/np.linalg.norm(E-Vw[a]))/2))**20
            cc=np.clip(np.array(col)*sh+spec,0,1)
            sub[m]=zz[m]
            img[y0:y1+1,x0:x1+1][m]=cc
            nb[y0:y1+1,x0:x1+1][m]=n
            idb[y0:y1+1,x0:x1+1][m]=oid
    # feature edges: normal or object discontinuities
    e=np.zeros((H2,W2),bool)
    for dy,dx in ((0,1),(1,0)):
        n1=nb; n2=np.roll(np.roll(nb,-dy,0),-dx,1)
        i2=np.roll(np.roll(idb,-dy,0),-dx,1)
        e|=((np.sum(n1*n2,axis=2)<0.85)|(idb!=i2))&((idb>=0)|(i2>=0))
    img[e]=img[e]*0.55
    im=Image.fromarray((img*255).astype(np.uint8)).resize((W,H),Image.LANCZOS)
    im.save(out); print("saved",out)

def get(k,off=(0,0,0)):
    V,T,c=mesh[k]; return (V,T,c,off,1)
