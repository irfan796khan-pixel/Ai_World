import numpy as np, io, sys
sys.path.insert(0,'/home/claude/irfan796khan-pixel/ai_world/tools')
from pygltflib import GLTF2, Image as GImage, Texture, TextureInfo, BufferView
from PIL import Image
import glbio
SRC='/home/claude/irfan796khan-pixel/ai_world/Girl_character_mixamo.glb'
g=glbio.load(SRC); F=np.load('final.npz'); g0=np.load('girl.npz')
p=g.meshes[0].primitives[0]
pos=glbio.read(g,p.attributes.POSITION)
J0=glbio.read(g,p.attributes.JOINTS_0); W0=glbio.read(g,p.attributes.WEIGHTS_0)
co=g0['co']; conv=np.stack([co[:,0],co[:,2],-co[:,1]],1)
print('order match max diff',np.abs(conv-pos).max())
assert np.abs(conv-pos).max()<1e-5
P=F['P']; Nn=F['N']
newpos=np.stack([P[:,0],P[:,2],-P[:,1]],1).astype(np.float32)
newnor=np.stack([Nn[:,0],Nn[:,2],-Nn[:,1]],1).astype(np.float32)
blob=bytearray(g.blob)
def write(acc_i,arr):
    a=g.accessors[acc_i]; bv=g.bufferViews[a.bufferView]; off=(bv.byteOffset or 0)+(a.byteOffset or 0)
    assert bv.byteStride in (None,12), bv.byteStride
    b=arr.tobytes(); blob[off:off+len(b)]=b
a=g.accessors[p.attributes.POSITION]
I=np.load('interior.npz'); im=I['mask']
oldnor=glbio.read(g,p.attributes.NORMAL); newnor[im]=oldnor[im]; newpos[im]=pos[im]
# teeth: close the gaps so each row reads as one solid band with a softly scalloped edge
uv0=glbio.read(g,p.attributes.TEXCOORD_0)
tidx=np.where(np.abs(uv0-np.array([0.6748047,0.83691406])).max(1)<1e-6)[0]
teeth=tidx.reshape(12,-1)
for k_,ids in enumerate(teeth):
    c=pos[ids].mean(0); up=k_<6
    S,Wd,Hh=(1.22,1.62,0.92) if up else (1.18,1.55,0.95)
    v=pos[ids].copy()
    nx=c[0]*S+(v[:,0]-c[0])*Wd
    v[:,2]+=0.020*((c[0]*S)**2-c[0]**2)/0.0004            # stay on the dental arc
    v[:,1]=c[1]+(v[:,1]-c[1])*Hh
    v[:,0]=nx; newpos[ids]=v
print('teeth rows widened',len(teeth))
write(p.attributes.POSITION,newpos); a.min=newpos.min(0).tolist(); a.max=newpos.max(0).tolist()
write(p.attributes.NORMAL,newnor)
write(p.attributes.TEXCOORD_0,I['newuv'])
# ---------------- jawOpen: almond-shaped opening instead of a box ----------------
from pygltflib import Accessor, Sparse, AccessorSparseIndices, AccessorSparseValues
names=g.meshes[0].extras['targetNames']; XC=0.034; HINGE=np.array([0.0,1.51,0.02]); TH=0.20
def sstep(a_,b_,v): t=np.clip((v-a_)/(b_-a_),0,1); return t*t*(3-2*t)
def seam_y(x_): q=np.clip((np.abs(x_)-0.020)/0.014,0,1); return 1.4441+0.0030*q*q
def rot(P_,w_):
    r=P_-HINGE; th=TH*w_; c,s=np.cos(th),np.sin(th)
    out=np.zeros_like(P_); out[:,1]=HINGE[1]+r[:,1]*c+r[:,2]*s-P_[:,1]; out[:,2]=HINGE[2]-r[:,1]*s+r[:,2]*c-P_[:,2]; return out
ti=names.index('jawOpen'); jacc=p.targets[ti]['POSITION']; Dold=glbio.read(g,jacc).astype(np.float64)
P0=pos.astype(np.float64); ryz=np.linalg.norm((P0-HINGE)[:,1:],axis=1)
wold=2*np.arcsin(np.clip(np.linalg.norm(Dold[:,1:],axis=1)/np.maximum(2*ryz,1e-9),0,1))/TH
X,Y,Z=P0.T; ax_=np.abs(X); dd=Y-seam_y(X)
env=(1-sstep(0.026,0.078,ax_))*sstep(1.29,1.38,Y)*(1-sstep(-0.03,0.05,Z))
vold=np.clip(wold/np.maximum(env,1e-6),0,1)
alm=np.clip(1-(ax_/XC)**2,0,1)**0.85
gg=np.exp(-(dd/0.012)**2)*(Z<-0.03)
vt=vold*(0.5+0.5*alm)+(1-vold)*0.5*(1-alm)
vnew=vold+(vt-vold)*gg
uvo=glbio.read(g,p.attributes.TEXCOORD_0)
rigid=np.zeros(len(P0),bool)
for k in (0,2):  # teeth, tongue keep their rigid jaw motion
    rigid|=(np.abs(uvo-np.array([[0.6748047,0.83691406],[0,0],[0.33496094,0.5966797]][k])).max(1)<1e-6)
