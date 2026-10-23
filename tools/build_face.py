"""Rebuild Girl_character_mixamo.glb with a real, openable mouth.
   orig.glb  ->  out.glb
   1. cut the skin along the painted lip line (slit, closed at rest)
   2. add lip rim + mouth cavity + teeth + tongue (same mesh, same material, flat texels)
   3. author new face shapes (morph targets)
"""
import sys, io, json, math
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from PIL import Image
from pygltflib import GLTF2, Accessor, BufferView, Sparse, AccessorSparseIndices as SparseIndices, AccessorSparseValues as SparseValues
sys.path.insert(0, "/home/claude/work")
from glbio import load, read, CT, NC

SRC = "/home/claude/work/orig.glb"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/work/out.glb"
XC = 0.034                                  # mouth corner |x|
HINGE = np.array([0.0, 1.51, 0.02])         # jaw hinge (mesh space, front = -z)
JAW_ANGLE = 0.20                            # radians at jawOpen = 1


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def seam_y(x):
    a = np.clip((np.abs(x) - 0.020) / 0.014, 0, 1)
    return 1.4441 + 0.0030 * a * a


def vnormals(P, T):
    n = np.zeros_like(P)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    for k in range(3): np.add.at(n, T[:, k], fn)
    l = np.linalg.norm(n, axis=1, keepdims=True); l[l == 0] = 1
    return n / l


# ------------------------------------------------------------------ load
g = load(SRC)
prim = g.meshes[0].primitives[0]
names = list(g.meshes[0].extras["targetNames"])
pos = read(g, prim.attributes.POSITION).astype(np.float32)
nrm = read(g, prim.attributes.NORMAL).astype(np.float32)
uv = read(g, prim.attributes.TEXCOORD_0).astype(np.float32)
jts = read(g, prim.attributes.JOINTS_0).astype(np.uint8)
wts = read(g, prim.attributes.WEIGHTS_0).astype(np.float32)
tri = read(g, prim.indices).reshape(-1, 3).astype(np.int64)
N0 = len(pos)
tg_pos, tg_nrm = {}, {}                      # name -> (indices, values) sparse
for i, t in enumerate(prim.targets):
    d = read(g, t["POSITION"]); m = np.abs(d).sum(1) > 0
    tg_pos[names[i]] = (np.where(m)[0], d[m].astype(np.float32))
    if "NORMAL" in t:
        d = read(g, t["NORMAL"]); m = np.abs(d).sum(1) > 0
        tg_nrm[names[i]] = (np.where(m)[0], d[m].astype(np.float32))
