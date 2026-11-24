# T4 Floaters, wire excluded — truck (L2 label, corrected)
Run: 2026-11-24 · config: `configs/T4_floaters_wire_excluded.yaml` · commit: 677b576 (code that produced these numbers)

**In one sentence:** with the 2,103 human-confirmed wire Gaussians excluded, `isolation` becomes the strongest feature (AUC 0.778 pooled, 0.835 within depth, above 0.5 in all 5 depth strata). `view_frac` drops from 0.861 to 0.760 pooled, because the wire had inflated it, and `contrib_ratio` stays inverted (0.221 / 0.295).

## What I did
Identical to `out/reports/T4_floaters.md`, with one change agreed before running: the wire part of the overhead layer is excluded from evaluation, neither positive nor negative. That part is the 2,103 Gaussians on the RANSAC line (`configs/layer_split.yaml`, 0.05 m, seed 0), all L2-positive, which the researcher judged to be a real electric wire on 2026-11-24. The check for AUC > 0.98 now also covers every single stratum.

## Numbers

**Scope:** N = 514,388 (516,491 − 2,103 wire). L2 positives: 2,882 (0.56 %). L1 positives on the same Gaussians: 1,688.

| Feature | Artefact if | T4 uncorrected: pooled / within depth | **Corrected: pooled / within depth** | Corrected strata < 0.5 | Corrected AUC vs L1 |
|---|---|---|---|---|---|
| contrib_ratio | high | 0.142 / 0.291 | **0.221 / 0.295** | 4 of 5 | 0.131 |
| view_frac | low | 0.861 / 0.710 | **0.760 / 0.705** | 1 of 5 | 0.878 |
| isolation | high | 0.572 / 0.780 | **0.778 / 0.835** | 0 of 5 | 0.798 |
| opacity | low | 0.652 / 0.615 | **0.641 / 0.618** | 1 of 5 | 0.665 |

**Per stratum, corrected (AUC vs L2):**

| Stratum | Depth (units) | N | L2 positives | contrib_ratio | view_frac | isolation | opacity |
|---|---|---|---|---|---|---|---|
| 1 | 3.17 – 3.59 | 102,878 | 219 | 0.402 | 0.464 | 0.978 | 0.657 |
| 2 | 3.59 – 3.75 | 102,877 | 528 | 0.527 | 0.572 | 0.840 | 0.541 |
| 3 | 3.75 – 3.91 | 102,878 | 303 | 0.354 | 0.666 | 0.943 | 0.487 |
| 4 | 3.91 – 4.20 | 102,877 | 870 | 0.139 | 0.861 | 0.701 | 0.680 |
| 5 | 4.20 – 5.88 | 102,878 | 962 | 0.053 | 0.963 | 0.711 | 0.725 |

No AUC exceeds 0.98, pooled, depth-weighted or in any single stratum.

**False-positive diagnostic.** The best feature is isolation. The studied set is 348 of the 2,882 L2 positives (12.07 %), down from 32.58 %. It remains tightly clustered: median nearest-neighbour distance 0.0013 m, against 0.1379 m for a random L2− sample. It is uniform in colour: P(neighbour colour std lower than L2−) = 0.838. It sits at scan z −5.92 to −4.77 (p10–p90), which is the overhead layer.

## What this does and does not show
- **The wire was distorting T4.** Excluding the 2,103 Gaussians lowers `view_frac` (pooled 0.861 → 0.760; stratum 5 0.989 → 0.963) and raises `isolation` (pooled 0.572 → 0.778; stratum 5 0.440 → 0.711). The wire is dense, so it looks "real" to `isolation`, and it is seen by few views, so it looks "artefact" to `view_frac`.
- **`isolation` is now the most consistent feature:** above 0.5 in every depth stratum, from 0.70 to 0.98. This is the strongest separation so far. But the remaining positives are not yet confirmed floaters:
  - the overhead layer's non-wire part (1,838) mixes near-tree foliage and floaters, per the human judgement at region level, and cluster-level review is pending;
  - 1,044 L2 positives outside the layer have not been inspected.
- **`contrib_ratio` stays inverted after the correction,** consistent with the definitional problem in `out/reports/diag_contrib_ratio.md`.
- **The studied false-positive set (348) is still in the overhead layer.** Some of it is probably the near tree, which would again be L2 label failure (foliage the scanner missed). Cluster review should tell.
- **Weak-label caveat:** L2 is not ground truth. Its failure modes in truck are now concrete: a missed wire (confirmed), probably missed foliage (pending), scan holes, and centre-only distance.

## What broke
Nothing errored. Both the uncorrected and corrected results are kept and reported.