wnew=np.where(rigid,wold,vnew*env)
Dnew=rot(P0,wnew)
pinch=np.exp(-((ax_-XC)/0.012)**2)*gg*(~rigid)
Dnew[:,0]+=-np.sign(X)*0.0028*pinch
def put_sparse(acc_i,Dm):
    m=np.abs(Dm).sum(1)>1e-7; idx=np.where(m)[0].astype(np.uint32); val=Dm[m].astype(np.float32)
    g._extra.append((acc_i,idx,val))
g._extra=[]
put_sparse(jacc,Dnew)
print('jawOpen verts moved old/new',(np.abs(Dold).sum(1)>1e-7).sum(),(np.abs(Dnew).sum(1)>1e-7).sum(),'max mm',np.abs(Dnew).max()*1000)
# keep the lip-slit copies apart when the file is packed: give copies with different motion a hair-different UV
nuv=I['newuv'].copy()
key=np.concatenate([np.round(P0,6),nuv.astype(np.float64)],1)
_,ginv,gcnt=np.unique(key,axis=0,return_inverse=True,return_counts=True); ginv=ginv.ravel()
dupv=np.where(gcnt[ginv]>1)[0]; order=dupv[np.argsort(ginv[dupv],kind='stable')]
fixed_n=0; i0=0
while i0<len(order):
    j0=i0
    while j0<len(order) and ginv[order[j0]]==ginv[order[i0]]: j0+=1
    mem=order[i0:j0]
    if np.abs(Dnew[mem]-Dnew[mem[0]]).max()>1e-6:
        for k_,v_ in enumerate(mem[1:],1): nuv[v_,0]+=k_*1.5e-4; fixed_n+=1
    i0=j0
print('lip-slit copies separated',fixed_n)
write(p.attributes.TEXCOORD_0,nuv.astype(np.float32))
# mouthClose follows the new jaw shape
ci=names.index('mouthClose'); cacc=p.targets[ci]['POSITION']; Cold=glbio.read(g,cacc).astype(np.float64)
nj=np.linalg.norm(Dold,axis=1); lipw=np.where(nj>1e-6,np.linalg.norm(Cold,axis=1)/np.maximum(0.9*nj,1e-9),np.exp(-(dd/0.008)**2)*(ax_<XC+0.004)*(Z<-0.09))
put_sparse(cacc,-0.9*Dnew*np.clip(lipw,0,1)[:,None])
# images
def jpg(path,size=None,q=90):
    im=Image.open(path).convert('RGB')
    if size: im=im.resize((size,size),Image.LANCZOS)
    b=io.BytesIO(); im.save(b,'JPEG',quality=q,subsampling=0); return b.getvalue()
def paint(path,out,scale,cols):
    im=np.asarray(Image.open(path).convert('RGB')).copy()
    for (r0,c0,hh,ww),fn in zip(I['boxes'],cols):
        r0,c0,hh,ww=[int(v_*scale) for v_ in (r0,c0,hh,ww)]; pad=max(1,int(6*scale))
        t=np.clip((np.arange(c0-pad,c0+ww+pad)-(c0+12*scale))/max(1,(ww-24*scale)),0,1)
        ra=max(0,r0-pad); ca=max(0,c0-pad); t=t[ca-(c0-pad):]
        im[ra:r0+hh+pad,ca:c0+ww+pad]=fn(t)[None,:im.shape[1]-ca,:]
    Image.fromarray(im).save(out)
cav=lambda t:(np.array([150,52,58])[None,:]*(1-t[:,None])**1.3+np.array([20,4,8])[None,:]*(1-(1-t[:,None])**1.3)).astype(np.uint8)
flat=lambda c:(lambda t:np.tile(np.array(c,np.uint8),(len(t),1)))
leath=lambda t:np.where((t<0.16)[:,None],np.array([150,152,160]),np.array([35,35,39])).astype(np.uint8)
paint('bakeC.png','bakeC2.png',1.0,[cav,flat((246,243,236)),flat((214,104,112)),leath])
paint('bakeORM.png','bakeORM2.png',0.25,[flat((255,225,0)),flat((255,64,0)),flat((255,120,0)),flat((255,92,0))])
imgC=jpg('bakeC2.png',q=90); imgO=jpg('bakeORM2.png',q=92)
# rebuild blob view by view
views=g.bufferViews; img_bv=g.images[0].bufferView
order=sorted(range(len(views)),key=lambda i:views[i].byteOffset or 0)
new=bytearray()
for i in order:
    bv=views[i]; data=imgC if i==img_bv else bytes(blob[(bv.byteOffset or 0):(bv.byteOffset or 0)+bv.byteLength])
    while len(new)%4: new.append(0)
    bv.byteOffset=len(new); bv.byteLength=len(data); new+=data
