import numpy as np, scipy.sparse as sp
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
d=np.load('weld.npz'); u=d['u'].astype(np.float64); wid=d['wid']; wc=d['wc']; wdom=d['wdom']; nw=len(u)
g0=np.load('girl.npz'); lv=g0['lv']
A=sp.load_npz('wadj.npz').tocsr(); deg=np.maximum(np.asarray(A.sum(1)).ravel(),1)
L=np.load('stage1.npz')['L'].astype(np.int8)
G=open('groups.txt').read().split('\n'); gn=np.array(G)[wdom]
SKIN,HAIR,TEE,JEANS,SHOE,EYE,JACKET,METAL,GOLD,RIP=range(10)
T=wid[lv].reshape(-1,3)
def normals(P):
    fn=np.cross(P[T[:,1]]-P[T[:,0]],P[T[:,2]]-P[T[:,0]])
    n=np.zeros_like(P)
    for k in range(3): np.add.at(n,T[:,k],fn)
    return n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
def sstep(a,b,v): t=np.clip((v-a)/(b-a),0,1); return t*t*(3-2*t)
x,y,z=u.T
hand=np.char.find(gn,'Hand')>=0; hand|=np.isin(gn,['hand.L','hand.R'])
face=(z>1.40)&(y>0.04)&(np.abs(x)<0.08)&(z<1.62)
# ---------- 1. gentle Taubin smoothing (not face / hands / eyes) ----------
wint=np.zeros(nw,bool); wint[wid[np.load('interior.npz')['mask']]]=True
P=u.copy(); fixed=face|hand|(L==EYE)|wint
for it in range(4):
    for lam in (0.5,-0.53):
        avg=np.stack([A@P[:,k] for k in range(3)],1)/deg[:,None]
        P=np.where(fixed[:,None],P,P+lam*(avg-P))
dl=P-u; nrm=np.linalg.norm(dl,axis=1,keepdims=True); P=u+dl*np.minimum(1,0.003/np.maximum(nrm,1e-9))
print('smooth max move mm',np.abs(P-u).max()*1000, 'mean',np.linalg.norm(P-u,axis=1).mean()*1000)
N=normals(P)
# smooth 'head surface' reference: heavy Laplacian of positions
Ps=P.copy()
for it in range(40): Ps=0.5*Ps+0.5*np.stack([A@Ps[:,k] for k in range(3)],1)/deg[:,None]
bump=((P-Ps)*N).sum(1)
# ---------- 2. parts ----------
L2=L.copy()
R=(L==SKIN)&(z>1.576)&(z<1.66)&(np.abs(x)<0.08)&(y>0.03)
def feat(xx,zz): return np.stack([np.ones_like(xx),xx,zz,xx*xx,zz*zz,xx*zz,xx**4],1)
keep=R.copy()
for it in range(8):
    cf,_,_,_=np.linalg.lstsq(feat(x[keep],z[keep]),y[keep],rcond=None)
    res=y-feat(x,z)@cf
    keep=R&(res<0.0010)&(res>-0.004)
cand=R&(res>0.0014)
for it in range(4):
    nb=(A@cand.astype(np.float32)); cand=(cand|(R&(nb>=deg*0.45)&(res>0.0006)))&~(R&(nb<=deg*0.2)&(res<0.003))
print('hair locks repainted verts',cand.sum())
L2[cand]=HAIR
# extra smoothing of the hair only (spiky tips)
hairv=(L2==HAIR)&~face&~wint
Ph=P.copy()
for it in range(8):
    for lam in (0.55,-0.57):
        avg=np.stack([A@Ph[:,k] for k in range(3)],1)/deg[:,None]
        Ph=np.where(hairv[:,None],Ph+lam*(avg-Ph),Ph)
dl=Ph-u; nrm=np.linalg.norm(dl,axis=1,keepdims=True); P=u+dl*np.minimum(1,0.005/np.maximum(nrm,1e-9))
N=normals(P)
# forehead lock painted skin colour -> hair
# earrings
for sg,(cy,cz) in ((1,(0.022,1.462)),(-1,(0.018,1.462))):
    r=np.hypot(y-cy,z-cz)
    e=(L==SKIN)&(sg*x>0.0845)&(sg*x<0.108)&(r<0.0215)&(r>0.005)&(z<1.4805)
    L2[e]=GOLD