bv = g.bufferViews[g.images[0].bufferView]
img_bytes = bytes(g.blob[bv.byteOffset:bv.byteOffset + bv.byteLength])
tex = np.asarray(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
ibm_acc = g.accessors[g.skins[0].inverseBindMatrices]
ibm_bv = g.bufferViews[ibm_acc.bufferView]
ibm_bytes = bytes(g.blob[ibm_bv.byteOffset + (ibm_acc.byteOffset or 0): ibm_bv.byteOffset + (ibm_acc.byteOffset or 0) + ibm_acc.count * 64])
print("loaded", N0, "verts", len(tri), "tris")

# ------------------------------------------------------------------ 1. cut along the lip line
f = pos[:, 1] - seam_y(pos[:, 0])
cand = (np.abs(pos[:, 0]) <= XC + 0.003) & (np.abs(f) < 0.0035) & (pos[:, 2] < -0.09) & (nrm[:, 2] < -0.2)
E = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
E = E[cand[E[:, 0]] & cand[E[:, 1]]]
fm = 0.5 * (np.abs(f[E[:, 0]]) + np.abs(f[E[:, 1]]))
L = np.linalg.norm(pos[E[:, 0]] - pos[E[:, 1]], axis=1)
cost = L * (1 + 400 * fm) + 1e-9
G = coo_matrix((cost, (E[:, 0], E[:, 1])), shape=(N0, N0)).tocsr(); G = G.maximum(G.T)
ci = np.where(cand)[0]
def corner(sgn):
    d = (pos[ci, 0] - sgn * XC) ** 2 + (pos[ci, 1] - seam_y(sgn * XC)) ** 2
    return ci[np.argmin(d)]
cL, cR = corner(+1), corner(-1)
dist, pred = dijkstra(G, indices=cL, return_predecessors=True)
assert np.isfinite(dist[cR]), "no path along lip line"
path = [cR]
while path[-1] != cL: path.append(pred[path[-1]])
path = path[::-1]                                   # from +x corner to -x corner
print("lip line path:", len(path), "vertices, x from", pos[path[0], 0].round(4), "to", pos[path[-1], 0].round(4),
      "max |f| along path (mm):", (np.abs(f[path]).max() * 1000).round(2))

# triangles per vertex
tv = tri.reshape(-1); order = np.argsort(tv, kind="stable"); tstart = np.searchsorted(tv[order], np.arange(N0 + 1))
def incident(v): return order[tstart[v]:tstart[v + 1]] // 3
newpos, newnrm, newuv, newj, neww, src_of = [], [], [], [], [], []
upper_idx = [path[0]]; lower_idx = [path[0]]
cen_all = pos[tri].mean(1)
n_next = N0
for k in range(1, len(path) - 1):
    v, a, b = path[k], path[k - 1], path[k + 1]
    ts = incident(v)
    cen = cen_all[ts][:, :2] - pos[v, :2]
    th = np.arctan2(cen[:, 1], cen[:, 0])
    tha = math.atan2(pos[a, 1] - pos[v, 1], pos[a, 0] - pos[v, 0]); thb = math.atan2(pos[b, 1] - pos[v, 1], pos[b, 0] - pos[v, 0])
    rel = (th - thb) % (2 * math.pi); rela = (tha - thb) % (2 * math.pi)
    g1 = rel < rela
    if g1.all() or (~g1).all():
        raise RuntimeError("path vertex with one-sided fan at %d" % k)
    low = g1 if cen[g1, 1].mean() < cen[~g1, 1].mean() else ~g1
    nv = n_next; n_next += 1
    for t in ts[low]:
        row = tri[t]; row[row == v] = nv
    src_of.append(v); upper_idx.append(v); lower_idx.append(nv)
upper_idx.append(path[-1]); lower_idx.append(path[-1])
upper_idx = np.array(upper_idx); lower_idx = np.array(lower_idx); src_of = np.array(src_of)
ndup = len(src_of)
pos = np.concatenate([pos, pos[src_of]]); nrm = np.concatenate([nrm, nrm[src_of]]); uv = np.concatenate([uv, uv[src_of]])
jts = np.concatenate([jts, jts[src_of]]); wts = np.concatenate([wts, wts[src_of]])
dup_new = np.arange(N0, N0 + ndup)
def extend_sparse(I, V):
    o = np.argsort(I); Is = I[o]; p_ = np.searchsorted(Is, src_of); p_c = np.clip(p_, 0, len(Is) - 1)
    ok = (p_ < len(Is)) & (Is[p_c] == src_of)
    return np.concatenate([I, dup_new[ok]]), np.concatenate([V, V[o[p_c[ok]]]])
for dct in (tg_pos, tg_nrm):
    for k_ in list(dct): dct[k_] = extend_sparse(*dct[k_])
print("slit made:", ndup, "duplicated vertices")

# which side of the slit is each original vertex on? (flood fill inside the slit span)
N1 = len(pos)
ff = pos[:, 1] - seam_y(pos[:, 0])
region = (np.abs(pos[:, 0]) < XC - 0.0005) & (np.abs(ff) < 0.016) & (pos[:, 2] < -0.085)
region[[path[0], path[-1]]] = False
Et = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]); Et = Et[region[Et[:, 0]] & region[Et[:, 1]]]
Gr = coo_matrix((np.ones(len(Et)), (Et[:, 0], Et[:, 1])), shape=(N1, N1)).tocsr()
ncomp, lab = connected_components(Gr, directed=False)
side = np.full(N1, -1, np.int8)                     # 0 = upper side, 1 = lower side, -1 = unknown
cu, cl = set(lab[upper_idx[1:-1]]), set(lab[lower_idx[1:-1]])
print("flood components: upper", cu, "lower", cl)
assert len(cu) == 1 and len(cl) == 1 and cu != cl, "slit does not separate the two lips"
side[region & (lab == list(cu)[0])] = 0; side[region & (lab == list(cl)[0])] = 1

