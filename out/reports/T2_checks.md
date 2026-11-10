# T2 Sanity checks — truck
Run: 2026-11-10 · config: `configs/T2_checks.yaml` (scene settings from `configs/T1_truck.yaml`) · commit: d5c84b5 (code that produced these numbers)

## What I did
`src/checks.py` runs the five checks from AGENTS.md T2 on the real truck model and its COLMAP data. I added check 5b because bounding-box overlap is weak evidence of a shared frame. All tolerances were fixed in the config before each check ran. Check 4 runs the full extraction twice from scratch and compares file hashes, which also confirms that this task's one refactor (`select_views()`, moved out of `main()`) changed nothing.

## Numbers

| # | Check | N | Result | Tolerance | Verdict |
|---|---|---|---|---|---|
| 1 | max \|R Rᵀ − I\| over all rotations | 2,541,226 | 1.159e-06 (median 6.1e-08); det ∈ [0.999999, 1.000001] | 1e-05 | PASS |
| 2 | max \|Σ − s²I\| / s², isotropic scale under every real rotation | 2,541,226 | 1.107e-06 (median 9.6e-08) | 1e-05 | PASS |
| 3a | real Gaussians behind all 40 views → view_count = 0 | 0 exist | nothing to test on real data | — | PASS (trivially) |
| 3b | synthetic Gaussian 1.0 unit (5 × near plane) behind each camera → view_count = 0 | 40 | 0 of 40 counted as seen | 0 | PASS |
| 4 | two fresh extractions, SHA-256 | 2 runs | identical, and equal to the T1 hash `1d1d4954…5a01` | bitwise | PASS |
| 5 | bounding-box overlap, Gaussians vs reference, p1–p99 box | 2,541,226 / 136,029 | intersection = 96.64 % of the reference box, 32.46 % of the Gaussian box | > 0 | PASS |
| 5b | model's init cloud (`input.ply`) vs COLMAP points3D | 136,029 / 136,029 | max NN distance 0.000e+00 | 1e-04 | PASS |

For check 5, the raw min/max boxes give 10.41 % of the reference box and 100 % of the Gaussian box, because 1 % outliers in the reference stretch to ±175 units. The full boxes are in `out/reports/T2_checks_stdout.txt`.

## What this does and does not show
- **Frame.** Check 5 alone is weak: overlapping boxes would also occur with a wrong but nearby frame. Check 5b settles it. The training run's own initial cloud is point-for-point identical to `points3D.bin`, so the Gaussians were optimised in exactly the reference frame. The separate laser-scan alignment (`out/reports/align_truck.md`) independently found COLMAP to be geometrically consistent with the scan to a median of 5.6 mm.
- **5b confirms the T3 confound exactly.** The `unsupported` label is computed from the same 136,029 points that initialised the model, not a similar cloud. Every Gaussian that never moved far from its seed is "supported" partly by construction. T3 has to measure how much this inflates the signal.
- **The robust Gaussian box is about 3× larger than the reference box.** It reaches z = −73.9 at the 1st percentile, against −28.9 for the reference. Much of the model lies where the sparse reference has almost no points, which is consistent with background and sky Gaussians and with T1's 42.45 % `unsupported` rate. The label therefore has a systematic failure mode in truck: it fires on real distant geometry that COLMAP barely triangulated.
- **Check 3 has no real-data test.** No Gaussian is behind all 40 sampled views, because the cameras circle the truck. The synthetic test only shows the near-plane cull works; it does not exercise a real edge case.
- **Checks 1–2 test the maths, not the data.** The worst deviations (about 1e-6) are float32 rounding.

## What broke
Nothing failed. One addition to the spec: check 5b, and its config keys `init_ply` and `init_match_tol` were added before it ran. One refactor: `select_views()` in `src/extract_features.py`, verified output-neutral by check 4.
