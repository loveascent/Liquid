# Liquid

WebGL- und Blender-Demos rund um Flüssigkeiten und Licht.

- `liquid-light.html` – 2D-Fluidsimulation (WebGL2, Navier-Stokes, Bloom). Tasten: Space/B/C/H
- `genesis.html` – prozeduraler Planet per Raymarching-Shader
- `kaffee-sahne-3d.html` – Echtzeit-3D-Voxelversion (verworfen, zu langsam)
- `kaffee-blender/build2.py` – Sahne in Kaffee, gitterfrei prozedural, Blender Cycles
- `kaffee-sahne-cinematic.mp4` – gerenderter Film, 8 s, 1080p

Blender-Render: `blender -b -P kaffee-blender/build2.py -- build` dann `-- render`.