# ------------------------------------------------------------------ jaw movement
def jaw_weight(P, sd=None):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]; ax = np.abs(x); d = y - seam_y(x)
    wlat = 1 - sstep(0.026, 0.078, ax)
    h = 0.0004 + 0.0076 * sstep(XC - 0.004, XC + 0.006, ax)
    v = 1 - sstep(-h, h, d)
    if sd is not None:
        v = np.where(sd == 0, 0.0, np.where(sd == 1, 1.0, v))
    wy = sstep(1.29, 1.38, y)
    wz = 1 - sstep(-0.03, 0.05, z)
    return v * wlat * wy * wz

def rot_delta(P, w, theta):
    r = P - HINGE; th = theta * w                      # per-vertex angle
    c, s = np.cos(th), np.sin(th)
    ny = HINGE[1] + r[:, 1] * c + r[:, 2] * s
    nz = HINGE[2] - r[:, 1] * s + r[:, 2] * c
    out = np.zeros_like(P); out[:, 1] = ny - P[:, 1]; out[:, 2] = nz - P[:, 2]
    return out

# ------------------------------------------------------------------ 2. mouth inside: lip rim, cavity, teeth, tongue
def find_flat(target, rgb_tol=60, used=None):
    """a flat-coloured texel of the skin texture close to `target` (so interior parts need no new texture)"""
    H, W = tex.shape[:2]; s = 8
    sm = tex[:H // s * s, :W // s * s].reshape(H // s, s, W // s, s, 3).astype(np.float32)
    mean = sm.mean((1, 3)); var = sm.var((1, 3)).sum(-1)
    dist = np.linalg.norm(mean - np.array(target, np.float32), axis=-1)
    score = dist + 6 * np.sqrt(var)
    j = np.unravel_index(np.argmin(score), score.shape)
    col = mean[j]
    return ((j[1] * s + s / 2) / W, (j[0] * s + s / 2) / H), col.round(0), float(np.sqrt(var[j]).round(2))
UV_CAV, c1, v1 = find_flat((70, 25, 30))
UV_TEETH, c2, v2 = find_flat((238, 232, 220))
UV_TONGUE, c3, v3 = find_flat((190, 85, 95))
print("flat colours  cavity", c1, v1, " teeth", c2, v2, " tongue", c3, v3)

inter_pos, inter_uv, inter_tri, inter_kind, inter_w = [], [], [], [], []   # kind: 0 rim/cavity, 1 teeth-up, 2 teeth-low, 3 tongue
def add_piece(P, T, uvp, kind, jw, orient, both=False):
    base = sum(len(p) for p in inter_pos) + N1
    P = np.asarray(P, np.float32); T = np.asarray(T, np.int64).copy()
    # orient triangles so the visible side faces `orient(tri_centre) -> unit vector`
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]); cen = P[T].mean(1)
    want = orient(cen); flip = (fn * want).sum(1) < 0
    T[flip] = T[flip][:, [0, 2, 1]]
    if both: T = np.concatenate([T, T[:, [0, 2, 1]]])          # visible from both sides (dark inside, no see-through holes)
    inter_pos.append(P); inter_uv.append(np.tile(np.array(uvp, np.float32), (len(P), 1)))
    inter_tri.append(T + base); inter_kind.append(np.full(len(P), kind)); inter_w.append(np.asarray(jw, np.float32))