# jacket
arm=np.isin(gn,['upper_arm.L','forearm.L','upper_arm.R','forearm.R','shoulder.L','shoulder.R'])
sleeve=(L==SKIN)&arm&(np.abs(x)>0.17)&(np.abs(x)<0.587)&(z>1.19)&(z<1.36)
hws=0.022+np.clip((z-1.0)/0.30,0,1)*0.034
hw=hws+0.028
front=N[:,1]>0.25
opening=(L==TEE)&front&(np.abs(x)<hw)
neckV=(L==TEE)&front&(z>1.285)&(np.abs(x)<0.048+ (z-1.285)*1.4)   # widen V at the top
opening|=neckV
jacket=((L==TEE)&~opening)|sleeve
L2[jacket]=JACKET
for it in range(4):
    vj=A@(L2==JACKET).astype(np.float32); vt=A@(L2==TEE).astype(np.float32)
    tj=(L2==TEE)&(vj>vt); jt=(L2==JACKET)&(vt>vj)&(L==TEE)
    L2[tj]=JACKET; L2[jt]=TEE
jacket=(L2==JACKET)
# ---------- 3. displacement ----------
D=np.zeros(nw)
jk=(L2==JACKET)|(L2==METAL)
D[jk]=0.0
lapel=jk&front&(np.abs(x)<hw+0.036)&(z>1.12)
pass
pass
pass
pass
# quilted ribs on shoulders and forearms
rib=jk&(((np.abs(x)>0.205)&(np.abs(x)<0.285))|((np.abs(x)>0.47)&(np.abs(x)<0.555)))
ribwave=np.sin(np.abs(x)*2*np.pi/0.013)
pass
# jeans: loosen lower leg, cargo pockets
je=(L2==JEANS)
loose=np.zeros(nw); loose[je]=0.013*sstep(0.62,0.36,z[je])*sstep(0.105,0.14,z[je])+0.004*sstep(0.14,0.105,z[je])
pocket=np.zeros(nw,bool); flap=np.zeros(nw,bool); snap=np.zeros(nw,bool); pedge=np.zeros(nw,bool)
for sg in (1,-1):
    side=je&(sg*N[:,0]>0.5)&(sg*x>0.09)
    for (z0,z1,zf,yc,hy) in ((0.565,0.715,0.675,0.005,0.046),(0.295,0.405,0.375,-0.022,0.036)):
        p=side&(z>z0)&(z<z1)&(np.abs(y-yc)<hy)
        pocket|=p; f=p&(z>zf); flap|=f
        pedge|=p&((np.abs(z-zf)<0.0022)|(np.abs(np.abs(y-yc)-hy)<0.0022)|(z-z0<0.0022))
        snap|=f&(np.hypot(y-yc,z-(zf+z1)/2)<0.0065)
D+=loose; D[pocket]+=0.0065; D[flap]+=0.003
L2[snap]=METAL
# rips
rip=np.zeros(nw,bool)
for (cx,cz,rx,rz) in ((0.092,0.475,0.036,0.013),(-0.095,0.655,0.034,0.012),(0.105,0.625,0.022,0.009),(-0.088,0.44,0.026,0.010)):
    rip|=je&(N[:,1]>0.55)&(((x-cx)/rx)**2+((z-cz)/rz)**2<1)
ripv=rip&~pocket
for it in range(2): D=0.5*D+0.5*(A@D)/deg
D[wint]=0
Pn=P+N*D[:,None]
Nn=normals(Pn)
# ---------- 4. colours (sRGB 0..1) ----------
def lin(c): return np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
def srgb(c): c=np.clip(c,0,1); return np.where(c<=0.0031308,c*12.92,1.055*c**(1/2.4)-0.055)
wl=lin(wc); lum=(0.2126*wl[:,0]+0.7152*wl[:,1]+0.0722*wl[:,2])
col=wl.copy()                       # linear working colour per welded vertex
mj=(L2==JEANS).astype(np.float32)   # per-texel jeans transform mask
md=((L2==SHOE)|(L2==TEE)).astype(np.float32)
def jeans_tf(l): return l*0.62+0.010
col[L2==JEANS]=jeans_tf(lum[L2==JEANS])[:,None]*np.array([0.96,0.98,1.06])
col[md>0]=np.clip(lum[md>0]*1.10,0,1)[:,None]
w=np.zeros(nw,np.float32)
facebox0=(z>1.40)&(y>0.03)&(np.abs(x)<0.082)&(z<1.60)
hm=(L2==HAIR)&~(facebox0&(L==HAIR))
HUE=np.array([0.066,0.0165,0.013]); HREF=0.023
def hair_tf(l): return np.clip(l,0.007,0.052)/HREF
hl=lum.copy(); hl[cand]=HREF
col[hm]=hair_tf(hl[hm])[:,None]*HUE
w[cand]=1
mh=hm.astype(np.float32); mh[cand]=0
# leather: near black with a little of the old shading
jm=(L2==JACKET); shade=np.clip(lum[jm]/np.median(lum[L==TEE]),0.5,1.25)
col[jm]=(0.017*shade**1.5)[:,None]*np.array([1.0,1.0,1.08]); w[jm]=1
lap_edge=jm&front&(np.abs(x)<hw+0.036)&(np.abs(x)>hw+0.031)&(z>1.12)
mt=(L2==METAL); col[mt]=np.array([0.55,0.56,0.60]); w[mt]=1
gd=(L2==GOLD); gs=np.clip(lum[gd]/np.median(lum[gd]),0.6,1.4); col[gd]=gs[:,None]*np.array([0.72,0.42,0.05]); w[gd]=1
pk=pocket&(L2==JEANS); col[pk]*=1.25; col[pedge&(L2==JEANS)]*=0.35; w[pocket&(L2!=METAL)]=1
hairfix=(L2==HAIR)&(L!=HAIR)
# ---------- 5. border cleanup on new parts ----------
K=3
bnd=np.zeros(nw,bool)
for k in range(10):
    mk=(L2==k).astype(np.float32); bnd|=(L2==k)&((A@(1-mk))>0)
