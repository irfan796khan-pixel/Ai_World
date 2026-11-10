import bpy,numpy as np,time
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath='/home/claude/irfan796khan-pixel/ai_world/Girl_character_mixamo.glb')
F=np.load('final.npz'); o=bpy.data.objects['Girl']; m=o.data; nv=len(m.vertices)
for ob in list(bpy.data.objects):
    if ob.name=='Icosphere': bpy.data.objects.remove(ob)
def fattr(name,arr):
    a=m.attributes.new(name,'FLOAT','POINT'); a.data.foreach_set('value',arr.astype(np.float32))
def cattr(name,rgb):
    a=m.attributes.new(name,'FLOAT_COLOR','POINT'); d=np.ones((nv,4),np.float32); d[:,:3]=rgb; a.data.foreach_set('color',d.ravel())
cattr('ncol',F['col']); cattr('jcol',F['jcol']); fattr('mfz',F['mfz']); fattr('mrip',F['mrip']); fattr('mh',F['mh']); fattr('w',F['w']); fattr('mj',F['mj']); fattr('md',F['md'])
orm=np.stack([np.ones(nv),F['rough'],F['metal']],1); cattr('orm',orm)
mat=bpy.data.materials['Girl_Material']; nt=mat.node_tree; N=nt.nodes; Lk=nt.links
tex=[n for n in N if n.type=='TEX_IMAGE'][0]
out=[n for n in N if n.type=='OUTPUT_MATERIAL'][0]
def A(name,typ='ShaderNodeAttribute'):
    n=N.new(typ); n.attribute_name=name; return n
bw=N.new('ShaderNodeRGBToBW'); Lk.new(tex.outputs['Color'],bw.inputs['Color'])
# jeans: lum*0.62+0.010, tinted
jm=N.new('ShaderNodeMath'); jm.operation='MULTIPLY_ADD'; Lk.new(bw.outputs['Val'],jm.inputs[0]); jm.inputs[1].default_value=0.62; jm.inputs[2].default_value=0.010
jc=N.new('ShaderNodeCombineColor'); 
for i,t in enumerate((0.96,0.98,1.06)):
    mm=N.new('ShaderNodeMath'); mm.operation='MULTIPLY'; Lk.new(jm.outputs[0],mm.inputs[0]); mm.inputs[1].default_value=t; Lk.new(mm.outputs[0],jc.inputs[i])
dm=N.new('ShaderNodeMath'); dm.operation='MULTIPLY'; dm.use_clamp=True; Lk.new(bw.outputs['Val'],dm.inputs[0]); dm.inputs[1].default_value=1.10
dc=N.new('ShaderNodeCombineColor'); [Lk.new(dm.outputs[0],dc.inputs[i]) for i in range(3)]
def mix(a,b,fac):
    n=N.new('ShaderNodeMix'); n.data_type='RGBA'; n.clamp_factor=True; Lk.new(fac,n.inputs['Factor']); Lk.new(a,n.inputs['A']); Lk.new(b,n.inputs['B']); return n.outputs['Result']
c1=mix(tex.outputs['Color'],jc.outputs['Color'],A('mj').outputs['Fac'])
c2=mix(c1,dc.outputs['Color'],A('md').outputs['Fac'])
hsc=N.new('ShaderNodeMath'); hsc.operation='DIVIDE'; hsc.inputs[1].default_value=0.023
hcl=N.new('ShaderNodeClamp'); hcl.inputs['Min'].default_value=0.007; hcl.inputs['Max'].default_value=0.052; Lk.new(bw.outputs['Val'],hcl.inputs['Value']); Lk.new(hcl.outputs[0],hsc.inputs[0])
hc=N.new('ShaderNodeCombineColor')
for i,t in enumerate((0.066,0.0165,0.013)):
    mm=N.new('ShaderNodeMath'); mm.operation='MULTIPLY'; Lk.new(hsc.outputs[0],mm.inputs[0]); mm.inputs[1].default_value=t; Lk.new(mm.outputs[0],hc.inputs[i])
