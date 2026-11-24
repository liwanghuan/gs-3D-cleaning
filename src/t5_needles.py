#!/usr/bin/env python3
"""
Protocol v1, T5 (needles) for one scene, option B (configs/protocol_v1.yaml
`needles_T5`):

  subset    = top `top_pct` % of ALL Gaussians by anisotropy
  near      = dist_to_reference <= near_spacing_mult x median COLMAP spacing
  far       = dist_to_reference >  far_spacing_mult  x median COLMAP spacing
  ambiguous = in between

The ambiguous fraction (with N) is the headline: the share of the most
needle-like Gaussians that distance to verified geometry cannot place.
`sample_n` ambiguous Gaussians (seed fixed) are dumped with raw attributes
for later human inspection. They are NOT classified here (AGENTS.md §2).

Usage:
    python src/t5_needles.py --config configs/T1_<scene>.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colmap_io import read_sparse  # noqa: E402
from make_plots import FIGSIZE, DPI, ACCENT, VERIF, MUTED, RULE  # noqa: E402

PROTOCOL = "configs/protocol_v1.yaml"
SAMPLE_COLS = ["gaussian_id", "x", "y", "z", "opacity", "scale_max", "scale_min",
               "anisotropy", "planarity", "volume", "sh_dc_norm", "isolation",
               "view_count", "dist_to_reference", "dist_in_spacing", "max_parallax_deg"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    T = yaml.safe_load(open(PROTOCOL))["needles_T5"]
    assert T["band"] == "spacing_multiples"
    scene = cfg["scene"]

    df = pd.read_parquet(cfg["out"])
    ex = pd.read_parquet(cfg["out"].replace(".parquet", "_extra.parquet"),
                         columns=["max_parallax_deg"])
    df["max_parallax_deg"] = ex.max_parallax_deg.to_numpy()
    N = len(df)

    _, _, (pts, _, _) = read_sparse(cfg["colmap"])
    pts = pts.astype(np.float32)          # as in extract_features.load_colmap
    spacing = float(np.median(cKDTree(pts).query(pts, k=2, workers=-1)[0][:, 1]))
    near_r = T["near_spacing_mult"] * spacing
    far_r = T["far_spacing_mult"] * spacing
    # consistency with the label: far == L1 unsupported
    tau = cfg["unsupported_spacing_mult"] * spacing
    assert np.isclose(far_r, tau), "far bound must equal the L1 threshold"

    thr = np.percentile(df.anisotropy, 100 - T["top_pct"])
    sub = df[df.anisotropy >= thr].copy()
    sub["dist_in_spacing"] = sub.dist_to_reference / spacing
    d = sub.dist_to_reference.to_numpy()
    near, far = d <= near_r, d > far_r
    amb = ~near & ~far
    n = len(sub)
    assert np.array_equal(far, sub.unsupported.to_numpy().astype(bool))

    print(f"[{scene}] N = {N:,}; top {T['top_pct']}% by anisotropy: n = {n:,} "
          f"(anisotropy >= {thr:.4g}); median COLMAP spacing = {spacing:.5g}")
    print(f"  near  (<= {T['near_spacing_mult']} x spacing = {near_r:.4g}): "
          f"{int(near.sum()):,} ({near.mean() * 100:.2f}%)")
    print(f"  ambiguous                              : "
          f"{int(amb.sum()):,} ({amb.mean() * 100:.2f}%)")
    print(f"  far   (>  {T['far_spacing_mult']} x spacing = {far_r:.4g}, == L1+): "
          f"{int(far.sum()):,} ({far.mean() * 100:.2f}%)")
    print(f"  unseen by all 40 views within the subset: {int((sub.view_count == 0).sum()):,}")
    for name, m in (("near", near), ("ambiguous", amb), ("far", far)):
        g = sub[m]
        if len(g):
            print(f"  {name:<9} median: view_count {g.view_count.median():.0f}, "
                  f"isolation {g.isolation.median():.3f}, opacity {g.opacity.median():.3f}, "
                  f"anisotropy {g.anisotropy.median():.1f}")

    os.makedirs("out/reports/protocol_v1", exist_ok=True)
    pd.DataFrame([dict(scene=scene, N=N, top_pct=T["top_pct"], n_subset=n,
                       anisotropy_thr=thr, spacing=spacing, near_r=near_r, far_r=far_r,
                       n_near=int(near.sum()), n_amb=int(amb.sum()), n_far=int(far.sum()),
                       pct_near=near.mean() * 100, pct_amb=amb.mean() * 100,
                       pct_far=far.mean() * 100,
                       n_unseen=int((sub.view_count == 0).sum()))]
                 ).to_csv(f"out/reports/protocol_v1/{scene}_T5.csv", index=False)

    pool = sub[amb]
    k = min(T["sample_n"], len(pool))
    samp = pool.sample(n=k, random_state=T["sample_seed"])[SAMPLE_COLS]
    samp.insert(0, "scene", scene)
    samp.to_csv(f"out/reports/protocol_v1/{scene}_T5_sample.csv", index=False)
    print(f"  sample: {k} ambiguous Gaussians -> out/reports/protocol_v1/{scene}_T5_sample.csv "
          f"(not classified)")

    os.makedirs("out/figures/protocol_v1", exist_ok=True)
    x = np.maximum(sub.dist_in_spacing.to_numpy(), 1e-3)
    a = sub.anisotropy.to_numpy()
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.axvspan(T["near_spacing_mult"], T["far_spacing_mult"], color=RULE, alpha=0.35, zorder=0)
    for m, c, lab in ((near, VERIF, "near verified point"), (amb, MUTED, "ambiguous"),
                      (far, ACCENT, "far (L1 unsupported)")):
        ax.scatter(x[m], a[m], s=2, c=c, alpha=0.35, lw=0,
                   label=f"{lab}: {m.mean() * 100:.1f}% (N={int(m.sum()):,})")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("distance to nearest COLMAP point  (× median spacing, log)")
    ax.set_ylabel("anisotropy  $s_{max}/s_{min}$  (log)")
    ax.set_title(f"{scene}: top {T['top_pct']:g}% most anisotropic, n = {n:,}",
                 fontsize=11, color=MUTED, loc="left")
    ax.legend(frameon=False, fontsize=9, markerscale=4, loc="upper left")
    fig.tight_layout()
    fig.savefig(f"out/figures/protocol_v1/{scene}_2_needle_split.png", dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
