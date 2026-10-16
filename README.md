# Ocean to Beer

A self-contained Blender scene and a repeatable Python / FFmpeg render pipeline.
All liquid geometry, surface detail, foam, bubbles, lighting, and transformation
fields are procedural. There are no downloaded images, stock clips, or external
texture dependencies.

## Play and edit

- [Play or download the completed motion preview](output/ocean_to_beer_motion_preview.mp4):
  10 seconds, 30 FPS, 480 × 270. This is a work-in-progress visual preview.
- The full 1920 × 1080 export is **not yet completed**. The render pipeline below
  generates it as `output/ocean_to_beer_1080p.mp4`.
- Open [ocean_to_beer.blend](ocean_to_beer.blend) to edit the scene in Blender.
- The camera is orthographic, directly overhead, and locked. The animation is
  300 frames at 30 fps, with a 1920 × 1080 render size.
- Timeline markers identify the natural ocean, transformation, and lager phases.

## Render and export

Requirements: Blender 4.5 LTS, Python 3.9 or later, and FFmpeg with the `libx264`
encoder. From this project folder, with Blender and FFmpeg on your PATH:

```sh
python3 render.py
```

This renders missing PNG frames and assembles a silent H.264 MP4 with broad
player compatibility. Existing frames are kept so a stopped render can resume.
On macOS you can also double-click `Render Video.command`. The launcher checks
`~/.local/bin` and the standard Blender application path when needed.

```sh
python3 render.py --preview                  # 960 × 540 motion preview
python3 render.py --samples 96 --overwrite   # higher-sample final render
python3 render.py --start 91 --end 210        # render only the transformation
python3 render.py --encode-only              # rebuild MP4 from all 300 PNGs
python3 render.py --rebuild --overwrite       # rebuild scene from source
```

After changing scene settings, use `--overwrite` to avoid mixing old and new
frames. A partial render exports only after all 300 frames are present.

The included 480 × 270 preview was rendered with 12 samples and ocean resolution
22. The `--preview` command above creates a larger 960 × 540 preview. To reproduce
the included preview's render settings:

```sh
blender -b ocean_to_beer.blend --python scripts/render_frames.py -- --samples 12 --scale 25 --resolution 22 --directory renders/motion_check
ffmpeg -y -framerate 30 -i renders/motion_check/frame_%04d.png -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart -an output/ocean_to_beer_motion_preview.mp4
```

## Validation

The included preview has been decoded and checked for 300 distinct frames,
10-second duration, and the expected blue-to-gold phase progression. These are
structural and timing checks, not a claim of final visual quality.

```sh
blender -b ocean_to_beer.blend --python scripts/verify_scene.py
python3 scripts/verify_video.py output/ocean_to_beer_motion_preview.mp4 --preview
python3 scripts/verify_video.py  # verify the full-resolution export after rendering
```

## Animation design

| Time | Frames | Behavior |
| --- | --- | --- |
| 0–3 seconds | 1–90 | Blue-green water with continuous ocean motion |
| 3–7 seconds | 91–210 | An irregular advected front converts the surface locally |
| 7–10 seconds | 211–300 | Golden liquid, carbonation, and warm creamy foam |

Two spectral ocean modifiers create directional swell and shorter crossing
waves. Their time values increase continuously throughout the shot. Fine bump
normals add foam microstructure. A common world-space field controls the surface
tint, submerged optical attenuation, foam color and coverage, and bubble
visibility. It spreads diagonally with turbulent boundaries, rather than
crossfading two images.

Foam is generated from the primary ocean's crest-compression attribute and
procedural rafts. Voronoi microstructure changes its texture. Individual bubble
shells are displaced by the same wave spectra, keeping them attached to the
moving surface. The scene uses refractive liquid shading, spectral absorption,
a procedural daylight sky, and Cycles rendering with Metal when available.

This is an art-directed spectral ocean and procedural shading system, not a
Navier–Stokes fluid solver or a chemically simulated conversion. Foam persistence
and bubble emergence are procedural approximations.

## Source files

- `scripts/build_scene.py`: creates the complete scene, materials, camera,
  geometry, and animation. The main artistic parameters are named in this file.
- `scripts/render_frames.py`: resumable frame renderer, run inside Blender.
- `render.py`: command-line entry point for rendering and MP4 encoding.
- `scripts/verify_scene.py` and `scripts/verify_video.py`: scene and movie checks.
- `output/`: the completed motion preview and validation reports.
- `renders/`: local frame sequences, stills, and logs; excluded from Git.

Built with Blender 4.5 LTS and FFmpeg 7.1. No third-party Python packages are
required by the render entry point. Rendering uses the GPU heavily; exact time
depends on sample count and hardware.
