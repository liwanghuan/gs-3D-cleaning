# Alignment to laser-scan ground truth — truck
Run: 2026-11-03 · config: `configs/align_truck.yaml` · commit: uncommitted, working tree on top of be9ca6e

## What I did
I estimated a similarity transform from the Inria COLMAP frame, which the 3DGS model lives in, to the Tanks & Temples laser-scan frame. First I fitted a similarity (Umeyama) between the 251 Inria camera centres and the 251 camera centres in T&T's own `Truck_COLMAP_SfM.log`, pairing cameras by image order (`000001.jpg` ↔ log entry 0). I then composed that fit with T&T's published `Truck_trans.txt`, which maps their COLMAP frame to the scan.

To check the result independently, I pushed the Inria sparse points through the transform, applied the official crop (`Truck.json`) and measured nearest-neighbour distance to the scan. A rigid ICP against the scan reports how far the scan would pull the transform; ICP is not applied.

## Numbers

**Step 1: camera fit.** Errors are in scan metres, N = 251 cameras.

| Quantity | Value |
|---|---|
| Scale, Inria units → metres | 1.280941 |
| Camera-centre error, RMS / median / max | 3.69 mm / 2.88 mm / 16.22 mm |
| Trajectory bounding-box diagonal | 15.759 m |
| Camera-orientation error, median / max (not used in the fit) | 0.086° / 0.338° |

**Step 2: independent check against the scan.**
- Scan points: N = 8,071,886 total, 7,143,563 inside the official crop.
- Inria sparse points inside the crop: N = 75,481 of 136,029 (55.5 %).
- Threshold τ = 0.005 m, the official T&T value for Truck, used only as a unit.

| Sparse point → scan NN distance | Before ICP | After diagnostic ICP |
|---|---|---|
| median | 5.6 mm | 4.1 mm |
| p90 | 25.0 mm | 23.6 mm |
| p99 | 220.4 mm | 220.4 mm |
| within 1τ / 2τ / 5τ / 10τ | 45.90 / 70.14 / 89.99 / 94.83 % | — |

**Diagnostic ICP.** Correspondences were limited to 10τ = 0.05 m, and it ran 49 iterations. It moves the transform by 0.060° of rotation and 10.2 mm at the crop centre. RMS over correspondences went from 11.4 mm to 10.4 mm.

Transform written to `out/alignment/truck_inria_to_gt.txt`.

## What this does and does not show
- **The pairing by image order holds.** A wrong pairing would leave errors of metres, not millimetres. The camera orientations agree to within 0.34° even though the fit never used them.
- **Residual misalignment is about 1 cm.** That is the ICP shift at the crop centre and the median improvement, roughly 1–2 τ. This is fine for labelling floaters: the T1 `unsupported` threshold of 0.22589 Inria units equals 0.22589 × 1.280941 ≈ 0.289 m in the scan frame, about 28× larger. It is **not** fine for anything that needs millimetre accuracy, such as F-scores at τ = 5 mm. Those would need the ICP refinement applied, and that choice should be made and logged before any metric is computed.
- **The p99 of 0.22 m is a genuine tail, not a fitting error.** ICP leaves it unchanged. About 5 % of the in-crop sparse points lie more than 5 cm from any scan point. The likely causes are COLMAP outliers and surfaces the scanner missed, such as glass, shiny paint and occluded undersides. The scan is dense but not complete, so "far from scan" will also over-label in those places, just much less than the sparse cloud does.
- **The scan only labels what is inside the crop.** 44.5 % of the sparse points fall outside it, and the background Gaussians that make up much of the 42.45 % `unsupported` set in T1 will mostly have no laser label at all. Any metric against the scan must be restricted to Gaussians inside the crop, with that N stated.
- **This is an estimated transform, not a guessed one.** AGENTS.md T2 check 5 forbids applying "a transform you guessed at". This transform is fitted from 251 correspondences, its error is measured two independent ways, and it is fully reproducible. Whether it can be used is still the professor's decision.

## What broke
- The first run's ICP diagnostic *worsened* the fit: the median rose from 5.6 to 15.4 mm and the rotation moved 0.64°. The cause was a bug. The ICP step reused the similarity solver, whose translation is computed for a fitted scale, but the step applied it with scale 1. I added a rigid mode (`with_scale=False`) and reran. All numbers above come from the corrected run. Step 1 and step 2 before ICP were unaffected.
- Data came from the official T&T Google Drive links: `Truck.ply` (411.7 MB), `Truck_COLMAP_SfM.log`, `Truck_trans.txt` and `Truck.json`. It is stored in `data/tnt/truck/`, which is gitignored.
