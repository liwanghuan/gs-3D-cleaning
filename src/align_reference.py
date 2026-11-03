#!/usr/bin/env python3
"""
Estimate the transform from the Inria 3DGS / COLMAP frame to the Tanks &
Temples laser-scan frame, and report how wrong it is.

Two independent steps, so the error is measured, not assumed:

  1. Similarity (Umeyama) between Inria camera centres and the camera
     centres in T&T's own COLMAP log, paired by image order, then composed
     with T&T's published COLMAP -> scan matrix.
     Residual: camera-centre distances and camera-orientation angles.

  2. Independent check against the laser scan: push the Inria sparse
     points through the transform, apply the official crop, and measure
     nearest-neighbour distance to the scan. A diagnostic rigid ICP reports
     how far the scan would pull the transform; it is not applied.

Usage:
    python src/align_reference.py --config configs/align_truck.yaml
"""

import argparse
import json
import os
import sys
import numpy as np
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colmap_io import read_sparse, qvec_to_R  # noqa: E402


# --------------------------------------------------------------------------
def read_tnt_log(path):
    """T&T .log: per camera a 'i j k' line then a 4x4 camera-to-world."""
    rows = [l.split() for l in open(path) if l.strip()]
    poses = []
    for a in range(0, len(rows), 5):
        poses.append(np.array(rows[a + 1:a + 5], float))
    return np.stack(poses)


