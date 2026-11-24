#!/usr/bin/env python3
"""
T8 cross-scene table (protocol v1). Reads out/reports/protocol_v1/<scene>_auc.csv,
_T6.csv and _T7.csv for every scene in the protocol and prints markdown tables:
scenes as rows, AUC per feature as columns (within-depth and pooled), plus the
pre-registered stability verdict: a feature is "stable" only if its
within-depth AUC is on the same side of 0.5 on every scene.

Usage:
    python src/cross_scene.py > out/reports/protocol_v1/T8_tables.md
"""

import numpy as np
import pandas as pd
import yaml

PROTOCOL = "configs/protocol_v1.yaml"
D = "out/reports/protocol_v1"


def md(t, fmt="{:.3f}"):
    cols = list(t.columns)
    out = ["| " + " | ".join([t.index.name or ""] + cols) + " |",
           "|" + "---|" * (len(cols) + 1)]
    for i, r in t.iterrows():
        cells = [fmt.format(v) if isinstance(v, (float, np.floating)) and not np.isnan(v)
                 else ("—" if isinstance(v, float) else str(v)) for v in r]
        out.append("| " + " | ".join([str(i)] + cells) + " |")
    return "\n".join(out)


def main():
    P = yaml.safe_load(open(PROTOCOL))
    scenes = list(P["scenes"])
    a = pd.concat([pd.read_csv(f"{D}/{s}_auc.csv") for s in scenes])
    feats = list(dict.fromkeys(a.feature))

    print("## Scope and label per scene\n")
    sc = a.groupby("scene", sort=False).first()[["n_pos", "n_neg", "strata_used", "n_far"]]
    sc["N_seen"] = sc.n_pos + sc.n_neg
    sc["L1_pos_pct"] = sc.n_pos / sc.N_seen * 100
    sc = sc[["N_seen", "n_pos", "L1_pos_pct", "strata_used"]].loc[scenes]
    sc.index.name = "scene"
    print(md(sc.astype(object).map(lambda v: f"{v:,}" if isinstance(v, (int, np.integer))
                                     else (f"{v:.2f}" if isinstance(v, float) else v))))

    print("\n## L1+ rate per depth stratum (% of stratum, seen Gaussians; stratum 1 = nearest)\n")
    rr = {}
    for s_ in scenes:
        t_ = pd.read_csv(f"{D}/{s_}_strata.csv")
        rr[s_] = dict(zip([f"s{k}" for k in t_.stratum], t_.n_pos / t_.N * 100))
        rr[s_]["deepest_share_of_L1+"] = t_.n_pos.iloc[-1] / t_.n_pos.sum() * 100
    rt = pd.DataFrame(rr).T
    rt.index.name = "scene"
    print(md(rt, "{:.1f}"))

    for col, title in (("auc_within_depth", "Within-depth AUC (N-weighted mean over used strata)"),
                       ("auc_pooled", "Pooled AUC (seen Gaussians)"),
                       ("auc_far_init", "Pooled AUC on far-from-init Gaussians (T3)")):
        t = a.pivot(index="scene", columns="feature", values=col).loc[scenes, feats]
        print(f"\n## {title}\n")
        print(md(t))

    w = a.pivot(index="scene", columns="feature", values="auc_within_depth").loc[scenes, feats]
    print("\n## Stability verdict (pre-registered rule: within-depth AUC on the same side of 0.5 on all scenes)\n")
    rows = []
    for f in feats:
        v = w[f].to_numpy()
        above, below = int((v > 0.5).sum()), int((v < 0.5).sum())
        verdict = ("stable, separates as hypothesised" if above == len(v) else
                   "stable, INVERTED (runs opposite to hypothesis)" if below == len(v) else
                   "NOT stable")
        rank = w.rank(axis=1, ascending=False)[f].astype(int).tolist()
        rows.append(dict(feature=f, min=v.min(), max=v.max(),
                         scenes_above_0_5=f"{above}/{len(v)}",
                         rank_per_scene=" ".join(map(str, rank)), verdict=verdict))
    t = pd.DataFrame(rows).set_index("feature")
    print(md(t))
    print(f"\nrank_per_scene order: {', '.join(scenes)}")

    sus = a[a.suspicious]
    print(f"\nAUC > {P['evaluation']['suspicious_auc']} flags (pooled or any stratum): "
          + (", ".join(f"{r.scene}/{r.feature}" for r in sus.itertuples()) or "none"))

    t6 = pd.concat([pd.read_csv(f"{D}/{s}_T6.csv") for s in scenes])
    t6["cell"] = t6.apply(lambda r: f"{r['shift']:+.3f} [{r.ci_lo:+.3f}, {r.ci_hi:+.3f}]", axis=1)
    p6 = t6.pivot(index="scene", columns="feature", values="cell").loc[
        scenes, ["volume", "scale_max", "anisotropy", "planarity"]]
    print("\n## T6 median shift, unsupported minus supported (decades; planarity raw), 95% bootstrap CI\n")
    print(md(p6))

    t5 = pd.concat([pd.read_csv(f"{D}/{s}_T5.csv") for s in scenes]).set_index("scene").loc[scenes]
    t5 = t5[["N", "n_subset", "anisotropy_thr", "n_near", "pct_near", "n_amb", "pct_amb",
             "n_far", "pct_far", "n_unseen"]]
    print("\n## T5 needles (option B: near <= 1 x spacing, far > 20 x spacing)\n")
    print(md(t5.astype(object).map(lambda v: f"{v:,}" if isinstance(v, (int, np.integer))
                                     else (f"{v:.4g}" if isinstance(v, float) else v))))

    t7 = pd.concat([pd.read_csv(f"{D}/{s}_T7.csv") for s in scenes]).set_index("scene").loc[scenes]
    t7 = t7[["N", "n_unseen", "n_few", "pct_few", "spread_p50", "parallax_p10",
             "parallax_p50", "n_many", "n_many_narrow"]]
    print("\n## T7 coverage\n")
    print(md(t7.astype(object).map(lambda v: f"{v:,}" if isinstance(v, (int, np.integer))
                                     else (f"{v:.3f}" if isinstance(v, float) else v))))


if __name__ == "__main__":
    main()
