#!/usr/bin/env python3
"""
Diagnose the T3 finding that contrib_ratio runs opposite to the hypothesis.

Re-projects one view at a time with the T1 code (so the "sees it" set is
identical) and tests:

  A. opacity cancels: contrib_ratio recomputed from area alone equals the
     T1 column, so the ratio is pure camera geometry
  B. bound: contrib_ratio <= view_count, so few-view Gaussians cannot score high
  C. AUC within view_count strata, removing that coupling
  D. how much a distance-only proxy (max/mean of 1/z^2) explains

Diagnosis only: nothing in the feature table, label or thresholds changes.

Usage:
    python src/diagnose_contrib_ratio.py --config configs/diag_contrib_ratio.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import (  # noqa: E402
    load_gaussians, covariance_3d, evidential_features_cpu, load_colmap, select_views,
)
from confound import auc_mann_whitney  # noqa: E402


def per_view_geometry(g, cams, proj):
    """
    Per-view footprint area (opacity = 1) and camera depth, accumulated over
    the views that see each Gaussian, with the T1 projection code so the
    "sees it" set is identical. One [N] buffer each (AGENTS.md §7).
    """
    N = len(g["xyz"])
    cov3d = covariance_3d(g)
    xyz = g["xyz"].astype(np.float64)
    area_sum = np.zeros(N)
    area_max = np.zeros(N)
    w_sum = np.zeros(N)          # sum of 1/z^2 over seeing views
    w_max = np.zeros(N)
    z_sum = np.zeros(N)
    seen_n = np.zeros(N, np.int32)
    ones = dict(g, opacity=np.ones(N, np.float32))
    for cam in tqdm(cams, desc="views"):
        ev = evidential_features_cpu(ones, cov3d, [cam], proj)   # opacity = 1 -> cov_sum = area
        seen = ev.view_count.to_numpy() > 0
        area = ev.cov_sum.to_numpy()
        z = xyz @ cam["R"][2] + cam["t"][2]
        w = np.where(seen, 1.0 / np.maximum(z, 1e-9) ** 2, 0.0)
        area_sum += area
        np.maximum(area_max, area, out=area_max)
        w_sum += w
        np.maximum(w_max, w, out=w_max)
        z_sum += np.where(seen, z, 0.0)
        seen_n += seen
    return dict(area_sum=area_sum, area_max=area_max, w_sum=w_sum, w_max=w_max,
                z_sum=z_sum, seen_n=seen_n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))
    proj = fcfg["projection"]

    df = pd.read_parquet(fcfg["out"])
    y = df.unsupported.to_numpy()
    g = load_gaussians(fcfg["ply"])
    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    cams = select_views(cams, fcfg["max_views"])
    N = len(df)
    acc = per_view_geometry(g, cams, proj)
    area_sum, area_max, w_sum, w_max, z_sum, seen_n = (
        acc[k] for k in ("area_sum", "area_max", "w_sum", "w_max", "z_sum", "seen_n"))

    vc = df.view_count.to_numpy()
    cr = df.contrib_ratio.to_numpy()
    assert np.array_equal(seen_n, vc), "re-projection disagrees with T1 view_count"
    n = np.maximum(vc, 1)

    print(f"N = {N:,}; views = {len(cams)}; unsupported = {int(y.sum()):,}")

    # A ---------------------------------------------------------------
    cr_area = area_max / (area_sum / n + 1e-9)
    seen = vc > 0
    rel = np.abs(cr_area[seen] - cr[seen]) / np.maximum(cr[seen], 1e-9)
    print("\n[A] opacity cancels out of contrib_ratio")
    print(f"  ratio recomputed from area only vs T1 column (N seen = {seen.sum():,}): "
          f"max relative diff {rel.max():.3e}, median {np.median(rel):.3e}")

    # B ---------------------------------------------------------------
    over = int((cr > vc + 1e-4).sum())
    rho_vc = spearmanr(cr, vc).statistic
    print("\n[B] contrib_ratio <= view_count (max of n values <= n x their mean)")
    print(f"  Gaussians with contrib_ratio > view_count: {over:,} of {N:,}")
    print(f"  Gaussians seen by exactly 1 view (ratio forced to 1): {int((vc == 1).sum()):,}")
    for lab, name in ((1, "unsupported"), (0, "supported")):
        m = y == lab
        print(f"  {name:<11} N = {m.sum():,}: median view_count {np.median(vc[m]):.0f}, "
              f"median contrib_ratio {np.median(cr[m]):.3f}")
    print(f"  Spearman(contrib_ratio, view_count) = {rho_vc:.4f}")

    # C ---------------------------------------------------------------
    score = cr if cfg["direction"] == "high" else -cr
    a_all, _, _ = auc_mann_whitney(score, y)
    rows = []
    for v in np.unique(vc):
        m = vc == v
        npos, nneg = int(y[m].sum()), int((1 - y[m]).sum())
        if v < 2 or min(npos, nneg) < cfg["min_per_class"]:
            continue
        a, _, _ = auc_mann_whitney(score[m], y[m])
        rows.append((int(v), npos, nneg, a))
    st = pd.DataFrame(rows, columns=["view_count", "n_pos", "n_neg", "auc"])
    w = st.n_pos + st.n_neg
    a_strat = float((st.auc * w).sum() / w.sum())
    print(f"\n[C] AUC within view_count strata (min {cfg['min_per_class']} per class, v >= 2)")
    print(f"  pooled AUC (all N) = {a_all:.4f}")
    print(f"  strata used: {len(st)} covering {int(w.sum()):,} Gaussians "
          f"({w.sum() / N * 100:.1f}%)")
    print(f"  N-weighted mean within-stratum AUC = {a_strat:.4f}; "
          f"strata with AUC < 0.5: {(st.auc < 0.5).sum()} of {len(st)}")
    print(f"  within-stratum AUC range: {st.auc.min():.4f} .. {st.auc.max():.4f}")
    with pd.option_context("display.max_rows", None, "display.float_format", "{:.4f}".format):
        print(st.to_string(index=False))

    # D ---------------------------------------------------------------
    dist_ratio = np.where(seen, w_max / (w_sum / n + 1e-300), 0.0)
    mean_z = np.where(seen, z_sum / n, np.nan)
    rho_d = spearmanr(cr[seen], dist_ratio[seen]).statistic
    a_d, _, _ = auc_mann_whitney(dist_ratio, y)
    resid = np.where(seen, cr / np.maximum(dist_ratio, 1e-9), 0.0)
    a_r, _, _ = auc_mann_whitney(resid, y)
    print("\n[D] distance-only proxy dist_ratio = max(1/z^2) / mean(1/z^2) over seeing views")
    print(f"  Spearman(contrib_ratio, dist_ratio), N seen = {seen.sum():,}: {rho_d:.4f}")
    print(f"  AUC(dist_ratio, high = artefact)              = {a_d:.4f}")
    print(f"  AUC(contrib_ratio / dist_ratio, high = artefact) = {a_r:.4f}")
    for lab, name in ((1, "unsupported"), (0, "supported")):
        m = (y == lab) & seen
        print(f"  {name:<11} N = {m.sum():,}: median mean-depth {np.nanmedian(mean_z[m]):.3f} units, "
              f"median dist_ratio {np.median(dist_ratio[m]):.3f}")


if __name__ == "__main__":
    main()
