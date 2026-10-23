import numpy as np
from pygltflib import GLTF2
CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
def load(path):
    g = GLTF2().load(path); g.blob = g.binary_blob(); return g
def read(g, i):
    a = g.accessors[i]; n = NC[a.type]; dt = CT[a.componentType]
    if a.bufferView is not None:
        bv = g.bufferViews[a.bufferView]; off = (bv.byteOffset or 0) + (a.byteOffset or 0)
        arr = np.frombuffer(g.blob, dtype=dt, count=a.count * n, offset=off).reshape(a.count, n).copy()
    else:
        arr = np.zeros((a.count, n), dtype=dt)
    if a.sparse:
        s = a.sparse; ib = g.bufferViews[s.indices.bufferView]; vb = g.bufferViews[s.values.bufferView]
        idx = np.frombuffer(g.blob, dtype=CT[s.indices.componentType], count=s.count, offset=(ib.byteOffset or 0) + (s.indices.byteOffset or 0))
        val = np.frombuffer(g.blob, dtype=dt, count=s.count * n, offset=(vb.byteOffset or 0) + (s.values.byteOffset or 0)).reshape(s.count, n)
        arr[idx] = val
    return arr
