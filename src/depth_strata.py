#!/usr/bin/env python3
"""
Step 1 of the contrib_ratio follow-up: AUC of each feature against
`unsupported` within strata of camera depth, so distance from the cameras
is held roughly fixed.

Depth = mean camera-space depth over the views that see the Gaussian,
from the same per-view pass as src/diagnose_contrib_ratio.py.

Usage:
    python src/depth_strata.py --config configs/depth_strata.yaml
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_features import load_gaussians, load_colmap, select_views  # noqa: E402
from confound import auc_mann_whitney  # noqa: E402
from diagnose_contrib_ratio import per_view_geometry  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))
    proj = fcfg["projection"]

    df = pd.read_parquet(fcfg["out"])
    g = load_gaussians(fcfg["ply"])
    cams, _ = load_colmap(fcfg["colmap"], proj["train_max_width"], fcfg["eval_holdout"])
    cams = select_views(cams, fcfg["max_views"])
    acc = per_view_geometry(g, cams, proj)
    assert np.array_equal(acc["seen_n"], df.view_count.to_numpy())

    vc = df.view_count.to_numpy()
    seen = vc > 0
    depth = np.full(len(df), np.nan)
    depth[seen] = acc["z_sum"][seen] / vc[seen]
    d = df[seen].assign(depth=depth[seen])
    print(f"N = {len(df):,}; seen by >= 1 view = {len(d):,}; "
          f"excluded (no depth) = {int((~seen).sum()):,}")

    edges = np.quantile(d.depth, np.linspace(0, 1, cfg["n_strata"] + 1))
    d["stratum"] = np.clip(np.searchsorted(edges, d.depth, side="right") - 1,
                           0, cfg["n_strata"] - 1)
    y = d.unsupported.to_numpy()
    feats = cfg["features"]

    def scores(sub, f):
        s = sub[f].to_numpy(np.float64)
        return s if feats[f] == "high" else -s

    pooled = {f: auc_mann_whitney(scores(d, f), y)[0] for f in feats}

    rows = []
    for k in range(cfg["n_strata"]):
        sub = d[d.stratum == k]
        ys = sub.unsupported.to_numpy()
        npos, nneg = int(ys.sum()), int(len(ys) - ys.sum())
        row = dict(stratum=k + 1, depth_lo=edges[k], depth_hi=edges[k + 1], N=len(sub),
                   unsup_pct=ys.mean() * 100, n_pos=npos, n_neg=nneg)
        ok = min(npos, nneg) >= cfg["min_per_class"]
        for f in feats:
            row[f] = auc_mann_whitney(scores(sub, f), ys)[0] if ok else np.nan
        rows.append(row)
    t = pd.DataFrame(rows)

    used = t.dropna(subset=list(feats))
    w = used.N
    print(f"\nstrata: {cfg['n_strata']} equal-count bins of mean camera depth; "
          f"used {len(used)} (min {cfg['min_per_class']} per class), "
          f"covering {int(w.sum()):,} Gaussians")
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4g}".format):
        print(t.to_string(index=False))

    print("\nAUC pooled vs within depth strata (N-weighted mean over used strata):")
    summ = []
    for f in feats:
        within = float((used[f] * w).sum() / w.sum())
        summ.append(dict(feature=f, artefact_if=feats[f], auc_pooled=pooled[f],
                         auc_within_depth=within, delta=within - pooled[f],
                         strata_below_0_5=int((used[f] < 0.5).sum()),
                         min=used[f].min(), max=used[f].max()))
    with pd.option_context("display.width", 250, "display.max_columns", None,
                           "display.float_format", "{:.4f}".format):
        print(pd.DataFrame(summ).to_string(index=False))


if __name__ == "__main__":
    main()
