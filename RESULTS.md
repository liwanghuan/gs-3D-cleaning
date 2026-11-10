# RESULTS

Running log, newest first. Each entry: three lines. Every number from a committed script + config.

## 2026-11-10 · T2 sanity checks · truck · `configs/T2_checks.yaml`
- All 5 checks plus an added 5b pass: rotations orthonormal to 1.2e-6, isotropic covariance to 1.1e-6, behind-camera view_count 0 (synthetic N = 40; no real case exists), reruns bitwise identical to T1. Report: `out/reports/T2_checks.md`.
- Frame: the p1–p99 boxes overlap (96.64 % of the reference box). The model's init cloud equals COLMAP points3D exactly (136,029 points, max distance 0).
- So the `unsupported` label is built from the exact seed cloud, and T3 must quantify that confound. The Gaussian box is about 3× the reference box, consistent with background Gaussians that the reference doesn't cover.

## 2026-11-03 · Alignment to T&T laser scan · truck · `configs/align_truck.yaml`
- Inria→scan similarity from 251 camera pairs: centre error RMS 3.69 mm (max 16.22 mm), orientation median 0.086°. Report: `out/reports/align_truck.md`.
- Independent check: sparse points inside the official crop (N = 75,481) sit a median 5.6 mm from the scan. A diagnostic ICP, not applied, shifts the transform by 10 mm and 0.06°.
- Good enough for labels at the 0.29 m scale, not for 5 mm F-scores. The scan covers only the crop (55.5 % of the sparse points), so the background has no laser label.

## 2026-10-20 · T1 feature extraction · truck · `configs/T1_truck.yaml`
- 2,541,226 Gaussians × 22 columns from 40 of 219 training views. All range checks pass (0 violations), nothing clipped. Report: `out/reports/T1_features.md`.
- `unsupported` (τ = 20 × 0.01129 = 0.226 units) flags 1,078,846 / 2,541,226 = 42.45 %. That is too high for a high-precision label, probably because the sparse reference barely covers the background.
- Config changes before any metric: full resolution and the 3DGS eval holdout (from `cfg_args`). pycolmap was replaced by a numpy COLMAP reader because there is no wheel for Python 3.15.
