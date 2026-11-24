#!/usr/bin/env python3
"""
Pre-registered extra per-Gaussian signals (configs/protocol_v1.yaml,
`new_signals` and T7), written to a separate parquet so the T1 table and its
reproducibility are untouched.

Per Gaussian, over the training views that see it (same "sees it" test as
T1 — asserted against the T1 view_count):

  mean_depth        mean camera-space depth           (depth strata)
  max_parallax_deg  largest angle between the rays from the centre to any
                    two seeing cameras                (0 if seen by < 2)
  angular_spread    1 - |mean unit viewing direction| (T7; 0 = all rays
                    parallel, -> 1 = spread around)
  contrib_F1        max_v area_v / sum_v area_v       (opacity cancels, as
                    in contrib_ratio; no view_count cap)
  contrib_F2        max/mean of area_v * z_v^2 / (fx_v fy_v): footprint
                    converted back to scene units^2, removing distance
  sh_rest_ratio     ||SH coefficients of degree >= 1|| / ||SH DC||

Memory: one [N] buffer per quantity plus a uint64 bitmask of seeing views
per Gaussian (max 64 views); never [n_views, N] (AGENTS.md §7).

Usage:
    python src/extra_signals.py --config configs/T1_<scene>.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import (  # noqa: E402
    load_gaussians, covariance_3d, evidential_features_cpu, load_colmap, select_views,
)


def sh_rest_ratio(ply_path):
    v = PlyData.read(ply_path)["vertex"]
    names = [p.name for p in v.properties]
    rest = sorted((n for n in names if n.startswith("f_rest_")), key=lambda n: int(n[7:]))
    dc2 = sum(np.asarray(v[f"f_dc_{i}"], np.float64) ** 2 for i in range(3))
    r2 = np.zeros(len(dc2))
    for n in rest:
        r2 += np.asarray(v[n], np.float64) ** 2
    return np.sqrt(r2) / (np.sqrt(dc2) + 1e-9), len(rest)


def cam_center(cam):
    return -cam["R"].T @ cam["t"]


def unit_dirs(xyz, c):
    d = (c[None, :] - xyz).astype(np.float32)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-12
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    proj = cfg["projection"]

    t1 = pd.read_parquet(cfg["out"], columns=["view_count"])
    g = load_gaussians(cfg["ply"])
    N = len(g["xyz"])
    cams, _ = load_colmap(cfg["colmap"], proj["train_max_width"], cfg["eval_holdout"],
                          proj.get("train_height"))
    cams = select_views(cams, cfg["max_views"])
    V = len(cams)
    assert V <= 64, "bitmask holds at most 64 views"
    print(f"{N:,} Gaussians, {V} views")

    cov3d = covariance_3d(g)
    xyz = g["xyz"].astype(np.float64)
    ones = dict(g, opacity=np.ones(N, np.float32))

    seen_n = np.zeros(N, np.int32)
    mask = np.zeros(N, np.uint64)
    z_sum = np.zeros(N)
    a_sum = np.zeros(N)
    a_max = np.zeros(N)
    w_sum = np.zeros(N)          # world-unit footprint, for F2
    w_max = np.zeros(N)
    dir_sum = np.zeros((N, 3))

    for k, cam in enumerate(tqdm(cams, desc="views")):
        ev = evidential_features_cpu(ones, cov3d, [cam], proj)
        seen = ev.view_count.to_numpy() > 0
        area = ev.cov_sum.to_numpy()                       # opacity = 1 -> pixel area
        z = xyz @ cam["R"][2] + cam["t"][2]
        world = np.where(seen, area * z * z / (cam["fx"] * cam["fy"]), 0.0)

        seen_n += seen
        mask[seen] |= np.uint64(1) << np.uint64(k)
        z_sum += np.where(seen, z, 0.0)
        a_sum += area
        np.maximum(a_max, area, out=a_max)
        w_sum += world
        np.maximum(w_max, world, out=w_max)
        dir_sum[seen] += unit_dirs(xyz[seen], cam_center(cam))

    t1_vc = t1.view_count.to_numpy()
    assert np.array_equal(seen_n, t1_vc), "seeing set differs from T1 view_count"
    print("seeing set identical to T1 view_count: yes")

    # max parallax: min cosine over all view pairs that both see the Gaussian
    centers = [cam_center(c) for c in cams]
    min_cos = np.ones(N, np.float32)
    for i in tqdm(range(V - 1), desc="parallax"):
        bi = (mask >> np.uint64(i)) & np.uint64(1) == 1
        if not bi.any():
            continue
        idx_i = np.nonzero(bi)[0]
        di = unit_dirs(xyz[idx_i], centers[i])
        for j in range(i + 1, V):
            bj = ((mask[idx_i] >> np.uint64(j)) & np.uint64(1)) == 1
            if not bj.any():
                continue
            sel = idx_i[bj]
            c = np.einsum("ij,ij->i", di[bj], unit_dirs(xyz[sel], centers[j]))
            min_cos[sel] = np.minimum(min_cos[sel], c)
    max_par = np.degrees(np.arccos(np.clip(min_cos, -1.0, 1.0)))
    max_par[seen_n < 2] = 0.0

    has = seen_n > 0
    nz = np.maximum(seen_n, 1)
    mean_depth = np.where(has, z_sum / nz, np.nan)
    spread = np.where(has, 1.0 - np.linalg.norm(dir_sum, axis=1) / nz, np.nan)
    F1 = np.where(has, a_max / np.maximum(a_sum, 1e-12), np.nan)
    F2 = np.where(has, w_max / np.maximum(w_sum / nz, 1e-30), np.nan)
    shr, n_rest = sh_rest_ratio(cfg["ply"])
    print(f"SH rest coefficients read: {n_rest}")

    out = pd.DataFrame({
        "gaussian_id": np.arange(N),
        "mean_depth": mean_depth,
        "max_parallax_deg": max_par.astype(np.float64),
        "angular_spread": spread,
        "contrib_F1": F1,
        "contrib_F2": F2,
        "sh_rest_ratio": shr,
    })
    path = cfg["out"].replace(".parquet", "_extra.parquet")
    out.to_parquet(path, index=False)
    print(f"wrote {path} ({len(out):,} rows)")
    with pd.option_context("display.width", 200, "display.max_columns", None,
                           "display.float_format", "{:.4g}".format):
        print(out.drop(columns="gaussian_id").describe().T)
    print(f"unseen (NaN depth/spread/F1/F2): {int((~has).sum()):,}")


if __name__ == "__main__":
    main()
