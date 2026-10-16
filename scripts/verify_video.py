#!/usr/bin/env python3
"""Decode the finished movie and check timing, dimensions and phase colors."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('video',nargs='?',default=str(ROOT/'output/ocean_to_beer_1080p.mp4'))
p.add_argument('--preview',action='store_true')
a=p.parse_args()
video=Path(a.video)
ffmpeg=shutil.which('ffmpeg')
assert ffmpeg, 'FFmpeg must be on PATH'
info=subprocess.run([ffmpeg,'-hide_banner','-i',str(video)],capture_output=True,text=True).stderr
stream=next((line for line in info.splitlines() if 'Video:' in line),'')
dimensions=re.search(r'\b(\d{2,5})x(\d{2,5})\b',stream)
assert dimensions, info
dimensions=[int(dimensions.group(1)),int(dimensions.group(2))]
if not a.preview:
    assert dimensions==[1920,1080], info
assert re.search(r'30 fps',info), info
assert re.search(r'Duration: 00:00:10\.00',info), info
raw=subprocess.run([ffmpeg,'-v','error','-i',str(video),'-map','0:v:0',
                    '-vf','scale=48:27:flags=area','-pix_fmt','rgb24','-f','rawvideo','-'],
                   capture_output=True,check=True).stdout
size=48*27*3
assert len(raw)%size==0
frames=[raw[i:i+size] for i in range(0,len(raw),size)]
assert len(frames)==300, f'Expected 300 frames, decoded {len(frames)}'
assert len({hashlib.sha256(f).digest() for f in frames})==300, 'Repeated / frozen frames'
def colors(frame):
    pixels=list(zip(frame[0::3],frame[1::3],frame[2::3]))
    sea=sum(b>r*1.18 and g>r*1.12 for r,g,b in pixels)/len(pixels)
    gold=sum(r>b*1.35 and g>b*1.15 for r,g,b in pixels)/len(pixels)
    return {'sea_fraction':round(sea,4),'gold_fraction':round(gold,4)}
measure=[colors(f) for f in frames]
assert max(m['gold_fraction'] for m in measure[:90])<0.10, 'Unexpected early amber'
assert max(m['sea_fraction'] for m in measure[210:])<0.10, 'Blue water remains after seven seconds'
assert measure[150]['gold_fraction']>0.1 and measure[150]['sea_fraction']>0.1, 'Missing spatial transition'
motion=[sum(abs(x-y) for x,y in zip(b,c))/size for b,c in zip(frames,frames[1:])]
assert min(motion)>0.01, 'A frame appears frozen'
report={'passed':True,'file':video.name,'decoded_frames':300,'fps':30,'duration_seconds':10,
        'dimensions':dimensions,
        'unique_downsampled_frames':300,'minimum_frame_difference':round(min(motion),4),
        'phase_samples':{str(f):measure[f-1] for f in (1,90,120,151,180,211,270,300)}}
path=video.with_name(video.stem+'_validation.json')
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
