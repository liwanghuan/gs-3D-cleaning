#!/usr/bin/env python3
"""
Split the T4 overhead layer into a wire part (RANSAC 3D line) and the rest,
then measure photo-consistency of each part against a truck-surface
reference: the colour std of a Gaussian centre's pixel across the training
views that have it in frame. Reports distributions; sets no class threshold.

Usage:
    python src/layer_split.py --config configs/layer_split.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import load_colmap  # noqa: E402
from align_reference import apply  # noqa: E402
from confound import auc_mann_whitney  # noqa: E402


def ransac_line(P, iters, tol, rng):
    best = None
    for _ in range(iters):
        i, j = rng.choice(len(P), 2, replace=False)
        d = P[j] - P[i]
        n = np.linalg.norm(d)
        if n < 1e-6:
            continue
        d /= n
        r = P - P[i]
        dist = np.linalg.norm(r - np.outer(r @ d, d), axis=1)
        inl = dist < tol
        if best is None or inl.sum() > best.sum():
            best = inl
    # refit direction on inliers, report extent along it
    Q = P[best]
    c = Q.mean(0)
    d = np.linalg.svd(Q - c)[2][0]
    t = (Q - c) @ d
    return best, d, float(t.max() - t.min())


def layer_wire_rest(split_config_path):
    """Indices of the overhead layer's wire part and rest, by the fixed rule
    in the split config (same layer cut, RANSAC parameters and seed)."""
    scfg = yaml.safe_load(open(split_config_path))
    icfg = yaml.safe_load(open(scfg["inspect_config"]))
    fcfg = yaml.safe_load(open(icfg["features_config"]))
    lcfg = yaml.safe_load(open(icfg["label_config"]))
    acfg = yaml.safe_load(open(icfg["align_config"]))
    df = pd.read_parquet(fcfg["out"], columns=["x", "y", "z", "view_count"])
    lab = pd.read_parquet(lcfg["out"])
    xyz_gt = apply(np.loadtxt(acfg["out_matrix"]), df[["x", "y", "z"]].to_numpy(np.float64))
    pos = (lab.unsupported_scan == 1).to_numpy(dtype=bool, na_value=False)
    seen = df.view_count.to_numpy() > 0
    layer_idx = np.nonzero(pos & seen & (xyz_gt[:, 2] > icfg["layer_min_scan_z"]))[0]
    wire, _, _ = ransac_line(xyz_gt[layer_idx], scfg["ransac_iterations"],
                             scfg["ransac_inlier_m"], np.random.default_rng(scfg["seed"]))
    return layer_idx[wire], layer_idx[~wire]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    icfg = yaml.safe_load(open(cfg["inspect_config"]))
    fcfg = yaml.safe_load(open(icfg["features_config"]))
    lcfg = yaml.safe_load(open(icfg["label_config"]))
    acfg = yaml.safe_load(open(icfg["align_config"]))
    proj = fcfg["projection"]
    rng = np.random.default_rng(cfg["seed"])

    df = pd.read_parquet(fcfg["out"], columns=["x", "y", "z", "view_count"])
    lab = pd.read_parquet(lcfg["out"])
    T = np.loadtxt(acfg["out_matrix"])
    xyz = df[["x", "y", "z"]].to_numpy(np.float64)
    xyz_gt = apply(T, xyz)
    seen = df.view_count.to_numpy() > 0
    pos = (lab.unsupported_scan == 1).to_numpy(dtype=bool, na_value=False)
    neg = (lab.unsupported_scan == 0).to_numpy(dtype=bool, na_value=False)
    layer_idx = np.nonzero(pos & seen & (xyz_gt[:, 2] > icfg["layer_min_scan_z"]))[0]

    # ---- wire split
    wire, direction, length = ransac_line(xyz_gt[layer_idx], cfg["ransac_iterations"],
                                          cfg["ransac_inlier_m"], rng)
    wire_idx, rest_idx = layer_idx[wire], layer_idx[~wire]
    print(f"layer Gaussians: {len(layer_idx):,}")
    print(f"wire part (RANSAC line, inlier {cfg['ransac_inlier_m']} m): {len(wire_idx):,} "
          f"({len(wire_idx) / len(layer_idx) * 100:.1f}%); line extent {length:.2f} m; "
          f"direction (scan frame) {np.round(direction, 3)}")
    print(f"rest of layer: {len(rest_idx):,}")

    ref_idx = rng.choice(np.nonzero(neg & seen)[0], cfg["reference_n"], replace=False)
    groups = {"wire": wire_idx, "layer rest": rest_idx, "truck surface (L2-, reference)": ref_idx}
    allg = np.concatenate(list(groups.values()))
    P = xyz[allg]

    # ---- photo-consistency, one image at a time
    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    s1 = np.zeros((len(P), 3)); s2 = np.zeros((len(P), 3)); n = np.zeros(len(P), int)
    for c in cams:
        img = plt.imread(os.path.join(icfg["images"], c["name"])).astype(np.float64) / 255.0
        H, W = img.shape[:2]
        pc = P @ c["R"].T + c["t"]
        z = pc[:, 2]
        front = z > proj["near_plane"]
        u = (c["fx"] * pc[:, 0] / np.where(front, z, 1) + c["cx"]) * W / c["width"]
        v = (c["fy"] * pc[:, 1] / np.where(front, z, 1) + c["cy"]) * H / c["height"]
        ok = front & (u >= 0) & (u < W - 0.5) & (v >= 0) & (v < H - 0.5)
        col = img[np.round(v[ok]).astype(int), np.round(u[ok]).astype(int)]
        s1[ok] += col; s2[ok] += col ** 2; n[ok] += 1
    mean = s1 / np.maximum(n, 1)[:, None]
    std = np.sqrt(np.maximum(s2 / np.maximum(n, 1)[:, None] - mean ** 2, 0)).mean(axis=1)

    print(f"\nphoto-consistency: colour std across views in frame (RGB mean, 0..1), "
          f"min {cfg['min_views']} views; no occlusion test")
    off, rows, vals = 0, [], {}
    for name, idx in groups.items():
        k = slice(off, off + len(idx)); off += len(idx)
        ok = n[k] >= cfg["min_views"]
        vals[name] = std[k][ok]
        q = np.percentile(vals[name], [25, 50, 75])
        rows.append(dict(group=name, N=len(idx), N_used=int(ok.sum()),
                         views_in_frame_med=np.median(n[k][ok]),
                         std_p25=q[0], std_median=q[1], std_p75=q[2]))
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4f}".format):
        print(pd.DataFrame(rows).to_string(index=False))
    ref = vals["truck surface (L2-, reference)"]
    for name in ("wire", "layer rest"):
        a = auc_mann_whitney(np.r_[vals[name], ref],
                             np.r_[np.ones(len(vals[name])), np.zeros(len(ref))].astype(int))[0]
        print(f"  P(colour std of {name} > truck surface) = {a:.4f}  (0.5 = no difference)")


if __name__ == "__main__":
    main()
