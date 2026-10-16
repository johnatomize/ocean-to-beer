"""Build the complete, self-contained Ocean / Lager Blender animation.

Run with Blender 4.5+: blender -b --python scripts/build_scene.py
No downloaded images, simulation caches, fonts, or add-ons are required.
"""
import bpy
import math
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENE_FILE = ROOT / 'ocean_to_beer.blend'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for data in bpy.data.materials:
    bpy.data.materials.remove(data)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.045
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = 8
scene.cycles.transmission_bounces = 6
scene.cycles.glossy_bounces = 4
scene.cycles.volume_bounces = 1
scene.cycles.volume_step_rate = 2.0
scene.cycles.volume_max_steps = 128
scene.cycles.sample_clamp_indirect = 3.0
scene.render.use_persistent_data = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, 300
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.render.filepath = '//renders/frames/frame_'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = -0.1

prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'METAL'
    scene.cycles.device = 'GPU'
except Exception:
    scene.cycles.device = 'CPU'

def node(tree, kind, name, x=0, y=0):
    n = tree.nodes.new(kind)
    n.name = name
    n.label = name
    n.location = (x,y)
    return n

def link(tree, output, target):
    tree.links.new(output,target)

def mathn(tree, operation, a, b=None, name=None):
    n = node(tree,'ShaderNodeMath',name or operation)
    n.operation=operation
    for i, v in enumerate((a,b)):
        if v is None: continue
        if isinstance(v,(float,int)): n.inputs[i].default_value=v
        else: link(tree,v,n.inputs[i])
    return n.outputs[0]

def ramp(tree, value, lo, hi, name):
    n=node(tree,'ShaderNodeMapRange',name)
    n.interpolation_type='SMOOTHERSTEP'
    n.clamp=True
    link(tree,value,n.inputs['Value'])
    n.inputs['From Min'].default_value=lo
    n.inputs['From Max'].default_value=hi
    return n.outputs['Result']

def mixcolor(tree, factor, a, b, name):
    n=node(tree,'ShaderNodeMixRGB',name)
    link(tree,factor,n.inputs[0])
    for i,v in ((1,a),(2,b)):
        if isinstance(v,tuple): n.inputs[i].default_value=v
        else: link(tree,v,n.inputs[i])
    return n.outputs[0]

def noise(tree, vector, scale, detail, roughness, name):
    n=node(tree,'ShaderNodeTexNoise',name)
    n.noise_dimensions='3D'
    link(tree,vector,n.inputs['Vector'])
    n.inputs['Scale'].default_value=scale
    n.inputs['Detail'].default_value=detail
    n.inputs['Roughness'].default_value=roughness
    return n

def linear_keys(idblock):
    if idblock.animation_data and idblock.animation_data.action:
        for fc in idblock.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation='LINEAR'

