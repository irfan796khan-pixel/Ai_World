# Avatar refit (9 Nov 2026)

Scripts that produced the current `Girl_character_mixamo.glb` from the previous one (commit 92e0e77).
They were run in this order with Blender's Python module (`bpy` 5.2.3), numpy, scipy and pygltflib.
Paths inside the scripts point at the machine they were run on and need editing before a re-run.

1. `extract.py`, `weights.py` - read the mesh, texture colours and bone weights
2. `label.py`, `process1.py` - sort every point into skin / hair / tee / jeans / shoes / eyes
3. `interior.py` - give the mouth cavity, teeth, tongue and jacket leather their own texture spots
4. `process2.py` - smoothing, hair fix, colours, cargo pockets, and the separate jacket shell
5. `bake.py` - bake the new colour and roughness textures (Cycles, emit)
6. `patch.py` - write positions, normals, UVs, textures, the reshaped jawOpen/mouthClose and the `Jacket` mesh into the GLB

Pack command (gltfpack 1.3):
`gltfpack -i Girl_character_mixamo.glb -o Girl_character_mixamo_packed.glb -cc -kn -km -ke -vpf -vtf`

Note: the lip-slit point copies carry a tiny UV offset on purpose. Without it gltfpack welds the
upper and lower lip together and the mouth cannot open in the packed file.
