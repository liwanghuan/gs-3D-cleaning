#!/usr/bin/env python3
"""
Show a human where the T4 overhead layer projects in the training images.
Images only: no metric, no classification (AGENTS.md §2).

For the n training views where most layer Gaussians land inside the image,
writes one PNG per view: full image with the layer marked, a zoom without
marks, and the same zoom with marks. No occlusion test: a marked point may
be hidden behind the truck in that view.

Usage:
    python src/inspect_layer.py --config configs/inspect_layer.yaml
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))
    lcfg = yaml.safe_load(open(cfg["label_config"]))
    acfg = yaml.safe_load(open(cfg["align_config"]))
    proj = fcfg["projection"]

    df = pd.read_parquet(fcfg["out"], columns=["x", "y", "z", "view_count"])
    lab = pd.read_parquet(lcfg["out"])
    T = np.loadtxt(acfg["out_matrix"])
    xyz = df[["x", "y", "z"]].to_numpy(np.float64)
    zs = apply(T, xyz)[:, 2]
    pos = (lab.unsupported_scan == 1).to_numpy(dtype=bool, na_value=False)
    layer = pos & (df.view_count.to_numpy() > 0) & (zs > cfg["layer_min_scan_z"])
    P = xyz[layer]
    print(f"layer Gaussians: {len(P):,} (L2+, seen, scan z > {cfg['layer_min_scan_z']})")

    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    rows = []
    for c in cams:
        pc = P @ c["R"].T + c["t"]
        front = pc[:, 2] > proj["near_plane"]
        u = c["fx"] * pc[:, 0] / pc[:, 2] + c["cx"]
        v = c["fy"] * pc[:, 1] / pc[:, 2] + c["cy"]
        inside = front & (u >= 0) & (u < c["width"]) & (v >= 0) & (v < c["height"])
        rows.append((c["name"], int(inside.sum()), u[inside], v[inside]))
    rows.sort(key=lambda r: -r[1])
    print(f"camera model {cams[0]['width']}x{cams[0]['height']} px; "
          f"published image {plt.imread(os.path.join(cfg['images'], cams[0]['name'])).shape[1::-1]}")
    print(f"training views with >= 1 layer Gaussian in frame: "
          f"{sum(r[1] > 0 for r in rows)} of {len(rows)}")

    os.makedirs(cfg["out_dir"], exist_ok=True)
    m = cfg["zoom_margin_px"]
    W0, H0 = cams[0]["width"], cams[0]["height"]
    for name, n, u, v in rows[:cfg["n_views"]]:
        img = plt.imread(os.path.join(cfg["images"], name))
        H, W = img.shape[:2]
        # published images are downsampled relative to the COLMAP cameras
        u, v = u * W / W0, v * H / H0
        x0, x1 = np.percentile(u, [2, 98]); y0, y1 = np.percentile(v, [2, 98])
        x0, x1 = int(max(x0 - m, 0)), int(min(x1 + m, W)); y0, y1 = int(max(y0 - m, 0)), int(min(y1 + m, H))
        fig, ax = plt.subplots(1, 3, figsize=(16, 4.6), dpi=130,
                               gridspec_kw=dict(width_ratios=[1.6, 1, 1]))
        ax[0].imshow(img); ax[0].scatter(u, v, s=0.4, c="#E0532F", lw=0)
        ax[0].add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#2E7D6E", lw=1.2))
        ax[0].set_title(f"{name}: {n:,} layer Gaussians in frame (no occlusion test)", fontsize=9)
        ax[1].imshow(img[y0:y1, x0:x1]); ax[1].set_title("zoom, unmarked", fontsize=9)
        ax[2].imshow(img[y0:y1, x0:x1])
        ax[2].scatter(u - x0, v - y0, s=0.8, c="#E0532F", lw=0); ax[2].set_title("zoom, layer marked", fontsize=9)
        for a in ax:
            a.set_xticks([]); a.set_yticks([])
        fig.tight_layout()
        out = os.path.join(cfg["out_dir"], f"{os.path.splitext(name)[0]}.png")
        fig.savefig(out); plt.close(fig)
        print(f"  {name}: {n:,} in frame -> {out}")


if __name__ == "__main__":
    main()