# A common world-space reaction front is used by surface, foam and volume.
group=bpy.data.node_groups.new('LAGER • advected reaction front','ShaderNodeTree')
group.interface.new_socket(name='Beer',in_out='OUTPUT',socket_type='NodeSocketFloat')
group.interface.new_socket(name='Flow',in_out='OUTPUT',socket_type='NodeSocketVector')
gout=node(group,'NodeGroupOutput','Coherent field',1000,0)
geom=node(group,'ShaderNodeNewGeometry','World coordinates',-1000,0)
flow=node(group,'ShaderNodeVectorMath','Slow surface current',-800,0)
flow.operation='ADD'
link(group,geom.outputs['Position'],flow.inputs[0])
flow.inputs[1].default_value=(0,0,0)
flow.inputs[1].keyframe_insert('default_value',frame=1)
flow.inputs[1].default_value=(-0.8,-0.45,0)
flow.inputs[1].keyframe_insert('default_value',frame=300)
linear_keys(group)
flatten=node(group,'ShaderNodeVectorMath','Horizontal transport',-600,0)
flatten.operation='MULTIPLY'
flatten.inputs[1].default_value=(1,1,0)
link(group,flow.outputs[0],flatten.inputs[0])
front_noise=noise(group,flatten.outputs[0],0.24,3.0,0.65,'Turbulent front')
front_detail=noise(group,flatten.outputs[0],0.85,2.0,0.65,'Fine eddies')
separate=node(group,'ShaderNodeSeparateXYZ','Diagonal travel')
link(group,flatten.outputs[0],separate.inputs[0])
field=mathn(group,'ADD',mathn(group,'MULTIPLY',separate.outputs['X'],0.028),mathn(group,'MULTIPLY',separate.outputs['Y'],0.026))
field=mathn(group,'ADD',field,mathn(group,'MULTIPLY',front_noise.outputs['Fac'],0.54))
field=mathn(group,'ADD',field,mathn(group,'MULTIPLY',front_detail.outputs['Fac'],0.13))
field=mathn(group,'ADD',field,0.16)
progress=node(group,'ShaderNodeValue','Transformation • 3–7 seconds')
for frame,value in [(1,-0.2),(91,-0.2),(211,1.2),(300,1.2)]:
    progress.outputs[0].default_value=value
    progress.outputs[0].keyframe_insert('default_value',frame=frame)
linear_keys(group)
front=mathn(group,'SUBTRACT',progress.outputs[0],field)
beer=ramp(group,front,-0.065,0.065,'Soft mixing boundary')
link(group,beer,gout.inputs['Beer'])
link(group,flow.outputs[0],gout.inputs['Flow'])

# FFT deep-water spectrum: a moving, genuinely displaced 3D surface.
mesh=bpy.data.meshes.new('Ocean seed')
ocean=bpy.data.objects.new('OCEAN • continuous spectral simulation',mesh)
bpy.context.collection.objects.link(ocean)
bpy.context.view_layer.objects.active=ocean
ocean.select_set(True)
sim=ocean.modifiers.new('Spectral ocean • directional swell & cross waves','OCEAN')
sim.geometry_mode='GENERATE'
sim.resolution=26
sim.viewport_resolution=18
sim.spatial_size=42
sim.size=1
sim.spectrum='PHILLIPS'
sim.wind_velocity=8
sim.wave_scale=1.35
sim.wave_scale_min=0.015
sim.choppiness=0.8
sim.wave_alignment=0.12
sim.wave_direction=math.radians(34)
sim.damping=0.35
sim.depth=80
sim.random_seed=21
sim.use_normals=True
sim.use_foam=True
sim.foam_layer_name='crest_foam'
sim.foam_coverage=0.18
sim.time=1.6
sim.keyframe_insert('time',frame=1)
sim.time=8.1
sim.keyframe_insert('time',frame=300)
linear_keys(ocean)
cross=ocean.modifiers.new('Short crossing wind waves','OCEAN')
cross.geometry_mode='DISPLACE'
cross.resolution=18
cross.viewport_resolution=14
cross.spatial_size=9
cross.wind_velocity=3.5
cross.wave_scale=0.25
cross.wave_scale_min=0.012
cross.choppiness=0.45
cross.wave_alignment=0.4
cross.wave_direction=math.radians(-42)
cross.random_seed=45
cross.time=2.2
cross.keyframe_insert('time',frame=1)
cross.time=8.7
cross.keyframe_insert('time',frame=300)
linear_keys(ocean)

mat=bpy.data.materials.new('SEA → LAGER | optical liquid + crest foam')
mat.use_nodes=True
t=mat.node_tree
t.nodes.clear()
out=node(t,'ShaderNodeOutputMaterial','Liquid output',1400,100)
fieldnode=node(t,'ShaderNodeGroup','Unified transformation',-1400,600)
fieldnode.node_tree=group
beer=fieldnode.outputs['Beer']
coords=fieldnode.outputs['Flow']