c2=mix(c2,hc.outputs['Color'],A('mh').outputs['Fac'])
c3=mix(c2,A('ncol').outputs['Color'],A('w').outputs['Fac'])
def M(op,a,b=None,c=None,clamp=False):
    n=N.new('ShaderNodeMath'); n.operation=op; n.use_clamp=clamp
    for i,v in enumerate((a,b,c)):
        if v is None: continue
        if isinstance(v,(int,float)): n.inputs[i].default_value=v
        else: Lk.new(v,n.inputs[i])
    return n.outputs[0]
geo=N.new('ShaderNodeNewGeometry'); sep=N.new('ShaderNodeSeparateXYZ'); Lk.new(geo.outputs['Position'],sep.inputs[0])
X,Z=sep.outputs['X'],sep.outputs['Z']; ax=M('ABSOLUTE',X)
ha=M('MULTIPLY_ADD',M('DIVIDE',M('SUBTRACT',Z,1.0),0.30,clamp=True),0.034,0.050)
hb=M('MULTIPLY_ADD',M('SUBTRACT',Z,1.285),1.4,0.048)
hwn=M('MAXIMUM',ha,hb)
openT=M('LESS_THAN',ax,hwn)
zipT=M('MULTIPLY',M('LESS_THAN',ax,-1.0),1.0)
silver=N.new('ShaderNodeRGB'); silver.outputs[0].default_value=(0.50,0.51,0.55,1)
jz=mix(A('jcol').outputs['Color'],silver.outputs[0],zipT)
zonec=mix(jz,dc.outputs['Color'],openT)
c4=mix(c3,zonec,A('mfz').outputs['Fac'])
# rips: 4 ellipses on the front of the jeans, horizontal threads
rm=None
for (cx,cz,rx,rz) in ((0.092,0.475,0.036,0.013),(-0.095,0.655,0.034,0.012),(0.105,0.625,0.022,0.009),(-0.088,0.44,0.026,0.010)):
    e=M('ADD',M('POWER',M('DIVIDE',M('SUBTRACT',X,cx),rx),2),M('POWER',M('DIVIDE',M('SUBTRACT',Z,cz),rz),2))
    wob=M('MULTIPLY_ADD',M('SINE',M('MULTIPLY',X,900)),0.18,1.0)   # frayed outline
    inside=M('LESS_THAN',e,wob); rm=inside if rm is None else M('MAXIMUM',rm,inside)
rm=M('MULTIPLY',rm,M('GREATER_THAN',A('mrip').outputs['Fac'],0.5))
thread=M('GREATER_THAN',M('SINE',M('MULTIPLY',Z,2*3.14159265/0.0042)),0.0)
thr=N.new('ShaderNodeRGB'); thr.outputs[0].default_value=(0.60,0.60,0.62,1)
gap=N.new('ShaderNodeRGB'); gap.outputs[0].default_value=(0.035,0.035,0.04,1)
ripc=mix(gap.outputs[0],thr.outputs[0],thread)
c3=mix(c4,ripc,rm)
em=N.new('ShaderNodeEmission'); Lk.new(c3,em.inputs['Color']); Lk.new(em.outputs[0],out.inputs['Surface'])
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=1; sc.cycles.use_denoising=False
sc.render.bake.margin=8; sc.render.bake.use_clear=True
[ob.select_set(False) for ob in bpy.data.objects]
bpy.context.view_layer.objects.active=o; o.select_set(True)
def bake(name,size,cs,src):
    img=bpy.data.images.new(name,size,size,alpha=False); img.colorspace_settings.name=cs
    bn=N.new('ShaderNodeTexImage'); bn.image=img
    for n in N: n.select=False
    bn.select=True; N.active=bn
    Lk.new(src,em.inputs['Color'])
    t=time.time(); bpy.ops.object.bake(type='EMIT'); print('baked',name,time.time()-t)
    img.filepath_raw='/tmp/claude-0/-home-claude/9e1bbd82-01ef-5340-891e-5e3a4c1e3744/scratchpad/bl/'+name+'.png'; img.file_format='PNG'; img.save()
    N.remove(bn)
bake('bakeC',4096,'sRGB',c3)
bake('bakeORM',1024,'Non-Color',A('orm').outputs['Color'])