def umeyama(src, dst, with_scale=True):
    """Similarity s, R, t minimising |dst - (s R src + t)|^2 (s = 1 if rigid)."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    U, D, Vt = np.linalg.svd(xd.T @ xs / len(src))
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    s = np.trace(np.diag(D) @ S) / xs.var(0).sum() if with_scale else 1.0
    t = mu_d - s * R @ mu_s
    return s, R, t


def to_h(s, R, t):
    T = np.eye(4)
    T[:3, :3] = s * R
    T[:3, 3] = t
    return T


def apply(T, x):
    return x @ T[:3, :3].T + T[:3, 3]


def rot_angle_deg(Ra, Rb):
    """Angle of Ra^T Rb, batched."""
    c = (np.einsum("nij,nij->n", Ra, Rb) - 1) / 2
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def crop_mask(x, crop):
    """Open3D SelectionPolygonVolume with orthogonal_axis Z."""
    poly = np.array(crop["bounding_polygon"])[:, :2]
    z = x[:, 2]
    inside_z = (z >= crop["axis_min"]) & (z <= crop["axis_max"])
    # even-odd ray casting in xy
    px, py = x[:, 0], x[:, 1]
    inside = np.zeros(len(x), bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        cross = ((yi > py) != (yj > py)) & \
                (px < (xj - xi) * (py - yi) / (yj - yi + 1e-300) + xi)
        inside ^= cross
        j = i
    return inside & inside_z


def rigid_icp(src, tree, ref, max_corr, max_iter):
    """Point-to-point rigid ICP; returns accumulated 4x4 and per-iter RMS."""
    T = np.eye(4)
    cur = src.copy()
    hist = []
    for _ in range(max_iter):
        d, idx = tree.query(cur, k=1, workers=-1)
        m = d < max_corr
        if m.sum() < 10:
            break
        hist.append(float(np.sqrt(np.mean(d[m] ** 2))))
        _, R, t = umeyama(cur[m], ref[idx[m]], with_scale=False)
        step = to_h(1.0, R, t)
        cur = apply(step, cur)
        T = step @ T
        if np.abs(step - np.eye(4)).max() < 1e-8:
            break
    return T, hist


def pct(a, qs=(50, 90, 99)):
    return {f"p{q}": float(np.percentile(a, q)) for q in qs}


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    tau = cfg["eval_tau"]

    cameras, images, (pts, _err, _track) = read_sparse(cfg["colmap"])
    imgs = sorted(images.values(), key=lambda im: im["name"])
    log = read_tnt_log(cfg["tnt_log"])
    print(f"Inria images: {len(imgs)}   T&T log poses: {len(log)}")
    if len(imgs) != len(log):
        sys.exit("camera counts differ: name_order correspondence impossible, stopping")
    print(f"first/last Inria names: {imgs[0]['name']} / {imgs[-1]['name']}")

    # Inria camera-to-world
    R_w2c = np.stack([qvec_to_R(im["qvec"]) for im in imgs])
    t_w2c = np.stack([im["tvec"] for im in imgs])
    C_inria = -np.einsum("nji,nj->ni", R_w2c, t_w2c)        # -R^T t
    R_c2w_inria = np.transpose(R_w2c, (0, 2, 1))
    C_tnt = log[:, :3, 3]
    R_c2w_tnt = log[:, :3, :3]

    # ---- step 1: camera-centre similarity
    s, R, t = umeyama(C_inria, C_tnt)
    T_inria_to_tntcolmap = to_h(s, R, t)
    T_tntcolmap_to_gt = np.loadtxt(cfg["tnt_trans"])
    T = T_tntcolmap_to_gt @ T_inria_to_tntcolmap               # Inria -> scan

    C_gt_pred = apply(T, C_inria)
    C_gt_ref = apply(T_tntcolmap_to_gt, C_tnt)
    cam_err = np.linalg.norm(C_gt_pred - C_gt_ref, axis=1)
    cam_span = np.linalg.norm(C_gt_ref.max(0) - C_gt_ref.min(0))
    ang = rot_angle_deg(R @ R_c2w_inria, R_c2w_tnt)
    s_total = np.cbrt(np.linalg.det(T[:3, :3]))

    print("\n[1] camera-centre similarity (errors in laser-scan metres)")
    print(f"  N cameras = {len(cam_err)}; scale Inria->scan = {s_total:.6f}")
    print(f"  centre error: RMS {np.sqrt(np.mean(cam_err**2)):.5f}  "
          f"median {np.median(cam_err):.5f}  max {cam_err.max():.5f}  "
          f"(trajectory diagonal {cam_span:.3f})")
    print(f"  orientation error (deg): median {np.median(ang):.4f}  max {ang.max():.4f}")

    # ---- step 2: independent check against the laser scan
    print(f"\nloading laser scan {cfg['tnt_gt']} ...")
    v = PlyData.read(cfg["tnt_gt"])["vertex"]
    gt = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    crop = json.load(open(cfg["tnt_crop"]))
    gt_c = gt[crop_mask(gt, crop)]
    tree = cKDTree(gt_c)
    print(f"  scan points: {len(gt):,} total, {len(gt_c):,} inside official crop")

    p_gt = apply(T, pts.astype(np.float64))
    in_crop = crop_mask(p_gt, crop)
    p_in = p_gt[in_crop]
    d, _ = tree.query(p_in, k=1, workers=-1)
    print(f"\n[2] Inria sparse points -> scan (inside crop: {len(p_in):,} of {len(pts):,})")
    print("  NN distance (m): " + "  ".join(f"{k} {v_:.4f}" for k, v_ in pct(d).items()))
    for m in (1, 2, 5, 10):
        print(f"  within {m:>2} x tau ({m * tau:.3f} m): {np.mean(d < m * tau) * 100:6.2f}%")

    # diagnostic ICP (not applied)
    ic = cfg["icp"]
    T_icp, hist = rigid_icp(p_in, tree, gt_c, ic["max_corr_tau_mult"] * tau, ic["max_iter"])
    d2, _ = tree.query(apply(T_icp, p_in), k=1, workers=-1)
    icp_rot = np.degrees(np.arccos(np.clip((np.trace(T_icp[:3, :3]) - 1) / 2, -1, 1)))
    # translation induced at the crop centre, not the origin
    centre = gt_c.mean(0)
    icp_shift = np.linalg.norm(apply(T_icp, centre[None])[0] - centre)
    print(f"\n[2b] diagnostic rigid ICP (max corr {ic['max_corr_tau_mult'] * tau:.3f} m, "
          f"{len(hist)} iters) — NOT applied")
    print(f"  rotation {icp_rot:.4f} deg, shift at crop centre {icp_shift:.4f} m")
    print(f"  RMS over correspondences: {hist[0]:.4f} -> {hist[-1]:.4f} m")
    print("  NN distance after ICP (m): "
          + "  ".join(f"{k} {v_:.4f}" for k, v_ in pct(d2).items()))

    os.makedirs(os.path.dirname(cfg["out_matrix"]), exist_ok=True)
    np.savetxt(cfg["out_matrix"], T, fmt="%.12e",
               header="Inria COLMAP frame -> T&T laser-scan frame (similarity). "
                      "From src/align_reference.py; ICP not applied.")
    print(f"\nwrote {cfg['out_matrix']}")
    print(np.array2string(T, precision=6, suppress_small=True))


if __name__ == "__main__":
    main()
