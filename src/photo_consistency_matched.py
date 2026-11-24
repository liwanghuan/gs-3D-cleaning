#!/usr/bin/env python3
"""
Matched photo-consistency, no rendering. Every group is measured over the
same window of training views, with every point in frame in all of them.
The reference is truck surface whose normal faces every window camera
(a back-face test, a dot product). A positive control on the reference,
fixed in the config, decides whether the method is usable at all.

Usage:
    python src/photo_consistency_matched.py --config configs/photo_consistency_matched.yaml
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
from extract_features import load_colmap, load_gaussians, quats_to_R  # noqa: E402
from align_reference import apply  # noqa: E402
from confound import auc_mann_whitney  # noqa: E402
from layer_split import ransac_line  # noqa: E402


def in_frame(P, c, near):
    pc = P @ c["R"].T + c["t"]
    z = pc[:, 2]
    front = z > near
    zz = np.where(front, z, 1.0)
    u = c["fx"] * pc[:, 0] / zz + c["cx"]
    v = c["fy"] * pc[:, 1] / zz + c["cy"]
    ok = front & (u >= 0) & (u < c["width"]) & (v >= 0) & (v < c["height"])
    return ok, u, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    scfg = yaml.safe_load(open(cfg["layer_split_config"]))
    icfg = yaml.safe_load(open(scfg["inspect_config"]))
    fcfg = yaml.safe_load(open(icfg["features_config"]))
    lcfg = yaml.safe_load(open(icfg["label_config"]))
    acfg = yaml.safe_load(open(icfg["align_config"]))
    proj, near = fcfg["projection"], fcfg["projection"]["near_plane"]

    df = pd.read_parquet(fcfg["out"], columns=["x", "y", "z", "view_count"])
    lab = pd.read_parquet(lcfg["out"])
    T = np.loadtxt(acfg["out_matrix"])
    xyz = df[["x", "y", "z"]].to_numpy(np.float64)
    xyz_gt = apply(T, xyz)
    seen = df.view_count.to_numpy() > 0
    in_crop = lab.in_crop.to_numpy()
    pos = (lab.unsupported_scan == 1).to_numpy(dtype=bool, na_value=False)
    neg = (lab.unsupported_scan == 0).to_numpy(dtype=bool, na_value=False)

    # same layer and wire split as layer_split.py (same rule, same seed)
    layer_idx = np.nonzero(pos & seen & (xyz_gt[:, 2] > icfg["layer_min_scan_z"]))[0]
    wire, _, _ = ransac_line(xyz_gt[layer_idx], scfg["ransac_iterations"],
                             scfg["ransac_inlier_m"], np.random.default_rng(scfg["seed"]))
    wire_idx, rest_idx = layer_idx[wire], layer_idx[~wire]

    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    win = [c for c in cams if cfg["window_first"] <= c["name"] <= cfg["window_last"]]
    print(f"view window ({len(win)} training views): {', '.join(c['name'] for c in win)}")

    # reference candidates: in-scope negatives, in frame and facing in every window view
    g = load_gaussians(fcfg["ply"])
    cand = np.nonzero(neg & seen & in_crop)[0]
    R = quats_to_R(g["quats"][cand]).astype(np.float64)
    k = np.argmin(g["scales"][cand], axis=1)
    nrm = R[np.arange(len(cand)), :, k]                    # column of smallest scale
    centre = xyz[in_crop].mean(0)
    flip = np.einsum("ij,ij->i", nrm, xyz[cand] - centre) < 0
    nrm[flip] *= -1
    cosmax = np.cos(np.radians(cfg["facing_max_deg"]))
    keep = np.ones(len(cand), bool)
    for c in win:
        ok, _, _ = in_frame(xyz[cand], c, near)
        cc = -c["R"].T @ c["t"]
        dv = cc - xyz[cand]
        dv /= np.linalg.norm(dv, axis=1, keepdims=True)
        keep &= ok & (np.einsum("ij,ij->i", nrm, dv) >= cosmax)
    eligible = cand[keep]
    rng = np.random.default_rng(cfg["seed"])
    ref_idx = rng.choice(eligible, min(cfg["reference_n"], len(eligible)), replace=False)
    print(f"reference: {len(cand):,} in-scope L2- candidates, {len(eligible):,} in frame and "
          f"facing (<= {cfg['facing_max_deg']} deg) in all window views, sampled {len(ref_idx):,}")

    groups = {"wire": wire_idx, "layer rest": rest_idx, "truck surface (matched reference)": ref_idx}
    stats, rows = {}, []
    for name, idx in groups.items():
        P = xyz[idx]
        allin = np.ones(len(P), bool)
        for c in win:
            allin &= in_frame(P, c, near)[0]
        P = P[allin]
        s1 = np.zeros((len(P), 3)); s2 = np.zeros((len(P), 3))
        for c in win:
            img = plt.imread(os.path.join(icfg["images"], c["name"])).astype(np.float64) / 255.0
            H, W = img.shape[:2]
            _, u, v = in_frame(P, c, near)
            ui = np.clip(np.round(u * W / c["width"]).astype(int), 0, W - 1)
            vi = np.clip(np.round(v * H / c["height"]).astype(int), 0, H - 1)
            col = img[vi, ui]
            s1 += col; s2 += col ** 2
        n = len(win)
        std = np.sqrt(np.maximum(s2 / n - (s1 / n) ** 2, 0)).mean(axis=1)
        stats[name] = std
        q = np.percentile(std, [25, 50, 75]) if len(std) else [np.nan] * 3
        rows.append(dict(group=name, N=len(idx), N_in_all_window_views=int(allin.sum()),
                         std_p25=q[0], std_median=q[1], std_p75=q[2]))
    print(f"\ncolour std across the same {len(win)} views (RGB mean, 0..1), nearest pixel:")
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4f}".format):
        print(pd.DataFrame(rows).to_string(index=False))

    ref = stats["truck surface (matched reference)"]
    med = float(np.median(ref))
    passed = med <= cfg["control_max_median_std"]
    print(f"\npositive control: matched reference median {med:.4f} vs threshold "
          f"{cfg['control_max_median_std']} -> {'PASS' if passed else 'FAIL'}")
    if not passed:
        print("  method NOT usable to judge floaters here (decided before running)")
    for name in ("wire", "layer rest"):
        if len(stats[name]):
            a = auc_mann_whitney(np.r_[stats[name], ref],
                                 np.r_[np.ones(len(stats[name])), np.zeros(len(ref))].astype(int))[0]
            print(f"  P(colour std of {name} > matched reference) = {a:.4f}")


if __name__ == "__main__":
    main()
