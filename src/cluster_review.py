#!/usr/bin/env python3
"""
Cluster the overhead layer's non-wire Gaussians and render each cluster in
the training views where it appears most, for a human to judge tree vs
floater. Writes a judgement sheet with empty judgement columns. Classifies
nothing (AGENTS.md §2).

Usage:
    python src/cluster_review.py --config configs/cluster_review.yaml
"""

import argparse
import itertools
import os
import sys
import numpy as np
import pandas as pd
import yaml
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import load_colmap  # noqa: E402
from align_reference import apply  # noqa: E402
from layer_split import layer_wire_rest  # noqa: E402
from photo_consistency_matched import in_frame  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    scfg = yaml.safe_load(open(cfg["layer_split_config"]))
    icfg = yaml.safe_load(open(scfg["inspect_config"]))
    fcfg = yaml.safe_load(open(icfg["features_config"]))
    acfg = yaml.safe_load(open(icfg["align_config"]))
    proj = fcfg["projection"]

    df = pd.read_parquet(fcfg["out"], columns=["x", "y", "z"])
    xyz = df.to_numpy(np.float64)
    xyz_gt = apply(np.loadtxt(acfg["out_matrix"]), xyz)
    wire_idx, rest_idx = layer_wire_rest(cfg["layer_split_config"])
    P = xyz_gt[rest_idx]

    pairs = cKDTree(P).query_pairs(cfg["link_m"], output_type="ndarray")
    A = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(P), len(P)))
    ncomp, comp = connected_components(A, directed=False)
    sizes = np.bincount(comp)
    order = np.argsort(-sizes)
    big = [c for c in order if sizes[c] >= cfg["min_cluster_size"]]
    shown = big[:cfg["max_clusters"]]
    print(f"non-wire layer Gaussians: {len(P):,}; components (link {cfg['link_m']} m): {ncomp:,}")
    print(f"  >= {cfg['min_cluster_size']} members: {len(big)} clusters, "
          f"{int(sizes[big].sum()):,} Gaussians ({sizes[big].sum() / len(P) * 100:.1f}%)")
    print(f"  shown (largest {cfg['max_clusters']}): {len(shown)} clusters, "
          f"{int(sizes[shown].sum()):,} Gaussians ({sizes[shown].sum() / len(P) * 100:.1f}%)")
    print(f"  fragments (< {cfg['min_cluster_size']}): {int(sizes[sizes < cfg['min_cluster_size']].sum()):,} Gaussians")

    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    os.makedirs(cfg["out_dir"], exist_ok=True)

    # overview: top view with cluster ids
    fig, ax = plt.subplots(figsize=(7.4, 4.3), dpi=200)
    ax.scatter(xyz_gt[wire_idx, 0], xyz_gt[wire_idx, 1], s=1, c="#9CA3AF", lw=0, label="wire (excluded)")
    ax.scatter(P[:, 0], P[:, 1], s=1, c="#DCDCD8", lw=0, label="non-wire layer")
    for i, c in enumerate(shown, 1):
        m = comp == c
        ax.scatter(P[m, 0], P[m, 1], s=2, lw=0)
        ax.annotate(f"C{i}", P[m].mean(0)[:2], fontsize=8, weight="bold")
    ax.set_aspect("equal"); ax.set_xlabel("scan x (m)"); ax.set_ylabel("scan y (m)")
    ax.legend(frameon=False, fontsize=7, markerscale=5)
    fig.tight_layout(); fig.savefig(os.path.join(cfg["out_dir"], "overview.png")); plt.close(fig)

    rows = []
    for i, c in enumerate(shown, 1):
        Q = xyz[rest_idx[comp == c]]
        counts = []
        for cam in cams:
            ok, u, v = in_frame(Q, cam, proj["near_plane"])
            counts.append((int(ok.sum()), cam, u[ok], v[ok]))
        if cfg.get("view_selection", "most_members") == "max_angle":
            # among views with >= min_frac of the cluster in frame, pick the set whose
            # smallest pairwise angle (seen from the cluster centroid) is largest
            ctr3 = Q.mean(0)
            cand = [r for r in counts if r[0] >= cfg["min_frac_in_frame"] * len(Q)]
            dirs = []
            for r in cand:
                cc = -r[1]["R"].T @ r[1]["t"]
                dv = cc - ctr3
                dirs.append(dv / np.linalg.norm(dv))
            dirs = np.array(dirs)
            k = min(cfg["views_per_cluster"], len(cand))
            best, best_min = None, -1.0
            for combo in itertools.combinations(range(len(cand)), k):
                if k < 2:
                    best = combo; break
                ang = min(np.degrees(np.arccos(np.clip(dirs[a] @ dirs[b], -1, 1)))
                          for a, b in itertools.combinations(combo, 2))
                if ang > best_min:
                    best, best_min = combo, ang
            top = [cand[i] for i in best] if best is not None else []
            angles = {}
            for a in best or ():
                others = [np.degrees(np.arccos(np.clip(dirs[a] @ dirs[b], -1, 1)))
                          for b in best if b != a]
                angles[cand[a][1]["name"]] = min(others) if others else float("nan")
            print(f"  C{i}: {len(cand)} candidate views (>= {cfg['min_frac_in_frame']:.0%} in frame); "
                  f"chosen min pairwise angle {best_min:.1f} deg" if k >= 2 else
                  f"  C{i}: {len(cand)} candidate view(s); no angle comparison possible")
        else:
            counts.sort(key=lambda r: -r[0])
            top = [r for r in counts[:cfg["views_per_cluster"]] if r[0] > 0]
            angles = {}
        fig, axes = plt.subplots(len(top), 3, figsize=(14, 3.6 * len(top)), dpi=110,
                                 gridspec_kw=dict(width_ratios=[1.6, 1, 1]), squeeze=False)
        for row, (n, cam, u, v) in zip(axes, top):
            img = plt.imread(os.path.join(icfg["images"], cam["name"]))
            H, W = img.shape[:2]
            u, v = u * W / cam["width"], v * H / cam["height"]
            mg = cfg["zoom_margin_px"]
            x0, x1 = np.percentile(u, [2, 98]); y0, y1 = np.percentile(v, [2, 98])
            x0, x1 = int(max(x0 - mg, 0)), int(min(x1 + mg, W)); y0, y1 = int(max(y0 - mg, 0)), int(min(y1 + mg, H))
            row[0].imshow(img); row[0].scatter(u, v, s=1, c="#E0532F", lw=0)
            row[0].add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#2E7D6E", lw=1.2))
            extra = (f"; nearest other chosen view {angles[cam['name']]:.0f} deg away"
                     if cam["name"] in angles and not np.isnan(angles[cam["name"]]) else "")
            row[0].set_title(f"C{i} in {cam['name']}: {n} of {len(Q)} in frame{extra}", fontsize=9)
            row[1].imshow(img[y0:y1, x0:x1]); row[1].set_title("zoom, unmarked", fontsize=9)
            row[2].imshow(img[y0:y1, x0:x1]); row[2].scatter(u - x0, v - y0, s=3, c="#E0532F", lw=0)
            row[2].set_title("zoom, marked", fontsize=9)
            for a in row:
                a.set_xticks([]); a.set_yticks([])
        fig.tight_layout(); fig.savefig(os.path.join(cfg["out_dir"], f"C{i:02d}.png")); plt.close(fig)
        ctr = P[comp == c].mean(0)
        rows.append(dict(cluster=f"C{i}", n_gaussians=int(sizes[c]),
                         centre_scan_x=round(ctr[0], 3), centre_scan_y=round(ctr[1], 3),
                         centre_scan_z=round(ctr[2], 3),
                         views=" ".join(r[1]["name"] for r in top),
                         judgement="", judged_by="", date="", note=""))
        print(f"     C{i}: {sizes[c]:,} Gaussians, views {rows[-1]['views']}")

    if os.path.exists(cfg["sheet"]):
        print(f"\n{cfg['sheet']} exists; not overwritten")
    else:
        pd.DataFrame(rows).to_csv(cfg["sheet"], index=False)
        print(f"\nwrote judgement sheet {cfg['sheet']} (judgement columns empty)")


if __name__ == "__main__":
    main()