Q = pos[upper_idx].copy(); Qd = pos[lower_idx].copy()            # rim front edge (identical at rest)
n = len(Q); xq = Q[:, 0]
tk = np.sqrt(np.clip(1 - (xq / XC) ** 2, 0, 1)) ** 0.8
depth = 0.006 + 0.005 * tk
UB = Q + np.stack([np.zeros(n), 0.0035 * tk, depth], 1)
LB = Q + np.stack([np.zeros(n), -0.0035 * tk, depth], 1)
cav_c = np.array([0, 1.4441, -0.085])
to_axis = lambda c: np.stack([np.zeros(len(c)), 1.4441 - c[:, 1], np.zeros(len(c))], 1)
# rim strips (front edge -> back edge); front-edge vertices are the real skin-slit vertices
def strip_tris(a_idx, b_idx):
    T = []
    for k in range(len(a_idx) - 1):
        T += [[a_idx[k], a_idx[k + 1], b_idx[k]], [a_idx[k + 1], b_idx[k + 1], b_idx[k]]]
    return T
# vertex layout of the interior block: UB (n), LB (n)  [corner pairs are separate verts, welded by position later]
PU, PL = UB, LB
rim_P = np.concatenate([Q, Qd, UB, LB])                          # copies of skin-slit edge so rim shares exact positions
rim_T = []
iQu, iQd, iUB, iLB = np.arange(n), n + np.arange(n), 2 * n + np.arange(n), 3 * n + np.arange(n)
rim_T += strip_tris(iQu, iUB) + strip_tris(iQd, iLB)
wjaw_front = jaw_weight(np.concatenate([Q, Qd]), np.concatenate([np.zeros(n, np.int8), np.ones(n, np.int8)]))
wjaw_back = np.concatenate([np.zeros(n), jaw_weight(LB, np.ones(n, np.int8))])
rim_w = np.concatenate([wjaw_front, wjaw_back])
rim_w[[0, n - 1, n, 2 * n - 1]] = 0.45                             # mouth corners are shared by both lips
rim_w[[2 * n, 3 * n - 1, 3 * n, 4 * n - 1]] = 0.45
add_piece(rim_P, rim_T, UV_CAV, 0, rim_w, to_axis, both=True)

# cavity pouch: from the back loop to an apex deep inside the head
loop = np.concatenate([UB, LB[::-1]])                              # closed loop around the opening
loop_w = np.concatenate([np.zeros(n), jaw_weight(LB, np.ones(n, np.int8))[::-1]]); loop_w[[0, n - 1, n, 2 * n - 1]] = 0.45
apex = np.array([0.0, 1.434, -0.045])
J = 7; rings = []; ring_w = []
for j in range(J + 1):
    s = j / J; e = s ** 0.8
    ring = loop * (1 - e) + apex * e
    ring[:, 0] = loop[:, 0] * (1 - s) ** 0.9                     # keep width, then close in
    ring[:, 1] += 0.004 * np.sin(math.pi * s) * np.sign(ring[:, 1] - 1.4441)
    rings.append(ring); ring_w.append(loop_w * (1 - 0.55 * s))
P_cav = np.concatenate(rings); W_cav = np.concatenate(ring_w); m_ = len(loop)
T_cav = []
for j in range(J):
    for k in range(m_):
        k2 = (k + 1) % m_
        a, b, c, d = j * m_ + k, j * m_ + k2, (j + 1) * m_ + k, (j + 1) * m_ + k2
        T_cav += [[a, b, c], [b, d, c]]
add_piece(P_cav, T_cav, UV_CAV, 0, W_cav, lambda c: np.stack([-c[:, 0] * 0.3, 1.4375 - c[:, 1], np.full(len(c), -0.02)], 1), both=True)

def superellipsoid(c, r, e=0.45, nu=14, nv=9):
    u = np.linspace(-math.pi, math.pi, nu, endpoint=False); v = np.linspace(-math.pi / 2, math.pi / 2, nv)
    P = [];
    for vv in v:
        for uu in u:
            cv = np.sign(math.cos(vv)) * abs(math.cos(vv)) ** e; sv = np.sign(math.sin(vv)) * abs(math.sin(vv)) ** e
            cu = np.sign(math.cos(uu)) * abs(math.cos(uu)) ** e; su = np.sign(math.sin(uu)) * abs(math.sin(uu)) ** e
            P.append([c[0] + r[0] * cv * cu, c[1] + r[1] * sv, c[2] + r[2] * cv * su])
    T = []
    for j in range(nv - 1):
        for i in range(nu):
            i2 = (i + 1) % nu; a, b, c_, d = j * nu + i, j * nu + i2, (j + 1) * nu + i, (j + 1) * nu + i2
            T += [[a, b, c_], [b, d, c_]]
    return np.array(P), T
