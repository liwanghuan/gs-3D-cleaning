# L2 laser-scan label — truck
Run: 2026-11-10 · config: `configs/L2_scan_label.yaml` (alignment from `configs/align_truck.yaml`) · commit: 677b576 (code that produced these numbers)

**In one sentence:** inside the official crop, 5,124 of 516,630 Gaussians (0.99 %) are more than 0.289 m from the laser scan. The old COLMAP label (L1) catches only 35.23 % of them, but 97.57 % of what L1 flags is also far from the scan.

## What I did
Approval, as reported by the user on 2026-11-10: the professor approved the laser-scan label and the estimated alignment. I transformed each Gaussian centre into the scan frame with `out/alignment/truck_inria_to_gt.txt` and kept those inside the official T&T crop. For each, I measured the distance to the nearest scan point in the crop. `unsupported_scan = 1` if that distance is above τ = 0.289 m, which is the L1 threshold of 0.22589 units × scale 1.280941, chosen from that derivation before computing. Outside the crop the label is missing, never 0.

The label is written to its own table (`out/features/truck_L2_label.parquet`, gitignored), and the T1 feature table is unchanged. Two runs produced identical files (SHA-256 `67bdb3d1…eb3a`).

## Numbers

| Quantity | Value |
|---|---|
| Gaussians, total | 2,541,226 |
| Labelled (inside crop) | 516,630 (20.33 %) |
| Label missing (outside crop) | 2,024,596 |
| Scan points inside crop | 7,143,563 |
| `unsupported_scan = 1` | **5,124 of 516,630 (0.99 %)** |
| `dist_to_scan_m` in crop, p5 / p25 / p50 / p75 / p95 / p99 | 0.0012 / 0.0032 / 0.0077 / 0.0181 / 0.0686 / 0.2840 m |

**L1 vs L2, inside the crop** (N = 516,630)

| | L2 = 0 | L2 = 1 |
|---|---|---|
| **L1 = 0** | 511,461 | 3,319 |
| **L1 = 1** | 45 | 1,805 |

- Of L2's positives, L1 also flags 35.23 %, so L1's recall against L2 is 35 %.
- Of L1's positives, L2 agrees on 97.57 %, so L1's precision against L2 is 98 %.
- Raw agreement is 99.35 %, which is uninformative because 99 % of Gaussians are negative under both labels.

## What this does and does not show
- **L2 gives the near-truck region the positives L1 lacked:** 5,124, against 1,850 for L1 in the same region.
- **L1 is high-precision and low-recall against the scan,** consistent with `out/reports/nearfield_checks.md`. The slightly different counts there (4,985 positives in 516,491 Gaussians) come from that report also excluding Gaussians seen by no view.
- **139 in-crop Gaussians are seen by no sampled view, and all 139 are L2 positives.** That is the difference between the two counts. They are likely inside the truck body or below the ground. For T4 this matters: `view_frac` = 0 marks them as maximally "artefact" for free. Whether to exclude unseen Gaussians must be fixed in the T4 config before running. `depth_strata.py` excluded them.
- **L2 is not ground truth.**
  - Scan holes (glass, shiny paint, undersides) make real Gaussians look far.
  - The alignment has about 1 cm of residual error, which is small next to 0.289 m.
  - Distance is measured from centres and ignores Gaussian size.
- **It covers only the truck,** with no camera inside the crop and no background. Results on L2 say nothing about deciles 4–10 or the camera ring.

## What broke
Nothing.