eye_adj=((A@(L2==EYE).astype(np.float32))>0)|(L2==EYE)
bnd&=~eye_adj
dist=np.full(nw,99,np.int16); dist[bnd]=0; fr=bnd.copy()
for dd in range(1,K+1):
    nb=((A@fr.astype(np.float32))>0)&(dist==99); dist[nb]=dd; fr=nb
facebox=(z>1.40)&(y>0.03)&(np.abs(x)<0.082)&(z<1.60)
band=((dist<K)|(L2!=np.load('weld.npz')['L0'])|hairfix)&~eye_adj&~facebox
band&=~np.isin(L2,[JACKET,METAL,GOLD,RIP])   # those are already flat-painted
band&=~(pocket)
known=~band; unf=0
for k in (SKIN,HAIR,TEE,JEANS,SHOE):
    mk=(L2==k); Ak=A.multiply(mk.astype(np.float32)[None,:]).tocsr()
    for it in range(60):
        todo=mk&~known
        if not todo.any(): break
        kn=(known&mk).astype(np.float64); s=Ak@kn; can=todo&(s>0)
        if not can.any(): break
        num=np.stack([Ak@(col[:,c]*kn) for c in range(3)],1); col[can]=num[can]/s[can,None]; known[can]=True
    unf+=(mk&~known).sum()
print('band',band.sum(),'unfilled',unf)
w[band&known]=1
# per-texel zone: front of the tee near the opening
zone=np.isin(L2,[TEE,JACKET])&(L==TEE)&front&(np.abs(x)<np.maximum(hw,0.048+(z-1.285)*1.4)+0.014)&(z>0.99)
mfz=zone.astype(np.float32)
jcol=col.copy(); tj=(L==TEE); sh=np.clip(lum[tj]/np.median(lum[L==TEE]),0.5,1.25); jcol[tj]=(0.017*sh**1.5)[:,None]*np.array([1.0,1.0,1.08])
w[zone]=0
mrip=((L2==JEANS)&(N[:,1]>0.45)&~pocket).astype(np.float32)
# ---------- 6. roughness / metal ----------
rough=np.full(nw,0.9,np.float32); metal=np.zeros(nw,np.float32)
rough[L2==JACKET]=0.36; rough[L2==HAIR]=0.62; rough[L2==SHOE]=0.7; rough[L2==EYE]=0.35
rough[L2==METAL]=0.3; rough[L2==GOLD]=0.25
print('parts',np.bincount(L2,minlength=10))
np.savez('final.npz',P=Pn[wid].astype(np.float32),N=Nn[wid].astype(np.float32),col=col[wid].astype(np.float32),w=w[wid],mj=mj[wid],md=md[wid],rough=rough[wid],metal=metal[wid],mfz=mfz[wid],jcol=jcol[wid].astype(np.float32),mrip=mrip[wid],mh=mh[wid],L2=L2[wid])
# preview scatter (approximate final colours)
prev=srgb(col)
fig,ax=plt.subplots(1,2,figsize=(18,11),facecolor='#bbb')
for a,(m,sx) in zip(ax,[(Nn[:,1]>0,1),(Nn[:,1]<0,-1)]):
    o=np.argsort(Pn[m,1]*sx); a.scatter(sx*Pn[m,0][o],Pn[m,2][o],c=prev[m][o],s=0.25,linewidths=0); a.set_aspect('equal'); a.set_facecolor('#bbb'); a.axis('off')
plt.tight_layout(); plt.savefig('preview.png',dpi=100)