def add_tooth(c, r, kind, w):
    P, T = superellipsoid(c, r)
    add_piece(P, T, UV_TEETH, kind, np.full(len(P), w), lambda cen, c=np.array(c): cen - c)

xs_up = np.array([-0.0163, -0.0098, -0.0033, 0.0033, 0.0098, 0.0163])
for x in xs_up:
    ys = seam_y(x); zf = -0.1115 + 0.020 * (x / 0.02) ** 2
    big = 1.15 if abs(x) < 0.005 else 1.0
    add_tooth([x, ys + 0.0008, zf + 0.0016], [0.0031, 0.0043 * big, 0.0016], 1, 0.0)
xs_lo = np.array([-0.0145, -0.0087, -0.0029, 0.0029, 0.0087, 0.0145])
for x in xs_lo:
    ys = seam_y(x); zf = -0.1085 + 0.020 * (x / 0.02) ** 2
    wl = float(jaw_weight(np.array([[x, ys - 0.006, zf]]), np.ones(1, np.int8))[0])
    add_tooth([x, ys - 0.0030, zf + 0.0015], [0.0027, 0.0033, 0.0015], 2, wl)
# tongue
Pt, Tt = superellipsoid([0.0, 1.4362, -0.078], [0.0125, 0.0036, 0.020], e=0.7, nu=16, nv=9)
add_piece(Pt, Tt, UV_TONGUE, 3, np.full(len(Pt), 0.9) * float(jaw_weight(np.array([[0, 1.43, -0.08]]), np.ones(1, np.int8))[0]),
          lambda cen: cen - np.array([0.0, 1.4362, -0.078]))

