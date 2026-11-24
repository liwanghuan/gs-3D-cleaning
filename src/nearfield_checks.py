#!/usr/bin/env python3
"""
Two checks before choosing a near-field label (diagnosis only):

  1. Does the official T&T crop cover the near field? Camera centres inside
     the crop, and the share of Gaussians inside the crop per depth decile.
  2. In each depth decile, how many in-crop Gaussians sit on the laser-scan
     surface, just off it, or far from it?

Uses the estimated alignment from src/align_reference.py; labels nothing.

Usage:
    python src/nearfield_checks.py --config configs/nearfield_checks.yaml
"""

import argparse
import json
import os
import sys
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import load_gaussians, load_colmap, select_views  # noqa: E402
from diagnose_contrib_ratio import per_view_geometry  # noqa: E402
from align_reference import crop_mask, apply  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))
    acfg = yaml.safe_load(open(cfg["align_config"]))
    proj = fcfg["projection"]

    df = pd.read_parquet(fcfg["out"], columns=["view_count", "unsupported"])
    g = load_gaussians(fcfg["ply"])
    all_cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    cams = select_views(all_cams, fcfg["max_views"])
    T = np.loadtxt(acfg["out_matrix"])
    crop = json.load(open(acfg["tnt_crop"]))

    # depth deciles, exactly as depth_strata.py
    acc = per_view_geometry(g, cams, proj)
    assert np.array_equal(acc["seen_n"], df.view_count.to_numpy())
    vc = df.view_count.to_numpy()
    seen = vc > 0
    depth = np.full(len(df), np.nan)
    depth[seen] = acc["z_sum"][seen] / vc[seen]
    edges = np.quantile(depth[seen], np.linspace(0, 1, cfg["n_strata"] + 1))
    stratum = np.full(len(df), -1)
    stratum[seen] = np.clip(np.searchsorted(edges, depth[seen], side="right") - 1,
                            0, cfg["n_strata"] - 1)

    # ---- check 1: crop coverage
    centres = np.stack([-c["R"].T @ c["t"] for c in all_cams])
    c_gt = apply(T, centres)
    cam_in = crop_mask(c_gt, crop)
    z_lo, z_hi = crop["axis_min"], crop["axis_max"]
    print(f"[1] crop coverage")
    print(f"  training cameras inside the crop: {int(cam_in.sum())} of {len(c_gt)}")
    print(f"  camera centre z (scan frame): {c_gt[:, 2].min():.3f} .. {c_gt[:, 2].max():.3f}; "
          f"crop z range {z_lo:.3f} .. {z_hi:.3f}")

    xyz_gt = apply(T, g["xyz"].astype(np.float64))
    g_in = crop_mask(xyz_gt, crop)
    print(f"  Gaussians inside the crop: {int(g_in.sum()):,} of {len(df):,} "
          f"({g_in.mean() * 100:.2f}%)")

    # ---- check 2: distance to scan, in-crop Gaussians
    v = PlyData.read(acfg["tnt_gt"])["vertex"]
    scan = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    scan = scan[crop_mask(scan, crop)]
    d = np.full(len(df), np.nan)
    d[g_in], _ = cKDTree(scan).query(xyz_gt[g_in], k=1, workers=-1)

    on, far = cfg["on_surface_m"], cfg["far_m"]
    y = df.unsupported.to_numpy()
    rows = []
    for k in range(cfg["n_strata"]):
        m = stratum == k
        mi = m & g_in
        dk = d[mi]
        rows.append(dict(
            stratum=k + 1, depth_lo=edges[k], depth_hi=edges[k + 1], N=int(m.sum()),
            in_crop_pct=mi.sum() / m.sum() * 100, N_in_crop=int(mi.sum()),
            on_surface_pct=np.mean(dk <= on) * 100 if len(dk) else np.nan,
            off_surface_pct=np.mean((dk > on) & (dk <= far)) * 100 if len(dk) else np.nan,
            far_pct=np.mean(dk > far) * 100 if len(dk) else np.nan,
            L1_unsup_in_crop_pct=y[mi].mean() * 100 if len(dk) else np.nan,
        ))
    t = pd.DataFrame(rows)
    print(f"\n[2] in-crop Gaussians by depth decile; distance to scan bands: "
          f"on <= {on} m, off {on}..{far} m, far > {far} m")
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4g}".format):
        print(t.to_string(index=False))

    mi = g_in & seen
    both = mi & (d > far) & (y == 1)
    print(f"\n  all in-crop seen Gaussians N = {int(mi.sum()):,}: "
          f"far from scan {np.mean(d[mi] > far) * 100:.2f}%, "
          f"L1 unsupported {y[mi].mean() * 100:.2f}%, "
          f"both {both.sum() / mi.sum() * 100:.2f}%")
    far_m = mi & (d > far)
    print(f"  of the far-from-scan Gaussians (N = {int(far_m.sum()):,}), "
          f"L1 calls {y[far_m].mean() * 100:.2f}% unsupported")

    # L1 agreement with "far from scan" inside the crop (diagnostic, not a label choice)
    l1 = mi & (y == 1)
    tp = int(both.sum())
    print(f"  L1 vs far-from-scan inside crop: L1 positives {int(l1.sum()):,}, "
          f"scan-far {int(far_m.sum()):,}, both {tp:,}; "
          f"precision {tp / max(l1.sum(), 1) * 100:.2f}%, recall {tp / max(far_m.sum(), 1) * 100:.2f}%")


if __name__ == "__main__":
    main()