stretch=node(t,'ShaderNodeVectorMath','Wind-stretched capillary ripples')
stretch.operation='MULTIPLY'
stretch.inputs[1].default_value=(0.8,2.7,0.7)
link(t,coords,stretch.inputs[0])
fine=noise(t,stretch.outputs[0],2.0,1.5,0.45,'Capillary turbulence')
medium=noise(t,coords,1.2,1.5,0.5,'Small crossed ripples')
bump1=node(t,'ShaderNodeBump','Capillary normals')
bump1.inputs['Strength'].default_value=0.25
bump1.inputs['Distance'].default_value=0.035
link(t,fine.outputs['Fac'],bump1.inputs['Height'])
bump2=node(t,'ShaderNodeBump','Secondary wavelets')
bump2.inputs['Strength'].default_value=0.4
bump2.inputs['Distance'].default_value=0.14
link(t,medium.outputs['Fac'],bump2.inputs['Height'])
link(t,bump1.outputs['Normal'],bump2.inputs['Normal'])

# Variable-radius gas pockets. The dome height creates curved reflections,
# and each Voronoi cell has a different radius rather than a uniform dot grid.
voro=node(t,'ShaderNodeTexVoronoi','Surface carbonation • irregular gas cells')
voro.voronoi_dimensions='3D'
voro.feature='F1'
voro.distance='EUCLIDEAN'
voro.inputs['Scale'].default_value=17
link(t,coords,voro.inputs['Vector'])
vcolor=node(t,'ShaderNodeRGBToBW','Bubble radius variation')
link(t,voro.outputs['Color'],vcolor.inputs[0])
radius=mathn(t,'ADD',mathn(t,'MULTIPLY',vcolor.outputs[0],0.15),0.11)
distance=mathn(t,'DIVIDE',voro.outputs['Distance'],radius)
dome=mathn(t,'MAXIMUM',mathn(t,'SUBTRACT',1.0,mathn(t,'MULTIPLY',distance,distance)),0.0)
dome=mathn(t,'SQRT',dome)
bubbles=mathn(t,'MULTIPLY',dome,beer)
gasbump=node(t,'ShaderNodeBump','Curved gas menisci')
gasbump.inputs['Strength'].default_value=0.55
gasbump.inputs['Distance'].default_value=0.026
link(t,bubbles,gasbump.inputs['Height'])
link(t,bump2.outputs['Normal'],gasbump.inputs['Normal'])

liquid=node(t,'ShaderNodeBsdfPrincipled','Refractive liquid',700,350)
liquid.inputs['IOR'].default_value=1.333
liquid.inputs['Roughness'].default_value=0.035
liquid.inputs['Transmission Weight'].default_value=1.0
base=mixcolor(t,beer,(0.84,0.96,0.98,1),(1.0,0.97,0.84,1),'Water / lager surface tint')
link(t,base,liquid.inputs['Base Color'])
# The resolved spectral mesh supplies the liquid normals. Keeping the fine
# artistic normal stack disconnected avoids noisy subpixel reflections.

# Breaking-wave foam is derived from the simulation's compression field.
attr=node(t,'ShaderNodeAttribute','Wave compression / foam')
attr.attribute_name='crest_foam'
foamnoise=noise(t,coords,3.8,3.0,0.72,'Torn foam edges')
foamnoise2=noise(t,coords,0.65,3.0,0.6,'Large foam islands')
foam_detail=mathn(t,'MULTIPLY',foamnoise.outputs['Fac'],0.06)
foamfield=mathn(t,'SUBTRACT',attr.outputs['Fac'],foam_detail)
foamfield=mathn(t,'ADD',foamfield,mathn(t,'MULTIPLY',beer,0.025))
foammask=ramp(t,foamfield,0.055,0.19,'Breaking wave coverage')
# Beer foam gathers in additional small rafts in slow currents.
raft=ramp(t,foamnoise2.outputs['Fac'],0.59,0.69,'Beer foam rafts')
raft=mathn(t,'MULTIPLY',raft,beer)
foammask=mathn(t,'MAXIMUM',foammask,raft)

