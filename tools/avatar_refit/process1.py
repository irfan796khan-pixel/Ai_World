import numpy as np, scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
d=np.load('weld.npz'); u=d['u']; wc=d['wc']; L=d['L0'].copy(); nw=len(u)
A=sp.load_npz('wadj.npz').tocsr()
SKIN,HAIR,TEE,JEANS,SHOE,EYE=0,1,2,3,4,5
z=u[:,2]
deg=np.asarray(A.sum(1)).ravel()
def neigh_major(L,mask):
    votes=np.stack([A@(L==k).astype(np.float32) for k in range(6)],1)
    return votes
# 1 small components -> majority neighbour label
L0=L.copy()
for it in range(3):
    for k in range(5):  # not EYE
        m=np.where(L==k)[0]
        if len(m)==0: continue
        sub=A[m][:,m]; n,cl=connected_components(sub,directed=False); cnt=np.bincount(cl)
        small=cnt[cl]<(600 if k!=HAIR else 300)
        idx=m[small]
        if len(idx)==0: continue
        votes=neigh_major(L,None)[idx]; votes[:,k]=0; votes[:,EYE]=0
        new=votes.argmax(1); has=votes.max(1)>0
        L[idx[has]]=new[has]
# 2 majority smoothing (2 passes), keep EYE fixed
for it in range(2):
    votes=neigh_major(L,None); votes[np.arange(nw),L]+=0.5
    new=votes.argmax(1); ch=(new!=L)&(L!=EYE)&(new!=EYE)&(votes.max(1)>deg*0.6)
    L[ch]=new[ch]
print('relabelled',(L!=L0).sum(), np.bincount(L,minlength=6))
# 3 boundary distance
K=4
bnd=np.zeros(nw,bool)
for k in range(6):
    mk=(L==k).astype(np.float32); other=(A@(1-mk))>0
    bnd|=(L==k)&other
# exclude boundaries that only involve EYE (leave eyes/teeth untouched)
eye_adj=((A@(L==EYE).astype(np.float32))>0)|(L==EYE)
bnd&=~eye_adj
dist=np.full(nw,99,np.int16); dist[bnd]=0; fr=bnd.copy()
for dd in range(1,K+1):
    nb=((A@fr.astype(np.float32))>0)&(dist==99); dist[nb]=dd; fr=nb
band=(dist<K)|((L!=L0))
band&=~eye_adj
# face protection: front of face keeps eyebrows/lashes/lips detail unless on the true hairline
face=(z>1.40)&(u[:,1]>0.045)&(np.abs(u[:,0])<0.075)&(z<1.60)
band&=~face
print('band verts',band.sum())
# 4 fill colours from good verts of same label
col=wc.copy(); known=~band
for k in range(5):
    mk=(L==k)
    Ak=A.multiply(mk.astype(np.float32)[None,:]).tocsr()  # only same-label sources
    for it in range(40):
        todo=mk&~known
        if not todo.any(): break
        kn=(known&mk).astype(np.float32)
        s=Ak@kn; can=todo&(s>0)
        if not can.any(): break
        num=np.stack([Ak@(col[:,c]*kn) for c in range(3)],1)
        col[can]=num[can]/s[can,None]; known[can]=True
    left=(mk&~known).sum()
    print('label',k,'unfilled',left)
w=band.astype(np.float32); w[~known]=0
# light smoothing of filled colours inside band (same label) to avoid streaks
for it in range(2):
    for k in range(5):
        mk=(L==k)&(w>0)
        Ak=A.multiply((L==k).astype(np.float32)[None,:]).tocsr(); s=np.asarray(Ak.sum(1)).ravel()
        avg=np.stack([Ak@col[:,c] for c in range(3)],1)/np.maximum(s,1)[:,None]
        col[mk]=0.5*col[mk]+0.5*avg[mk]
np.savez('stage1.npz',L=L,col=col.astype(np.float32),w=w,dist=dist)
