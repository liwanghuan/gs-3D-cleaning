# T1 Feature extraction — truck
Run: 2026-10-20 · config: `configs/T1_truck.yaml` · commit: 82f8bfc (code that produced these numbers)

## What I did
I ported `extract_features_cpu.py` to `src/extract_features.py` and ran it on the published Inria 3DGS truck model (iteration 30000) with its COLMAP `sparse/0`. It writes one parquet row per Gaussian, with 22 columns. Opacity goes through a sigmoid, scales through exp, and quaternions are normalised. Each Gaussian is projected with the EWA Jacobian, plus the 0.3 px² low-pass and the 1.3·tan(fov/2) Jacobian clamp from the reference rasteriser. Accumulation runs one view at a time into `[N]` buffers. The run used 40 views, taken at a fixed stride from the 219 **training** views.

## Numbers

| Quantity | Value |
|---|---|
| Gaussians (rows) | N = 2,541,226 |
| Columns | 22: `gaussian_id, x, y, z, opacity, scale_max, scale_min, volume, anisotropy, planarity, sh_dc_norm, knn_mean, knn_max, isolation, view_count, view_frac, cov_sum, cov_max, radius_max_px, contrib_ratio, dist_to_reference, unsupported` |
| COLMAP views total / training (eval holdout 8) / used | 251 / 219 / 40 |
| Image size used | 1957 × 1091 px (`cfg_args` resolution=1) |
| Reference points (COLMAP points3D) | N = 136,029 |
| Median reference NN spacing | 0.01129 scene units |
| `unsupported` threshold τ = 20 × spacing | 0.22589 scene units |
| `unsupported` = 1 | 1,078,846 of 2,541,226 = **42.45 %** |
| Wall time / peak RSS (Apple M-series, 8 GB) | 52 s / 0.85 GB |

**Range checks (nothing clipped).** All violation counts are out of N = 2,541,226.

| Check | Violations |
|---|---|
| opacity ∈ [0, 1] | 0 |
| scale_min > 0 | 0 |
| scale_max > 0 | 0 |
| view_frac ∈ [0, 1] | 0 |
| all numeric values finite | 0 |

**In range but notable.** All counts are out of N = 2,541,226.

| Observation | Count | % |
|---|---|---|
| `view_count == 0` (no sampled view sees it) | 10,397 | 0.41 |
| `opacity == 1.0` exactly (float32 sigmoid saturates) | 2,105 | 0.08 |
| `scale_min < 1e-6` scene units (min observed 1.16e-14) | 62,491 | 2.46 |
| `anisotropy > 1e4` (max 5.0e8) | 139,461 | 5.49 |

Medians, all over N = 2,541,226: opacity 0.054, view_frac 0.25, contrib_ratio 1.26, isolation 1.00 (by construction), dist_to_reference 0.171. The full `df.describe()` is in `out/reports/T1_truck_stdout.txt`.

## What this does and does not show
This only shows that the pipeline runs end to end and that the columns are in their valid ranges. It says nothing yet about whether any feature separates artefacts.

The `unsupported` label is weak supervision, not ground truth. It is meant to be high precision and low recall. Flagging 42.45 % of the model is far more than a high-precision floater label should, and that is the first warning. The truck scene's Gaussians span about 130 × 35 × 135 scene units, while the COLMAP sparse points are concentrated on the textured truck and the nearby ground. The label will therefore fire on real but sparsely triangulated geometry: distant buildings and trees, sky, and low-texture tarmac. In this scene it is likely measuring "far from textured foreground" as much as "floater".

τ = 20 × median spacing was inherited unchanged from the starting script. It was not tuned, and per §1.2 I am not changing it now. T3/T4 should show how much of the 42 % is background.

There are other confounds. There is no transmittance, so occluded Gaussians count as contributing. Using 40 of 219 views makes `view_frac` coarse: steps of 0.025, and some of the 10,397 unseen Gaussians are probably seen by views that were skipped. `isolation` is normalised by the scene median, so it can only be compared within a scene.

## What broke
- **pycolmap** has no wheel for Python 3.15, which is the interpreter on this machine. I replaced it with `src/colmap_io.py`, a numpy/struct reader for COLMAP binaries, so nothing was added. **pyyaml** was installed because §3 requires YAML configs.
- **Config changed before any metric was computed.** I logged both changes in the config:
  - `train_max_width` 1600 → 0. The starting assumption was 3DGS's `-r -1` default, but `cfg_args` says `resolution=1`, and `cameras.json` confirms 1957 px wide.
  - Added `eval_holdout: 8`. `cfg_args` says `eval=True`, so 32 test views were never seen in training and are now excluded.
- **Changes from the starting script:**
  - Added the rasteriser's Jacobian FoV clamp.
  - Views are sorted by name so subsampling is deterministic.
  - Columns are reordered to the spec.
  - Constants moved to the config.
  - Camera distortion is ignored. That is moot here because truck uses PINHOLE.
- I could not check the eval split against `cameras.json`, because it lists all 251 cameras. The split rule comes from the 3DGS source (`llffhold=8`) and is not verified from the data.
- Surprise: 2.46 % of Gaussians have `scale_min < 1e-6`, which is effectively 2D. That drives `anisotropy` up to 5e8. T5's top-2 % anisotropy set will be dominated by these flat discs, not only by needles.