while len(new)%4: new.append(0)
for acc_i,idx,val in g._extra:
    while len(new)%4: new.append(0)
    views.append(BufferView(buffer=0,byteOffset=len(new),byteLength=idx.nbytes)); new+=idx.tobytes(); bi=len(views)-1
    while len(new)%4: new.append(0)
    views.append(BufferView(buffer=0,byteOffset=len(new),byteLength=val.nbytes)); new+=val.tobytes(); bvv=len(views)-1
    ac=g.accessors[acc_i]; ac.bufferView=None; ac.byteOffset=None
    ac.sparse=Sparse(count=len(idx),indices=AccessorSparseIndices(bufferView=bi,componentType=5125),values=AccessorSparseValues(bufferView=bvv))
    ac.min=val.min(0).clip(max=0).tolist(); ac.max=val.max(0).clip(min=0).tolist()
# ---------------- jacket shell as its own skinned mesh ----------------
from pygltflib import Mesh, Primitive, Attributes, Node
Sh=np.load('shell.npz'); ns_=len(Sh['Q'])
cv=lambda A_:np.stack([A_[:,0],A_[:,2],-A_[:,1]],1).astype(np.float32)
sp_=np.concatenate([cv(Sh['Q']),cv(Sh['Qin'])]); sn_=np.concatenate([cv(Sh['N']),-cv(Sh['N'])])
r0,c0,hh,ww=[float(v_) for v_ in I['boxes'][3]]
tt=np.clip(Sh['dedge']/0.035,0,1); uo=np.stack([(c0+12+tt*(ww-24))/4096,np.full(ns_,(r0+hh/2)/4096)],1)
ui=uo.copy(); ui[:,0]=(c0+ww-14)/4096
suv=np.concatenate([uo,ui]).astype(np.float32)
sj=np.concatenate([J0[Sh['src']]]*2).astype(np.uint8); sw=np.concatenate([W0[Sh['src']]]*2).astype(np.float32)
Tq=Sh['T'].astype(np.uint32); Tg=Tq  # winding: blender->gltf axis swap is a rotation, keeps handedness
sidx=np.concatenate([Tg,Tg[:,[0,2,1]]+ns_]).astype(np.uint32).ravel()
def add_acc(arr,comp,typ,target=None,mm=False):
    global new
    while len(new)%4: new.append(0)
    views.append(BufferView(buffer=0,byteOffset=len(new),byteLength=arr.nbytes,target=target)); new+=arr.tobytes()
    ac=Accessor(bufferView=len(views)-1,componentType=comp,count=len(arr) if arr.ndim>1 else arr.size,type=typ)
    if mm: ac.min=arr.min(0).tolist(); ac.max=arr.max(0).tolist()
    g.accessors.append(ac); return len(g.accessors)-1
att=Attributes(POSITION=add_acc(sp_,5126,'VEC3',34962,True),NORMAL=add_acc(sn_,5126,'VEC3',34962),TEXCOORD_0=add_acc(suv,5126,'VEC2',34962),JOINTS_0=add_acc(sj,5121,'VEC4',34962),WEIGHTS_0=add_acc(sw,5126,'VEC4',34962))
g.meshes.append(Mesh(name='Jacket',primitives=[Primitive(attributes=att,indices=add_acc(sidx,5125,'SCALAR',34963),material=0)]))
gi=[i_ for i_,n_ in enumerate(g.nodes) if n_.mesh==0][0]
g.nodes.append(Node(name='Jacket',mesh=len(g.meshes)-1,skin=g.nodes[gi].skin))
for n_ in g.nodes:
    if n_.children and gi in n_.children: n_.children.append(len(g.nodes)-1)
print('jacket mesh added: verts',len(sp_),'tris',len(sidx)//3)
while len(new)%4: new.append(0)
del g._extra
views.append(BufferView(buffer=0,byteOffset=len(new),byteLength=len(imgO))); new+=imgO
while len(new)%4: new.append(0)
g.images.append(GImage(mimeType='image/jpeg',bufferView=len(views)-1,name='Girl_ORM'))
t0=g.textures[g.materials[0].pbrMetallicRoughness.baseColorTexture.index]
g.textures.append(Texture(source=len(g.images)-1,sampler=t0.sampler))
pbr=g.materials[0].pbrMetallicRoughness; pbr.metallicRoughnessTexture=TextureInfo(index=len(g.textures)-1); pbr.roughnessFactor=1.0; pbr.metallicFactor=1.0  # ORM blue channel is 0 everywhere = non-metal
g.buffers[0].byteLength=len(new); g.set_binary_blob(bytes(new))
g.save('out/Girl_character_mixamo.glb')
print('saved',len(new)/1e6,'MB', 'imgC',len(imgC)/1e6)
