#!/usr/bin/env python3
"""
T3: how much does initialising 3DGS from the reference cloud inflate the
apparent signal of the `unsupported` label?

Splits Gaussians into near-init (within k x median reference spacing of an
init point) and far-init, reports dist_to_reference and the unsupported rate
per group, and scores the T4 features against the label on all Gaussians
and on far-init alone.

AUC is the tie-aware Mann-Whitney statistic (average ranks): view_frac has
only n_views + 1 distinct values, and an argsort ROC would order ties
arbitrarily.

Usage:
    python src/confound.py --config configs/T3_confound.yaml
"""

import argparse
import numpy as np
import pandas as pd
import yaml
from plyfile import PlyData
from scipy.spatial import cKDTree
from scipy.stats import rankdata


def auc_mann_whitney(score, label):
    """P(score_pos > score_neg) + 0.5 P(tie). Higher score = more positive."""
    pos = label.astype(bool)
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan"), n_pos, n_neg
    r = rankdata(score)
    auc = (r[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc), n_pos, n_neg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    fcfg = yaml.safe_load(open(cfg["features_config"]))

    df = pd.read_parquet(fcfg["out"])
    N = len(df)

    v = PlyData.read(cfg["init_ply"])["vertex"]
    init = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    tree = cKDTree(init)
    spacing = float(np.median(tree.query(init, k=2, workers=-1)[0][:, 1]))
    d_init, _ = tree.query(df[["x", "y", "z"]].to_numpy(np.float64), k=1, workers=-1)
    r = cfg["near_init_spacing_mult"] * spacing
    far = d_init > r

    same = np.abs(d_init - df.dist_to_reference.to_numpy()).max()
    print(f"init points N = {len(init):,}; median init spacing = {spacing:.5f}; "
          f"near/far radius = {r:.5f}")
    print(f"max |dist_to_init - dist_to_reference| = {same:.3e}  "
          f"(init cloud == reference cloud, T2 check 5b)")

    print(f"\n[1] groups (N = {N:,})")
    pcts = cfg["dist_pct"]
    rows = []
    for name, m in (("near-init", ~far), ("far-init", far), ("all", np.ones(N, bool))):
        g = df[m]
        q = np.percentile(g.dist_to_reference, pcts) if len(g) else [np.nan] * len(pcts)
        rows.append(dict(group=name, N=len(g), share_pct=len(g) / N * 100,
                         unsupported=int(g.unsupported.sum()),
                         unsupported_pct=g.unsupported.mean() * 100,
                         **{f"dist_p{p}": x for p, x in zip(pcts, q)}))
    t = pd.DataFrame(rows).set_index("group")
    with pd.option_context("display.width", 250, "display.max_columns", None, "display.float_format", "{:.4g}".format):
        print(t)

    print("\n[2] AUC of features against `unsupported` (tie-aware rank AUC)")
    out = []
    for feat, direction in cfg["features"].items():
        s = df[feat].to_numpy(np.float64)
        s = s if direction == "high" else -s
        a_all, p_all, n_all = auc_mann_whitney(s, df.unsupported.to_numpy())
        a_far, p_far, n_far = auc_mann_whitney(s[far], df.unsupported.to_numpy()[far])
        out.append(dict(feature=feat, artefact_if=direction,
                        auc_all=a_all, auc_far=a_far, delta=a_far - a_all,
                        n_pos_all=p_all, n_neg_all=n_all, n_pos_far=p_far, n_neg_far=n_far))
    a = pd.DataFrame(out).set_index("feature")
    with pd.option_context("display.width", 250, "display.max_columns", None, "display.float_format", "{:.4f}".format):
        print(a)


if __name__ == "__main__":
    main()
