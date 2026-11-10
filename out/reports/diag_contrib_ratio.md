# Diagnostic: why contrib_ratio runs backwards — truck
Run: 2026-11-10 · config: `configs/diag_contrib_ratio.yaml` (features from `configs/T1_truck.yaml`, 40 views) · commit: uncommitted, working tree on top of 546c50c

**In one sentence:** the AUC of 0.22 is not evidence about floaters. Opacity cancels out of `contrib_ratio`, which leaves pure camera geometry. The ratio is capped by `view_count`, and its rank correlation with a distance-only proxy is 0.85. Compared only among Gaussians seen by the same number of views, its AUC against `unsupported` is 0.51, which is no signal in either direction.

## What I did
I re-projected all 2,541,226 Gaussians one view at a time with the T1 projection code, so the set of views that see each Gaussian is identical to T1 (asserted in code). I tested four things:
- **A.** Whether opacity drops out of the ratio.
- **B.** Whether the ratio is bounded by `view_count`.
- **C.** AUC within `view_count` strata, which removes that coupling.
- **D.** How much a distance-only proxy explains: `dist_ratio` = max(1/z²) / mean(1/z²) over the seeing views. This is what the ratio would be for a sphere with no low-pass filter and no area cap.

Nothing in the feature table, the label or any threshold was changed.

## Numbers

| Test | N | Result |
|---|---|---|
| A. ratio from area alone vs T1 `contrib_ratio` | 2,530,829 seen | max relative difference 1.5e-07, so identical |
| B. Gaussians with `contrib_ratio` > `view_count` | 2,541,226 | 0 |
| B. Gaussians seen by exactly 1 view (ratio forced to 1) | 2,541,226 | 97,414 |
| B. Spearman(`contrib_ratio`, `view_count`) | 2,541,226 | 0.797 |
| C. pooled AUC (as in T3) | 2,541,226 | 0.219 |
| C. N-weighted mean AUC within `view_count` strata | 1,834,889 (72.2 %, 18 strata, view_count 2–19) | **0.514** |
| C. range across strata | 18 strata | 0.430 – 0.749; 9 of 18 below 0.5 |
| D. Spearman(`contrib_ratio`, `dist_ratio`) | 2,530,829 | **0.849** |
| D. AUC of `dist_ratio` alone | 2,541,226 | 0.198 |
| D. AUC of `contrib_ratio / dist_ratio` (the part distance does not explain) | 2,541,226 | 0.541 |

| Label group | N | median view_count | median contrib_ratio | median mean camera depth | median dist_ratio |
|---|---|---|---|---|---|
| unsupported | 1,078,846 (1,068,450 seen) | 6 | 1.155 | 22.28 units | 1.264 |
| supported | 1,462,380 (1,462,379 seen) | 14 | 1.546 | 9.81 units | 1.565 |

Stratum rule, fixed before running: view_count ≥ 2 and at least 1,000 Gaussians per label class. The full per-stratum table is in `out/reports/diag_contrib_ratio_stdout.txt`.

## What this does and does not show
- **No code bug.** The implementation matches the T1 definition exactly. The problem is the definition.
- **Opacity weighting is a no-op in a ratio** (test A). Opacity is the same in every view, so `contrib_ratio` measures only how much the projected footprint area varies across views. That depends on camera distance and viewing angle, not on how much the Gaussian contributes to the image.
- **The ratio is mechanically tied to view count** (test B). The maximum of *n* values is at most *n* times their mean, so a Gaussian seen by one view scores exactly 1, the lowest possible value. A floater seen in one or two views, the case §2 describes, is forced to the bottom of the scale. The feature cannot flag the artefact it was designed for.
- **Controlling for view count removes the inversion** (test C). Within strata the AUC is 0.514, with half the strata on each side of 0.5. The pooled 0.219 is mostly the view-count coupling: unsupported Gaussians have a median of 6 views against 14 for supported ones.
- **Most of what remains is camera distance** (test D). A distance-only proxy has a rank correlation of 0.85 with the ratio, and on its own gives an even more inverted AUC (0.198). Unsupported Gaussians sit a median 22.3 units from the cameras that see them, against 9.8 for supported ones. That fits the T1/T2 picture of the label firing on distant background: background is seen at similar depth from every view, so its ratio stays near 1.
- **This does not show whether the feature or the label is "right".** Both are dominated by distance from the cameras. The label says "far from triangulated points", which in this scene largely means far background; the feature says "far and few views". The residual AUC of 0.541 after dividing out distance is a small effect, but its meaning is unclear for the same reason. The laser-scan label inside the official crop would separate these. Using it is still pending the professor's decision on the alignment.
- **The weak-label caveat stands.** `unsupported` is high-precision / low-recall by design, and in truck it over-fires on sparsely triangulated background (T1: 42.45 %).

## What broke
Nothing errored. The saved log's progress-bar lines were stripped after the run, and the numbers were not touched. `dist_ratio` is a diagnostic proxy only. It is not proposed as a feature, and no threshold was set from it.