foamv=node(t,'ShaderNodeTexVoronoi','Foam microcells')
foamv.inputs['Scale'].default_value=28
link(t,coords,foamv.inputs['Vector'])
foamheight=mathn(t,'SUBTRACT',1.0,foamv.outputs['Distance'])
fb=node(t,'ShaderNodeBump','Aerated cream microstructure')
fb.inputs['Strength'].default_value=0.3
fb.inputs['Distance'].default_value=0.012
link(t,foamheight,fb.inputs['Height'])
foam=node(t,'ShaderNodeBsdfPrincipled','Dense creamy foam',700,-50)
foam.inputs['Roughness'].default_value=0.5
foam.inputs['Subsurface Weight'].default_value=0.065
foam.inputs['Subsurface Radius'].default_value=(0.08,0.045,0.02)
foam.inputs['IOR'].default_value=1.34
cream=mixcolor(t,beer,(0.45,0.55,0.60,1),(0.42,0.35,0.23,1),'Whitecaps → warm cream')
link(t,cream,foam.inputs['Base Color'])
link(t,fb.outputs['Normal'],foam.inputs['Normal'])
surface=node(t,'ShaderNodeMixShader','Crest-bound surface foam',1100,300)
link(t,foammask,surface.inputs[0])
link(t,liquid.outputs[0],surface.inputs[1])
link(t,foam.outputs[0],surface.inputs[2])
link(t,surface.outputs[0],out.inputs['Surface'])

absorb=node(t,'ShaderNodeVolumeAbsorption','Spectral liquid absorption',700,-500)
absorb.inputs['Density'].default_value=0.24
ac=mixcolor(t,beer,(0.01,0.4,0.48,1),(0.88,0.69,0.18,1),'Blue-green / amber absorption')
link(t,ac,absorb.inputs['Color'])
scatter=node(t,'ShaderNodeVolumeScatter','Light inside the liquid',700,-700)
scatter.inputs['Density'].default_value=0.0
scatter.inputs['Anisotropy'].default_value=0.32
sc=mixcolor(t,beer,(0.015,0.3,0.4,1),(0.94,0.74,0.15,1),'Optical scattering')
link(t,sc,scatter.inputs['Color'])
vol=node(t,'ShaderNodeAddShader','Participating liquid volume',1100,-500)
link(t,absorb.outputs[0],vol.inputs[0])
link(t,scatter.outputs[0],vol.inputs[1])
ocean.data.materials.append(mat)

# Keep the optical reservoir separate from the free surface. Extruding a
# choppy surface along its normals would create self-intersecting side walls.
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-3.5))
reservoir=bpy.context.object
reservoir.name='Optical reservoir • absorption below free surface'
reservoir.scale=(100,100,5.0)
vm=bpy.data.materials.new('Submerged spectral attenuation')
vm.use_nodes=True
vt=vm.node_tree
vt.nodes.clear()
vg=node(vt,'ShaderNodeGroup','Same world-space transformation')
vg.node_tree=group
va=node(vt,'ShaderNodeVolumeAbsorption','Amber and seawater attenuation')
va.inputs['Density'].default_value=0.24
vc=mixcolor(vt,vg.outputs['Beer'],(0.01,0.4,0.48,1),(0.88,0.69,0.18,1),'Optical absorption colors')
link(vt,vc,va.inputs['Color'])
vo=node(vt,'ShaderNodeOutputMaterial','Volume only')
link(vt,va.outputs[0],vo.inputs['Volume'])
reservoir.data.materials.append(vm)

