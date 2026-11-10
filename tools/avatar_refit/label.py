import numpy as np, scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
d=np.load('girl.npz'); co=d['co']; lv=d['lv']; vc=d['vc'].astype(np.float64); nv=len(co)
dom=np.load('dom.npy'); G=open('groups.txt').read().split('\n')
# weld
u,wid=np.unique(co,axis=0,return_inverse=True); wid=wid.ravel(); nw=len(u); print('welded',nw,'of',nv)
t=wid[lv].reshape(-1,3)
i=np.concatenate([t[:,0],t[:,1],t[:,2]]); j=np.concatenate([t[:,1],t[:,2],t[:,0]])
A=sp.coo_matrix((np.ones(len(i),np.float32),(i,j)),shape=(nw,nw)).tocsr(); A=((A+A.T)>0).astype(np.float32).tocsr(); A.setdiag(0); A.eliminate_zeros()
n,cl=connected_components(A,directed=False); print('welded comps',n, np.sort(np.bincount(cl))[::-1][:8])
# welded colour / dominant group
cnt=np.bincount(wid,minlength=nw).astype(np.float64)
wc=np.stack([np.bincount(wid,vc[:,k],nw)/cnt for k in range(3)],1)
wdom=np.zeros(nw,np.int16); wdom[wid]=dom
P=u; x,y,z=P[:,0],P[:,1],P[:,2]
r,g,b=wc[:,0],wc[:,1],wc[:,2]; V=wc.max(1); S=(V-wc.min(1))/np.maximum(V,1e-4)
SKIN,HAIR,TEE,JEANS,SHOE,EYE=0,1,2,3,4,5
L=np.full(nw,SKIN,np.int8)
blue=(b>r+0.04)&(b>g)
white=(S<0.22)&(V>0.40)&~blue
dark=(r>g*1.55)&(V<0.52)
L[dark&(z>1.1)]=HAIR
L[blue&(z<1.08)]=JEANS
L[white&(z<0.16)]=SHOE
L[white&(z>=0.16)&(z<1.43)]=TEE
L[white&(z>=1.43)]=EYE
gname=np.array(G)[wdom]
print('counts',np.bincount(L,minlength=6))
np.savez('weld.npz',u=u,wid=wid,wc=wc,L0=L,wdom=wdom,cl=cl)
sp.save_npz('wadj.npz',A)
cols=np.array([[0.85,0.6,0.5],[0.35,0.1,0.1],[1,1,1],[0.1,0.2,0.9],[0.9,0.9,0.2],[0,1,1]])
fig,ax=plt.subplots(1,2,figsize=(16,10),facecolor='gray')
for a,(m,sx) in zip(ax,[(y>-0.02,1),(y<0.02,-1)]):
    o=np.argsort(y[m]*sx); a.scatter(sx*x[m][o],z[m][o],c=cols[L[m][o]],s=0.05,linewidths=0); a.set_aspect('equal'); a.set_facecolor('gray'); a.axis('off')
plt.tight_layout(); plt.savefig('labels0.png',dpi=110)
