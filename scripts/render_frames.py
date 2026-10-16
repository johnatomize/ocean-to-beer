"""Render resumable PNG frames from the saved project (run inside Blender)."""
import argparse
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--start', type=int, default=1)
p.add_argument('--end', type=int, default=300)
p.add_argument('--step', type=int, default=1)
p.add_argument('--samples', type=int, default=48)
p.add_argument('--scale', type=int, default=100)
p.add_argument('--resolution', type=int, default=26)
p.add_argument('--directory', default='renders/frames')
p.add_argument('--overwrite', action='store_true')
args = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
scene = bpy.context.scene
scene.cycles.samples = args.samples
scene.render.resolution_percentage = args.scale
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices: d.use = d.type == 'METAL'
    scene.cycles.device = 'GPU'
except Exception:
    scene.cycles.device = 'CPU'
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.type == 'OCEAN' and 'Spectral ocean' in modifier.name:
            modifier.resolution = args.resolution
directory = ROOT / args.directory
directory.mkdir(parents=True, exist_ok=True)
for frame in range(args.start, args.end + 1, args.step):
    path = directory / f'frame_{frame:04d}.png'
    if path.exists() and not args.overwrite:
        print(f'SKIP {frame}: already rendered', flush=True)
        continue
    scene.frame_set(frame)
    scene.render.filepath = str(path)
    print(f'RENDER_FRAME {frame}/{args.end}', flush=True)
    bpy.ops.render.render(write_still=True)
print('RENDER_COMPLETE', flush=True)