# Explicit curved bubble shells ride the very same spectral displacement.
# A separate shell shader disappears ahead of the transformation front.
rng=random.Random(213)
vertices=[]
faces=[]
for i in range(2600):
    x=rng.uniform(-15,15)
    y=rng.uniform(-10,10)
    radius=rng.uniform(0.012,0.041)
    if rng.random()<0.07: radius*=1.8
    start=len(vertices)
    rings=5
    sides=10
    for r in range(rings+1):
        theta=math.pi*(r+0.01)/(rings+0.02)
        for j in range(sides):
            phi=2*math.pi*j/sides
            vertices.append((x+radius*math.sin(theta)*math.cos(phi),y+radius*math.sin(theta)*math.sin(phi),0.002+radius*0.72*math.cos(theta)))
    for r in range(rings):
        for j in range(sides):
            a=start+r*sides+j
            b=start+r*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
bm=bpy.data.meshes.new('2600 individual carbonation domes')
bm.from_pydata(vertices,[],faces)
bm.update()
bo=bpy.data.objects.new('CARBONATION • floating gas domes',bm)
bpy.context.collection.objects.link(bo)
for poly in bm.polygons: poly.use_smooth=True
for source in (sim,cross):
    m=bo.modifiers.new(source.name,'OCEAN')
    for prop in ('resolution','viewport_resolution','spatial_size','wind_velocity','wave_scale','wave_scale_min','choppiness','wave_alignment','wave_direction','damping','depth','random_seed','spectrum'):
        setattr(m,prop,getattr(source,prop))
    m.geometry_mode='DISPLACE'
    m.time=1.6 if source==sim else 2.2
    m.keyframe_insert('time',frame=1)
    m.time=8.1 if source==sim else 8.7
    m.keyframe_insert('time',frame=300)
linear_keys(bo)
bmat=bpy.data.materials.new('Thin lager bubble films')
bmat.use_nodes=True
bt=bmat.node_tree
bt.nodes.clear()
bgp=node(bt,'ShaderNodeGroup','Carbonation follows the beer front')
bgp.node_tree=group
bglass=node(bt,'ShaderNodeBsdfPrincipled','Curved transparent shell')
bglass.inputs['Base Color'].default_value=(0.95,0.83,0.50,1)
bglass.inputs['Transmission Weight'].default_value=0.78
bglass.inputs['Roughness'].default_value=0.055
bglass.inputs['IOR'].default_value=1.33
btransparent=node(bt,'ShaderNodeBsdfTransparent','No bubbles in seawater')
bmx=node(bt,'ShaderNodeMixShader','Bubbles emerge locally')
link(bt,bgp.outputs['Beer'],bmx.inputs[0])
link(bt,btransparent.outputs[0],bmx.inputs[1])
link(bt,bglass.outputs[0],bmx.inputs[2])
bout=node(bt,'ShaderNodeOutputMaterial','Gas shell output')
link(bt,bmx.outputs[0],bout.inputs['Surface'])
bm.materials.append(bmat)

# The below-surface irradiance reservoir has no visible texture or objects.
# It makes sunlight transmitted through the waves visible in a finite patch.
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-4.5))
floor=bpy.context.object
floor.name='Deep liquid irradiance • below view'
fm=bpy.data.materials.new('Deep optical return')
fm.use_nodes=True
ft=fm.node_tree
fprincipled=ft.nodes.get('Principled BSDF')
fgroup=node(ft,'ShaderNodeGroup','Same advected field')
fgroup.node_tree=group
depthnoise=noise(ft,fgroup.outputs['Flow'],0.55,2,0.55,'Underwater irradiance variation')
seacolor=mixcolor(ft,depthnoise.outputs['Fac'],(0.006,0.065,0.085,1),(0.015,0.21,0.25,1),'Ocean optical depths')
beercolor=mixcolor(ft,depthnoise.outputs['Fac'],(0.26,0.12,0.004,1),(0.85,0.58,0.035,1),'Amber and golden optical depths')
fcolor=mixcolor(ft,fgroup.outputs['Beer'],seacolor,beercolor,'Deep liquid color')
fe=node(ft,'ShaderNodeEmission','Integrated return from the deep liquid')
fe.inputs['Strength'].default_value=1.0
link(ft,fcolor,fe.inputs['Color'])
link(ft,fe.outputs[0],ft.nodes.get('Material Output').inputs['Surface'])
floor.data.materials.append(fm)

