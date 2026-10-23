# ---- new face shapes (run inside build_face.py)
NEW_NAMES = ["mouthUpperUp", "mouthLowerDown", "mouthShrugLower"]
P = pos
ys_all = seam_y(P[:, 0]); dyv = P[:, 1] - ys_all
mov = (kind_all <= 0)                                   # skin + rim + cavity (not teeth/tongue)
front = (kind_all >= 0) | (P[:, 2] < -0.05)
mv = (mov & front).astype(np.float32)
CL = pos[upper_idx[0]].astype(np.float64); CR = pos[upper_idx[-1]].astype(np.float64)
def gauss(c, R, ax=(1, 1, 1)):
    d = (P - c) * np.array(ax); return np.exp(-(d ** 2).sum(1) / R ** 2).astype(np.float32)
sideL = sstep(-0.004, 0.006, P[:, 0]); sideR = sstep(-0.004, 0.006, -P[:, 0])      # model +x = her left
def vec(x, y, z): return np.array([x, y, z], np.float32)

# --- jaw
jawD = rot_delta(pos, jaw_w_all, JAW_ANGLE)
put("jawOpen", jawD)
lower_ids = np.concatenate([np.where(side[:N1] == 1)[0], lower_idx[1:-1]])
lipw = np.zeros(Ntot, np.float32)
lipw[lower_ids] = 1 - sstep(0.004, 0.016, seam_y(pos[lower_ids, 0]) - pos[lower_ids, 1])
lipw[N1 + n: N1 + 2 * n] = 1.0                        # rim front edge (lower)
put("mouthClose", -0.9 * jawD * lipw[:, None])

# --- corners: smile / frown / stretch
for nm, C, sd, sgn in (("Left", CL, sideL, 1), ("Right", CR, sideR, -1)):
    w = gauss(C + np.array([sgn * 0.002, 0.002, 0.0]), 0.024) * mv * sd
    cheek = gauss(vec(sgn * 0.050, 1.478, -0.095), 0.040) * mv * sd
    put("mouthSmile" + nm, w[:, None] * vec(sgn * 0.0075, 0.0125, 0.005) + cheek[:, None] * vec(sgn * 0.002, 0.0045, 0.0))
    w = gauss(C, 0.026) * mv * sd
    put("mouthFrown" + nm, w[:, None] * vec(sgn * 0.002, -0.0165, 0.004))
    w = gauss(C, 0.026) * mv * sd
    put("mouthStretch" + nm, w[:, None] * vec(sgn * 0.0105, -0.002, 0.004))

# --- lips: funnel (O) and pucker
lipz = np.exp(-(dyv / 0.022) ** 2 - (P[:, 0] / 0.05) ** 2).astype(np.float32) * mv
put("mouthFunnel", np.stack([-P[:, 0] * 0.38 * lipz, np.sign(dyv) * 0.003 * lipz, -0.011 * lipz], 1))
put("mouthPucker", np.stack([-P[:, 0] * 0.58 * lipz, np.zeros(Ntot), -0.012 * lipz], 1))

# --- upper lip up / lower lip down / chin shrug (new shapes)
side_full = np.concatenate([side, np.full(Ntot - N1, -1, np.int8)])
up = ((side_full == 0) | np.isin(np.arange(Ntot), upper_idx)).astype(np.float32); up[N1:] = 0
up[N1: N1 + n] = 1; up[N1 + 2 * n: N1 + 3 * n] = 1; up[N1 + 4 * n: N1 + 5 * n] = 1   # upper rim edges + first ring of the mouth wall
wx = np.exp(-(P[:, 0] / 0.027) ** 2).astype(np.float32)
wv_up = np.exp(-(np.clip(dyv, 0, None) / 0.011) ** 2).astype(np.float32)
mask_up = np.where(P[:, 1] > ys_all - 0.001, 1.0, 0.0).astype(np.float32) * (up > 0) * mv
put("mouthUpperUp", (mask_up * wx * wv_up)[:, None] * vec(0, 0.0085, 0.001))
lo = np.zeros(Ntot, np.float32); lo[lower_ids] = 1; lo[N1 + 5 * n: N1 + 6 * n] = 1; lo[N1 + n: N1 + 2 * n] = 1; lo[N1 + 3 * n: N1 + 4 * n] = 1
wv_lo = np.exp(-(np.clip(-dyv, 0, None) / 0.012) ** 2).astype(np.float32)
put("mouthLowerDown", (lo * wx * wv_lo)[:, None] * vec(0, -0.0085, 0.001))
chin = np.exp(-((P[:, 1] - 1.426) / 0.016) ** 2 - (P[:, 0] / 0.032) ** 2).astype(np.float32) * (P[:, 2] < -0.07) * mv * (np.where(P[:, 1] < ys_all + 0.001, 1.0, 0.0))
put("mouthShrugLower", chin[:, None] * vec(0, 0.011, -0.007))

# --- mouth shifts (teeth + tongue go along)
shift = np.exp(-((P[:, 1] - 1.443) / 0.045) ** 2 - (P[:, 0] / 0.075) ** 2).astype(np.float32) * (front | (kind_all >= 0))
put("mouthLeft", shift[:, None] * vec(0.0075, 0, 0)); put("mouthRight", shift[:, None] * vec(-0.0075, 0, 0))

# --- boost the weak original shapes (they only moved 4-12 mm)
def boost(nm, k):
    I, V = tg_pos[nm]; tg_pos[nm] = (I, V * k); tg_nrm.pop(nm, None)
for nm, k in (("browInnerUp", 1.3), ("browDownLeft", 1.5), ("browDownRight", 1.5), ("browOuterUpLeft", 1.25), ("browOuterUpRight", 1.25),
              ("eyeSquintLeft", 3.2), ("eyeSquintRight", 3.2), ("cheekSquintLeft", 4.5), ("cheekSquintRight", 4.5),
              ("noseSneerLeft", 2.2), ("noseSneerRight", 2.2), ("cheekPuff", 1.4)):
    boost(nm, k)
# wide eyes: the upper lid goes UP (inverse of the blink) on top of the old (weak) shape
for nm, bl in (("eyeWideLeft", "eyeBlinkLeft"), ("eyeWideRight", "eyeBlinkRight")):
    B = dense(bl); Dw = dense(nm) * 1.5
    upper = B[:, 1] < 0
    Dw += np.where(upper[:, None], -0.85 * B, -0.35 * B)
    put(nm, Dw)
for nm in ("eyeBlinkLeft", "eyeBlinkRight"): tg_nrm.pop(nm, None)
