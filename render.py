#!/usr/bin/env python3
"""One-command Blender rendering and MP4 encoding. Python standard library only."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def executable(name, fallback=None):
    path = shutil.which(name)
    if path: return path
    local = Path.home()/'.local'/'bin'/name
    if local.exists(): return str(local)
    if fallback and Path(fallback).exists(): return fallback
    raise SystemExit(f'{name} was not found. Add it to PATH and run again.')

def run(command):
    print('Running:', ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True)

def encode(ffmpeg, directory, filename, fps):
    (ROOT/'output').mkdir(exist_ok=True)
    run([ffmpeg, '-hide_banner', '-y', '-framerate', str(fps), '-start_number', '1',
         '-i', ROOT/directory/'frame_%04d.png',
         '-vf', 'scale=out_color_matrix=bt709:out_range=tv',
         '-c:v', 'libx264', '-preset', 'slow',
         '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
         '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
         '-an', ROOT/'output'/filename])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild',action='store_true',help='Rebuild the .blend from source')
    parser.add_argument('--preview',action='store_true',help='Render all 300 frames at 960×540 / 24 samples')
    parser.add_argument('--encode-only',action='store_true')
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--start',type=int,default=1)
    parser.add_argument('--end',type=int,default=300)
    args=parser.parse_args()
    ffmpeg=executable('ffmpeg')
    blend=ROOT/'ocean_to_beer.blend'
    directory='renders/preview_motion' if args.preview else 'renders/frames'
    filename='ocean_to_beer_preview.mp4' if args.preview else 'ocean_to_beer_1080p.mp4'
    if not args.encode_only:
        blender=executable('blender','/Applications/Blender.app/Contents/MacOS/Blender')
        if args.rebuild or not blend.exists():
            run([blender,'-b','--python',ROOT/'scripts/build_scene.py'])
        command=[blender,'-b',blend,'--python',ROOT/'scripts/render_frames.py','--',
                 '--start',args.start,'--end',args.end,'--directory',directory,
                 '--samples',24 if args.preview else args.samples,
                 '--scale',50 if args.preview else 100,
                 '--resolution',18 if args.preview else 26]
        if args.overwrite: command.append('--overwrite')
        run(command)
    missing=[f for f in range(1,301) if not (ROOT/directory/f'frame_{f:04d}.png').exists()]
    if missing:
        print(f'Rendered requested frames. {len(missing)} frames remain before MP4 export.')
        return
    encode(ffmpeg,directory,filename,30)
    print('Finished:',ROOT/'output'/filename)

if __name__=='__main__':
    main()
