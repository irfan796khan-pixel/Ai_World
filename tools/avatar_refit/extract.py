import bpy,sys,numpy as np
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath='/home/claude/irfan796khan-pixel/ai_world/Girl_character_mixamo.glb')
o=bpy.data.objects['Girl']; m=o.data
nv=len(m.vertices); nl=len(m.loops); nf=len(m.polygons)
co=np.empty(nv*3,np.float32); m.shape_keys.key_blocks[0].data.foreach_get('co',co); co=co.reshape(-1,3)
lv=np.empty(nl,np.int32); m.loops.foreach_get('vertex_index',lv)
uv=np.empty(nl*2,np.float32); m.uv_layers[0].data.foreach_get('uv',uv); uv=uv.reshape(-1,2)
ls=np.empty(nf,np.int32); m.polygons.foreach_get('loop_total',ls); print('tri only',(ls==3).all())
img=bpy.data.materials['Girl_Material'].node_tree.nodes
img=[n.image for n in img if n.type=='TEX_IMAGE'][0]
W,H=img.size; px=np.empty(W*H*4,np.float32); img.pixels.foreach_get(px); px=px.reshape(H,W,4)
print('colorspace',img.colorspace_settings.name, 'alpha range',px[...,3].min(),px[...,3].max())
x=np.clip((uv[:,0]*W).astype(int),0,W-1); y=np.clip((uv[:,1]*H).astype(int),0,H-1)
lc=px[y,x,:3]
vc=np.zeros((nv,3),np.float64); cnt=np.zeros(nv); np.add.at(vc,lv,lc); np.add.at(cnt,lv,1); vc/=np.maximum(cnt,1)[:,None]
print('names',[k.name for k in m.shape_keys.key_blocks])
print('vgroups',[g.name for g in o.vertex_groups][:70])
np.savez('girl.npz',co=co,lv=lv,uv=uv,vc=vc.astype(np.float32))
np.save('tex.npy',(px[...,:3]*255+0.5).astype(np.uint8))
print('bbox',co.min(0),co.max(0))