# =================== JACKET SHELL (separate mesh) ===================
openS=(L==TEE)&front&(np.abs(x)<np.maximum(hws,0.02+(z-1.285)*1.4))
S=((L==TEE)&~openS)|sleeve
keepT=S[T].all(1); Ts=T[keepT]
sid=np.where(S)[0]; remap=np.full(nw,-1); remap[sid]=np.arange(len(sid)); Ts=remap[Ts]
ns=len(sid)
ii=np.concatenate([Ts[:,0],Ts[:,1],Ts[:,2]]); jj=np.concatenate([Ts[:,1],Ts[:,2],Ts[:,0]])
As=sp.coo_matrix((np.ones(len(ii),np.float32),(ii,jj)),shape=(ns,ns)).tocsr(); As=((As+As.T)>0).astype(np.float32).tocsr(); dgs=np.maximum(np.asarray(As.sum(1)).ravel(),1)
xs,ys,zs=x[sid],y[sid],z[sid]; Ns_=N[sid]; fr=front[sid]; tors=((L[sid]==TEE)|(L[sid]==JEANS))
t=np.full(ns,0.0085)
t[np.abs(xs)>0.565]+=0.003                                   # cuffs
t+=0.0016*np.sin(np.abs(xs)*2*np.pi/0.013)*(((np.abs(xs)>0.205)&(np.abs(xs)<0.285))|((np.abs(xs)>0.47)&(np.abs(xs)<0.555)))
t[zs>1.305]+=0.006*sstep(1.305,1.325,zs[zs>1.305])           # collar band
Q=P[sid]+Ns_*t[:,None]
# hang straight from the ribs instead of hugging the waist
zc=np.linspace(0.96,1.34,16); yc_s=np.array([np.median(y[((L==TEE)|(L==JEANS))&(np.abs(x)<0.12)&(np.abs(z-c)<0.015)]) for c in zc])
ycs=np.interp(zs,zc,yc_s); dx,dy=Q[:,0],Q[:,1]-ycs; rad=np.hypot(dx,dy); th=np.arctan2(dy,dx)
nb_=90; bins=((th+np.pi)/(2*np.pi)*nb_).astype(int)%nb_
ref=tors&(np.abs(xs)<0.145)&(zs>1.12)&(zs<1.20)
Rref=np.array([np.percentile(rad[ref&(bins==b)],80) if (ref&(bins==b)).sum()>20 else np.nan for b in range(nb_)])
ok=~np.isnan(Rref); Rref=np.interp(np.arange(nb_),np.where(ok)[0],Rref[ok],period=nb_)
for it in range(6): Rref=(np.roll(Rref,1)+2*Rref+np.roll(Rref,-1))/4
rt=Rref[bins]*0.99+0.004
blend=sstep(1.20,1.10,zs)*(1-sstep(0.13,0.17,np.abs(xs)))
push=np.where(tors,np.clip(rt-rad,0,0.045)*blend,0.0)
for it in range(12): push=np.where(tors,0.5*push+0.5*(As@push)/dgs,0.0)
ux,uy=dx/np.maximum(rad,1e-6),dy/np.maximum(rad,1e-6)
Q[:,0]+=ux*push; Q[:,1]+=uy*push
# front panels stand away from the shirt and open a little toward the hem
dedge=np.where(fr&tors,np.abs(xs)-np.maximum(hws[sid],0.02+(zs-1.285)*1.4),1.0); dedge=np.clip(dedge,0,1)
fl=np.exp(-dedge/0.035)*(fr&tors)
Q[:,1]+=0.010*fl*sstep(1.33,1.12,zs)
Q[:,0]+=np.sign(xs)*0.010*fl*sstep(1.25,0.98,zs)
for it in range(3): Q=0.6*Q+0.4*np.stack([As@Q[:,k] for k in range(3)],1)/dgs[:,None]
# clean straight hem and cuffs: flatten the ragged border onto a line
lowz=tors&(Q[:,2]<1.012); Q[lowz,2]=1.0-0.006+0.0*Q[lowz,2]
Q[tors&(Q[:,2]<1.03)&~lowz,2]-=0.006*sstep(1.03,1.012,Q[tors&(Q[:,2]<1.03)&~lowz,2])
cf=(~tors)&(np.abs(xs)>0.575); Q[cf,0]=np.sign(xs[cf])*np.minimum(np.abs(Q[cf,0]),0.587)
def nrm_s(Pp):
    fn=np.cross(Pp[Ts[:,1]]-Pp[Ts[:,0]],Pp[Ts[:,2]]-Pp[Ts[:,0]]); n_=np.zeros_like(Pp)
    for k in range(3): np.add.at(n_,Ts[:,k],fn)
    return n_/np.maximum(np.linalg.norm(n_,axis=1,keepdims=True),1e-12)
Nq=nrm_s(Q)
Qin=Q-Nq*0.003
print('jacket shell verts',ns,'tris',len(Ts),'stand-off at hem mm (median)',np.median(push[tors&(zs<1.02)])*1000)
# representative original vertex for skin weights
rep=np.zeros(nw,np.int64); rep[wid]=np.arange(len(wid))
np.savez('shell.npz',Q=Q.astype(np.float32),Qin=Qin.astype(np.float32),N=Nq.astype(np.float32),T=Ts.astype(np.uint32),src=rep[sid],dedge=dedge.astype(np.float32))