I_pos = np.concatenate(inter_pos); I_uv = np.concatenate(inter_uv); I_tri = np.concatenate(inter_tri); I_w = np.concatenate(inter_w)
nI = len(I_pos)
# normals for the interior parts (per piece, smooth)
I_nrm = np.zeros_like(I_pos); off = 0; done = []; kinds_piece = [k_[0] for k_ in inter_kind]
for P_, T_ in zip(inter_pos, inter_tri):
    Tl = T_ - N1 - off
    if len(Tl) and (kinds_piece[len(done)] == 0): Tl = Tl[:len(Tl) // 2]
    I_nrm[off:off + len(P_)] = vnormals(P_, Tl); off += len(P_); done.append(1)
# skin joints/weights for the interior: copy from the nearest face vertex
kd = cKDTree(pos[(pos[:, 2] < -0.05) & (np.abs(pos[:, 0]) < 0.06) & (np.abs(pos[:, 1] - 1.44) < 0.04)])
face_ids = np.where((pos[:, 2] < -0.05) & (np.abs(pos[:, 0]) < 0.06) & (np.abs(pos[:, 1] - 1.44) < 0.04))[0]
_, nn = kd.query(I_pos); I_j = jts[face_ids[nn]]; I_wt = wts[face_ids[nn]]
print("interior parts:", nI, "verts,", len(I_tri), "tris")

pos = np.concatenate([pos, I_pos]); nrm = np.concatenate([nrm, I_nrm]); uv = np.concatenate([uv, I_uv])
jts = np.concatenate([jts, I_j]); wts = np.concatenate([wts, I_wt]); tri = np.concatenate([tri, I_tri])
Ntot = len(pos)
jaw_w_all = np.zeros(Ntot, np.float32)
jaw_w_all[:N1] = jaw_weight(pos[:N1], side)
jaw_w_all[upper_idx[[0, -1]]] = 0.45                          # mouth corners are shared by both lips
jaw_w_all[lower_idx[1:-1]] = jaw_weight(pos[lower_idx[1:-1]], np.ones(ndup, np.int8))
jaw_w_all[upper_idx[1:-1]] = 0.0
jaw_w_all[N1:] = I_w
np.save("/home/claude/work/jaw_w.npy", jaw_w_all)

# ------------------------------------------------------------------ 3. face shapes (morph targets)
def dense(name):
    I, V = tg_pos[name]; out = np.zeros((Ntot, 3), np.float32); out[I] = V; return out
def put(name, D):
    m = np.abs(D).sum(1) > 1e-7; tg_pos[name] = (np.where(m)[0], D[m].astype(np.float32)); tg_nrm.pop(name, None)

kind_all = np.full(Ntot, -1, np.int8); kind_all[N1:] = np.concatenate(inter_kind)
exec(open("/home/claude/work/shapes_def.py").read())
for nm_ in NEW_NAMES:
    if nm_ not in names: names.append(nm_)
g.meshes[0].extras = {"targetNames": names}; g.meshes[0].weights = [0.0] * len(names)

# ------------------------------------------------------------------ write glb
parts = []; cur = [0]
def add_bytes(b, align=4):
    pad = (-cur[0]) % align
    if pad: parts.append(b"\0" * pad); cur[0] += pad
    off = cur[0]; parts.append(b); cur[0] += len(b); return off
new_bv, new_acc = [], []
def bview(b, target=None):
    off = add_bytes(b); new_bv.append(BufferView(buffer=0, byteOffset=off, byteLength=len(b), target=target)); return len(new_bv) - 1
def acc_dense(arr, comp, typ, target=None, minmax=False):
    i = bview(arr.tobytes(), target)
    a = Accessor(bufferView=i, byteOffset=0, componentType=comp, count=len(arr), type=typ)
    if minmax: a.min = arr.min(0).astype(float).tolist(); a.max = arr.max(0).astype(float).tolist()
    new_acc.append(a); return len(new_acc) - 1
def acc_sparse(I, V, count):
    ib = bview(I.astype(np.uint32).tobytes()); vb = bview(V.astype(np.float32).tobytes())
    full = np.concatenate([V, np.zeros((1, 3), np.float32)])
    a = Accessor(componentType=5126, count=count, type="VEC3", min=full.min(0).astype(float).tolist(), max=full.max(0).astype(float).tolist(),
                 sparse=Sparse(count=len(I), indices=SparseIndices(bufferView=ib, componentType=5125), values=SparseValues(bufferView=vb)))
    new_acc.append(a); return len(new_acc) - 1

img_bv = bview(img_bytes)
ibm_i = bview(ibm_bytes); new_acc.append(Accessor(bufferView=ibm_i, componentType=5126, count=ibm_acc.count, type="MAT4")); ibm_ai = 0
pa = acc_dense(pos.astype(np.float32), 5126, "VEC3", 34962, True)
na = acc_dense(nrm.astype(np.float32), 5126, "VEC3", 34962)
ua = acc_dense(uv.astype(np.float32), 5126, "VEC2", 34962)
ja = acc_dense(jts.astype(np.uint8), 5121, "VEC4", 34962)
wa = acc_dense(wts.astype(np.float32), 5126, "VEC4", 34962)
ia = acc_dense(tri.reshape(-1).astype(np.uint32), 5125, "SCALAR", 34963)
targets = []
for nm in names:
    I, V = tg_pos[nm]; o = np.argsort(I); t = {"POSITION": acc_sparse(I[o], V[o], Ntot)}
    if nm in tg_nrm:
        I2, V2 = tg_nrm[nm]; o2 = np.argsort(I2); t["NORMAL"] = acc_sparse(I2[o2], V2[o2], Ntot)
    targets.append(t)
g.images[0].bufferView = img_bv
g.skins[0].inverseBindMatrices = ibm_ai
prim.attributes.POSITION, prim.attributes.NORMAL, prim.attributes.TEXCOORD_0 = pa, na, ua
prim.attributes.JOINTS_0, prim.attributes.WEIGHTS_0, prim.indices, prim.targets = ja, wa, ia, targets
g.bufferViews = new_bv; g.accessors = new_acc
blob = b"".join(parts); blob += b"\0" * ((-len(blob)) % 4)
g.buffers[0].byteLength = len(blob); g.set_binary_blob(blob)
g.save_binary(OUT)
import os; print("saved", OUT, round(os.path.getsize(OUT) / 1e6, 1), "MB;", Ntot, "verts")
