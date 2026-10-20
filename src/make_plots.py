#!/usr/bin/env python3
"""
Make the four week-1 result figures from the feature table.

Every figure is saved at exactly 7.4 x 4.3 inches, which is the size of the
image frame on the result slides, so you can drop the PNG straight in with no
resizing (resizing in PowerPoint is what makes fonts come out inconsistent
across slides).

    python src/make_plots.py --config configs/T1_truck.yaml --out out/figures

Thresholds (needle top-%, ambiguous band percentiles) come from the config.

No GPU, no sklearn. ROC is computed directly.
"""

import argparse
import os
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIGSIZE = (7.4, 4.3)      # matches the slide frame exactly
DPI = 200

INK, ACCENT, VERIF, MUTED, RULE = "#1A1D21", "#E0532F", "#2E7D6E", "#6B7280", "#DCDCD8"

plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def roc(scores, labels):
    """Return fpr, tpr, auc. Higher score should mean more likely positive."""
    order = np.argsort(-scores)
    y = labels[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    tpr = tp / max(tp[-1], 1)
    fpr = fp / max(fp[-1], 1)
    # np.trapz was removed in numpy 2.0 and renamed to trapezoid
    _trap = getattr(np, "trapezoid", None) or np.trapz
    auc = _trap(tpr, fpr)
    return fpr, tpr, auc


# --------------------------------------------------------------------------
def plot_floater_roc(df, path):
    y = df["unsupported"].values.astype(int)

    # each tuple: (label, score, whether high values mean "artefact")
    feats = [
        ("contribution ratio", df["contrib_ratio"].values, True),
        ("view fraction",      df["view_frac"].values,     False),
        ("isolation",          df["isolation"].values,     True),
        ("opacity",            df["opacity"].values,       False),
    ]

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    for i, (name, s, high_is_bad) in enumerate(feats):
        s = np.nan_to_num(s, nan=0.0, posinf=0.0, neginf=0.0)
        score = s if high_is_bad else -s
        fpr, tpr, auc = roc(score, y)
        colour = [ACCENT, VERIF, MUTED, RULE][i]
        lw = 2.4 if i == 0 else 1.5
        ax.plot(fpr, tpr, color=colour, lw=lw, label=f"{name}  (AUC {auc:.3f})")

    ax.plot([0, 1], [0, 1], color=RULE, lw=1, ls="--")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="lower right", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"  {path}")


def plot_needle_split(df, path, top_pct, band_lo_pct, band_hi_pct):
    """The experiment that sizes the semantic problem: among the most
    anisotropic Gaussians, how many sit on verified surface (real thin
    structure) versus far from it (artefact)?"""
    thr = np.percentile(df["anisotropy"], 100 - top_pct)
    sub = df[df["anisotropy"] >= thr]

    d = np.maximum(sub["dist_to_reference"].values, 1e-4)
    a = sub["anisotropy"].values

    # the band where distance alone cannot decide
    lo, hi = np.percentile(d, band_lo_pct), np.percentile(d, band_hi_pct)
    ambiguous = ((d > lo) & (d < hi)).mean() * 100

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.axvspan(lo, hi, color=RULE, alpha=0.35, zorder=0)
    near, far = d <= lo, d >= hi
    mid = ~near & ~far
    ax.scatter(d[near], a[near], s=4, c=VERIF, alpha=0.45, lw=0, label="on verified surface")
    ax.scatter(d[far],  a[far],  s=4, c=ACCENT, alpha=0.45, lw=0, label="far from any surface")
    ax.scatter(d[mid],  a[mid],  s=4, c=MUTED,  alpha=0.35, lw=0, label=f"ambiguous ({ambiguous:.0f}%)")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("distance to nearest reference point  (scene units, log)")
    ax.set_ylabel("anisotropy  $s_{max}/s_{min}$  (log)")
    ax.set_title(f"top {top_pct:g}% most anisotropic Gaussians", fontsize=11, color=MUTED, loc="left")
    ax.legend(frameon=False, fontsize=9.5, markerscale=2.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"  {path}   ambiguous fraction = {ambiguous:.1f}%")
    return ambiguous


def plot_dilation(df, path):
    """CPU version: dilated Gaussians should be both large and unsupported.
    Compare the volume distributions of the two label groups."""
    v = np.log10(np.maximum(df["volume"].values, 1e-12))
    lab = df["unsupported"].values.astype(bool)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    bins = np.linspace(np.percentile(v, 0.5), np.percentile(v, 99.5), 70)
    ax.hist(v[~lab], bins=bins, color=VERIF, alpha=0.6, label="on verified surface", density=True)
    ax.hist(v[lab],  bins=bins, color=ACCENT, alpha=0.6, label="unsupported", density=True)

    m0, m1 = np.median(v[~lab]), np.median(v[lab])
    ax.axvline(m0, color=VERIF, lw=1.6, ls="--")
    ax.axvline(m1, color=ACCENT, lw=1.6, ls="--")
    ax.set_xlabel(r"$\log_{10}$ Gaussian volume  $s_x s_y s_z$")
    ax.set_ylabel("density")
    ax.set_title(f"median shift = {m1 - m0:+.2f} decades", fontsize=11, color=MUTED, loc="left")
    ax.legend(frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"  {path}   median log-volume shift = {m1 - m0:+.3f}")


def plot_coverage(df, path, k=3):
    """Gaussian-level coverage: how much of the model rests on almost no
    observational evidence. The voxel version comes later; this needs
    nothing beyond the feature table."""
    vf = np.sort(df["view_frac"].values)
    cdf = np.arange(1, len(vf) + 1) / len(vf)
    n_views_equiv = df["view_count"].values
    thin = (n_views_equiv < k).mean() * 100

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.plot(vf, cdf * 100, color=ACCENT, lw=2.2)
    x_thin = np.percentile(vf, thin) if thin > 0 else 0
    ax.axhline(thin, color=MUTED, lw=1, ls="--")
    ax.annotate(f"{thin:.1f}% seen in fewer than {k} views",
                xy=(0.35, thin), xytext=(0.38, min(thin + 12, 92)),
                fontsize=10.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
    ax.set_xlabel("view fraction  (share of training views that see the Gaussian)")
    ax.set_ylabel("cumulative % of Gaussians")
    ax.set_xlim(0, max(vf.max(), 0.05)); ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"  {path}   {thin:.1f}% of Gaussians seen in <{k} views")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="out/figures")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    os.makedirs(args.out, exist_ok=True)
    df = pd.read_parquet(cfg["out"])
    print(f"{len(df):,} Gaussians, {df.unsupported.mean()*100:.1f}% unsupported\n")

    plot_floater_roc(df,   os.path.join(args.out, "1_floater_roc.png"))
    nc = cfg["needle"]
    plot_needle_split(df,  os.path.join(args.out, "2_needle_split.png"),
                      nc["top_pct"], nc["band_lo_pct"], nc["band_hi_pct"])
    plot_dilation(df,      os.path.join(args.out, "3_dilation.png"))
    plot_coverage(df,      os.path.join(args.out, "4_coverage.png"))

    print(f"\nfour PNGs at {FIGSIZE[0]}x{FIGSIZE[1]} in @ {DPI} dpi — "
          f"drop straight onto the slide frames, no resizing")


if __name__ == "__main__":
    main()
