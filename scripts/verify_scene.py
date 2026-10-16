"""Check delivery requirements against the saved Blender scene."""
import bpy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
s=bpy.context.scene
assert (s.render.resolution_x,s.render.resolution_y)==(1920,1080)
assert s.render.fps==30 and s.render.fps_base==1
assert (s.frame_start,s.frame_end)==(1,300)
assert s.camera.data.type=='ORTHO'
assert all(abs(v)<1e-8 for v in s.camera.rotation_euler)
assert s.camera.animation_data is None, 'Camera must remain fixed'
assert not s.camera.data.dof.use_dof, 'Entire surface must remain in focus'

g=bpy.data.node_groups['LAGER • advected reaction front']
progress=g.nodes['Transformation • 3–7 seconds'].outputs[0]
o=bpy.data.objects['OCEAN • continuous spectral simulation']
wave=o.modifiers[0]
rows=[]
for f in (1,90,91,120,151,180,210,211,270,300):
    s.frame_set(f)
    rows.append({'frame':f,'time_seconds':(f-1)/30,
                 'transformation_front':round(progress.default_value,5),
                 'ocean_simulation_time':round(wave.time,5)})
assert rows[0]['transformation_front']==rows[1]['transformation_front']
assert rows[-1]['transformation_front']==rows[-2]['transformation_front']
assert all(b['ocean_simulation_time']>a['ocean_simulation_time'] for a,b in zip(rows,rows[1:]))
assert len(bpy.data.objects['CARBONATION • floating gas domes'].data.vertices)>100000
assert all(image.source=='GENERATED' or image.type=='RENDER_RESULT' for image in bpy.data.images), 'External imagery should not be required'
report={'passed':True,'resolution':[1920,1080],'fps':30,'frames':300,'duration_seconds':10,
        'camera':'fixed orthographic nadir','external_images':False,'timeline':rows}
(ROOT/'output').mkdir(exist_ok=True)
(ROOT/'output'/'scene_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
