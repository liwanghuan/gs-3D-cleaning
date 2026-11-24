# T4 Floaters — truck (L2 laser-scan label)
Run: 2026-11-24 · config: `configs/T4_floaters.yaml` (label `configs/L2_scan_label.yaml`, features `configs/T1_truck.yaml`, 40 views) · commit: uncommitted

**In one sentence:** against the independent laser-scan label, `contrib_ratio` is still inverted (AUC 0.142 pooled, 0.291 within depth). So the inversion is a property of the feature, not of the COLMAP label. But most of L2's positives sit in one thin layer about 1.5 m above the truck, including a straight line about 2.8 m long that the scan does not cover. Until a human looks at it, the other AUCs cannot be read as floater detection.

## What I did
- **Scope:** Gaussians inside the official T&T crop and seen by at least one of the 40 views: N = 516,491.
- **Excluded:** the 139 in-crop Gaussians seen by no view, all of them L2-positive, as decided by the user before running.
- **AUCs:** tie-aware rank AUC of the four T4 features against L2 (τ = 0.289 m), pooled and within 5 equal-count strata of mean camera depth. L1 is scored on the same Gaussians for comparison.
- **ROC figure:** `out/figures/1_floater_roc.png` (7.4 × 4.3 in, 200 dpi).
- **False-positive diagnostic:**
  - "Best feature" = highest within-depth AUC (isolation).
  - "Clearly real" = isolation's artefact score at or below its 25th percentile.
  - The studied set = L2 positives that isolation calls clearly real.
  - I reported where they sit, their `sh_dc_norm`, and, beyond the spec, the colour standard deviation over 8 nearest Gaussians. `sh_dc_norm` measures brightness, not texture.

All rules were fixed in the config before running.

## Numbers

**Scope:** N = 516,491. L2 positives: 4,985 (0.97 %). L1 positives on the same Gaussians: 1,711.

| Feature | Artefact if | AUC vs L2, pooled | AUC vs L2, within depth (5 strata) | Strata < 0.5 | AUC vs L1, same Gaussians |
|---|---|---|---|---|---|
| contrib_ratio | high | **0.142** | **0.291** | 4 of 5 | 0.131 |
| view_frac | low | 0.861 | 0.710 | 1 of 5 | 0.879 |
| isolation | high | 0.572 | 0.780 | 1 of 5 | 0.795 |
| opacity | low | 0.652 | 0.615 | 1 of 5 | 0.666 |

**Per depth stratum (AUC vs L2):**

| Stratum | Depth (units) | N | L2 positives | contrib_ratio | view_frac | isolation | opacity |
|---|---|---|---|---|---|---|---|
| 1 | 3.17 – 3.59 | 103,298 | 220 | 0.404 | 0.466 | 0.977 | 0.656 |
| 2 | 3.59 – 3.75 | 103,298 | 528 | 0.527 | 0.572 | 0.840 | 0.541 |
| 3 | 3.75 – 3.91 | 103,298 | 306 | 0.355 | 0.665 | 0.943 | 0.491 |
| 4 | 3.91 – 4.21 | 103,298 | 871 | 0.139 | 0.861 | 0.701 | 0.679 |
| 5 | 4.21 – 5.88 | 103,299 | 3,060 | 0.031 | **0.989** | 0.440 | 0.706 |

**False-positive diagnostic.** The best feature is isolation (within-depth AUC 0.780). "Clearly real" covers 129,123 Gaussians. The studied set is 1,624 of the 4,985 L2 positives (32.58 %).

| Group | N | Median dist to scan | sh_dc_norm median | Neighbour colour std median | Scan z p10 / median / p90 | Median view_count |
|---|---|---|---|---|---|---|
| L2+ and clearly real (studied) | 1,624 | 1.451 m | 2.175 | 0.163 | −5.326 / −5.292 / −5.232 | 7 |
| Other L2+ | 3,361 | 1.491 m | 2.202 | 0.260 | −7.876 / −5.285 / −5.194 | 7 |
| L2− | 511,506 | 0.0076 m | 1.545 | 0.331 | −8.683 / −7.827 / −7.074 | 34 |

- P(neighbour colour std lower in the studied set than in L2−) = 0.796, so the studied set is more uniform in colour.
- P(sh_dc_norm lower in the studied set than in L2−) = 0.305, so the studied set is brighter.
- Median nearest-neighbour distance within the studied set is 0.0012 m, against 0.0540 m for an equal-size random L2− sample (seed 0). The studied set is extremely tightly clustered.

Figure: `out/figures/T4_fp_spatial.png` (top view and height histogram, scan frame).

## What this does and does not show
- **`contrib_ratio` is inverted against an independent label too.** L2 does not use the COLMAP cloud, and the AUC is still 0.142 pooled and 0.291 within depth. This settles the open question from the diagnostic: the problem is the feature's definition (camera geometry, the view-count cap), not the COLMAP label.
- **Most L2 positives are one overhead layer.** The height histogram puts most positives in a band about 10 cm thick at scan z ≈ −5.29, while the truck surface (L2−) spans about −9.0 to −6.8.
  - The camera centres sit at −7.57 to −6.86, about 1.4–2.1 m above the lowest Gaussians. That suggests z points up and the layer sits about 1.5 m above the top of the truck. This direction is an inference, not checked against images.
  - In the top view, part of the layer is a **straight line about 2.8 m long** (scan x −3.7 to −1.0). The rest is patches over the truck.
  - The layer is a median 1.45 m from any scan point, so the scanner recorded nothing there.
- **I cannot tell what the layer is, and §2 says not to guess.** It fits two readings:
  - (a) a real thin structure the scan missed, such as an overhead cable for the straight line. That would be a label failure, and exactly the needle/wire ambiguity of §2.
  - (b) genuine floaters, for example a sky-coloured sheet. That is consistent with it being bright and uniform in colour.

  A human needs to look at the training images where it projects.
- **This dominates the AUCs, so do not read them as floater-detection results yet.**
  - Stratum 5 holds 3,060 of the 4,985 positives (61 %), and there `view_frac` reaches 0.989.
  - Per §7 I checked for a shared input. `view_frac` uses only camera visibility and L2 uses only the scan, so they do not share an input. The likely reason is structural: an overhead layer is seen by few views (median 7, against 34 for L2−) and is also outside the scan.
  - `isolation` flips from 0.572 pooled to 0.780 within depth. The dense overhead layer, with isolation 0.440 in stratum 5, pulls the pooled value down, a Simpson's-paradox effect.
- **The false-positive diagnostic.** The Gaussians the best feature calls real but the label calls unsupported are spatially clustered (1.2 mm against 54 mm nearest-neighbour spacing), uniform in colour, bright, and almost all in the overhead layer. By the spec's own test ("if they cluster on textureless … regions, the label is wrong there") this points to label failure. Reading (b) is not excluded, though.
- **L1 gives almost the same AUCs on these Gaussians** (0.131 / 0.879 / 0.795 / 0.666). Inside the crop, both labels are dominated by the same overhead layer.
- **Weak-label caveat.** L2 is not ground truth: scan holes, centre-only distance, and an alignment residual of about 1 cm. Its failure mode in truck is now concrete: structure above the truck that the scanner did not record.

## What broke
- The script's AUC > 0.98 check only tested the pooled and depth-weighted AUCs. It missed stratum 5's per-stratum `view_frac` of 0.989, which I caught by reading the table and checked by hand, as described above. The check should also cover per-stratum values in later tasks.
- Nothing errored.