world=bpy.data.worlds.new('Natural daylight • high soft sun')
world.use_nodes=True
scene.world=world
w=world.node_tree
w.nodes.clear()
wo=node(w,'ShaderNodeOutputWorld','Daylight output')
bg=node(w,'ShaderNodeBackground','Sky illumination')
bg.inputs['Strength'].default_value=0.65
sky=node(w,'ShaderNodeTexSky','Atmospheric sky')
sky.sky_type='NISHITA'
sky.sun_elevation=math.radians(75)
sky.sun_rotation=math.radians(135)
sky.sun_size=math.radians(0.8)
sky.sun_intensity=0.7
sky.air_density=1.0
sky.dust_density=0.6
sky.ozone_density=1.0
wc=node(w,'ShaderNodeTexCoord','Sky direction')
cloud=noise(w,wc.outputs['Normal'],3.2,3,0.65,'Soft broken clouds')
cloudmask=ramp(w,cloud.outputs['Fac'],0.35,0.65,'Cloud luminance contrast')
cloudcolor=mixcolor(w,cloudmask,(0.08,0.13,0.21,1),(1.0,1.0,1.0,1),'Directional sky variation')
skymix=node(w,'ShaderNodeMixRGB','Cloud-filtered daylight')
skymix.blend_type='MULTIPLY'
skymix.inputs[0].default_value=0.85
link(w,sky.outputs[0],skymix.inputs[1])
link(w,cloudcolor,skymix.inputs[2])
link(w,sky.outputs[0],bg.inputs[0])
link(w,bg.outputs[0],wo.inputs['Surface'])

ld=bpy.data.lights.new('Large soft sky reflection','AREA')
light=bpy.data.objects.new('Large soft sky reflection',ld)
bpy.context.collection.objects.link(light)
light.location=(-6,5,12)
light.rotation_euler=(0.24,-0.35,-0.2)
ld.energy=0
ld.shape='DISK'
ld.size=9
ld.color=(1.0,0.94,0.82)

cd=bpy.data.cameras.new('Locked nadir camera')
camera=bpy.data.objects.new('CAMERA • 90° overhead • locked',cd)
bpy.context.collection.objects.link(camera)
camera.location=(0,0,24)
camera.rotation_euler=(0,0,0)
cd.type='ORTHO'
cd.ortho_scale=24
cd.lens=50
scene.camera=camera
camera.lock_location=(True,True,True)
camera.lock_rotation=(True,True,True)
camera.lock_scale=(True,True,True)

scene.timeline_markers.new('SEA | natural blue-green ocean',frame=1)
scene.timeline_markers.new('TRANSFORM | organic front begins',frame=91)
scene.timeline_markers.new('LAGER | full golden ocean',frame=211)
scene.timeline_markers.new('END | 10 seconds',frame=300)
scene['project']='Ocean to Beer — procedural cinematic liquid study'
scene['duration_seconds']=10
scene['notes']='A fixed nadir camera; FFT displaced ocean; coherent world-space conversion; refractive liquid; procedural foam and gas menisci. No static imagery.'

# Leave a useful camera view when the project is opened interactively.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
scene.frame_set(1)
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.type == 'OCEAN':
            modifier.filepath = '//renders/ocean_cache/'
bpy.ops.wm.save_as_mainfile(filepath=str(SCENE_FILE))
print('PROJECT_SAVED',SCENE_FILE,flush=True)

# Render one inexpensive first look immediately when requested.
if os.environ.get('OCEAN_PREVIEW'):
    scene.cycles.samples=24
    scene.render.resolution_percentage=50
    sim.resolution=18
    for frame in (1,151,270):
        scene.frame_set(frame)
        scene.render.filepath=str(ROOT / f'renders/previews/look_{frame:04d}.png')
        bpy.ops.render.render(write_still=True)
