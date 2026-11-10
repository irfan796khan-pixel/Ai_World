import bpy,numpy as np
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath='/home/claude/irfan796khan-pixel/ai_world/Girl_character_mixamo.glb')
o=bpy.data.objects['Girl']; m=o.data; nv=len(m.vertices)
dom=np.zeros(nv,np.int16); 
for v in m.vertices:
    g=v.groups
    if len(g):
        b=max(g,key=lambda e:e.weight); dom[v.index]=b.group
np.save('dom.npy',dom)
open('groups.txt','w').write('\n'.join(g.name for g in o.vertex_groups))
no=np.empty(nv*3,np.float32); m.vertices.foreach_get('normal',no); np.save('vnorm.npy',no.reshape(-1,3))
print('ok')
