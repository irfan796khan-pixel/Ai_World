import numpy as np, sys
sys.path.insert(0,'/home/claude/irfan796khan-pixel/ai_world/tools'); import glbio
g=glbio.load('/home/claude/irfan796khan-pixel/ai_world/Girl_character_mixamo.glb'); p=g.meshes[0].primitives[0]
uv=glbio.read(g,p.attributes.TEXCOORD_0); pos=glbio.read(g,p.attributes.POSITION)
a=g.accessors[p.attributes.TEXCOORD_0]; print('uv comp',a.componentType,uv.dtype,uv.shape)
uu,inv,cnt=np.unique(uv,axis=0,return_inverse=True,return_counts=True); inv=inv.ravel()
top=np.argsort(-cnt)[:5]
for t in top: print('uv',uu[t],'count',cnt[t],'pos mean',np.round(pos[inv==t].mean(0),3))
teeth=inv==top[0]; cav=inv==top[1]; tongue=inv==top[2]
print('cavity',cav.sum(),'teeth',teeth.sum(),'tongue',tongue.sum())
print('cavity depth range gltf z',pos[cav][:,2].min(),pos[cav][:,2].max())
# free atlas space
W=4096; cell=16; n=W//cell
occ=np.zeros((n,n),bool); ij=np.clip((uv*n).astype(int),0,n-1); occ[ij[:,1],ij[:,0]]=True
from scipy.ndimage import binary_dilation, uniform_filter
occd=binary_dilation(occ,iterations=1)
free=~occd
print('free cells',free.sum(),'of',n*n)
# find free rectangles: need 8x4 cells (256x128 px) for cavity, 4x4 for teeth, 4x4 for tongue
def find(h,w,taken):
    f=free&~taken
    for r in range(n-h):
        for c in range(n-w):
            if f[r:r+h,c:c+w].all(): return r,c
    return None
taken=np.zeros((n,n),bool); res={}
for name,(h,w) in (('cav',(3,7)),('teeth',(3,3)),('tongue',(3,3)),('leather',(3,8))):
    rc=find(h,w,taken); print(name,rc); r,c=rc; taken[r:r+h,c:c+w]=True; res[name]=(r*cell,c*cell,h*cell,w*cell)
newuv=uv.copy()
r0,c0,hh,ww=res['cav']; depth=np.clip((pos[cav][:,2]-pos[cav][:,2].min())/(pos[cav][:,2].max()-pos[cav][:,2].min()),0,1)  # 0 at lips (front=-z) -> 1 deep
newuv[cav,0]=(c0+12+depth*(ww-24))/W; newuv[cav,1]=(r0+hh/2)/W
for name,m in (('teeth',teeth),('tongue',tongue)):
    r0,c0,hh,ww=res[name]; newuv[m]=((c0+ww/2)/W,(r0+hh/2)/W)
np.savez('interior.npz',mask=(cav|teeth|tongue),newuv=newuv.astype(np.float32),boxes=np.array([res['cav'],res['teeth'],res['tongue'],res['leather']]))
