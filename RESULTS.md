# RESULTS

Running log, newest first. Each entry: three lines. Every number from a committed script + config.

## 2026-10-20 · T1 feature extraction · truck · `configs/T1_truck.yaml`
- 2,541,226 Gaussians × 22 columns from 40 of 219 training views. All range checks pass (0 violations), nothing clipped. Report: `out/reports/T1_features.md`.
- `unsupported` (τ = 20 × 0.01129 = 0.226 units) flags 1,078,846 / 2,541,226 = 42.45 %. That is too high for a high-precision label, probably because the sparse reference barely covers the background.
- Config changes before any metric: full resolution and the 3DGS eval holdout (from `cfg_args`). pycolmap was replaced by a numpy COLMAP reader because there is no wheel for Python 3.15.
