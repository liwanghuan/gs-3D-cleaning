# Near-field checks — truck
Run: 2026-11-10 · config: `configs/nearfield_checks.yaml` (features from `configs/T1_truck.yaml`, alignment from `configs/align_truck.yaml`) · commit: 677b576 (code that produced these numbers)

**In one sentence:** the laser scan's official crop covers the truck and nothing else. That is 20.33 % of Gaussians, nearly all of depth deciles 1–2, part of decile 3, and none of deciles 4–10; none of the 219 training cameras is inside it. Within the crop, the current COLMAP label agrees with "far from the scan" at 97.37 % precision but only 33.42 % recall, which is the first direct measurement of its high-precision / low-recall behaviour.

## What I did
Diagnosis only. I used the estimated Inria → scan alignment (`out/alignment/truck_inria_to_gt.txt`) to see what the scan covers. Nothing was labelled with it, and whether to use it as a label (L2) is still the professor's decision.
- **Check 1:** camera centres inside the official crop, and the share of Gaussians inside the crop per depth decile. The deciles are identical to `depth_strata.py`.
- **Check 2:** distance from each in-crop Gaussian centre to the nearest scan point, sorted into three bands fixed before running:
  - on-surface: ≤ 0.02 m, about twice the ~1 cm alignment residual;
  - off-surface: 0.02–0.289 m;
  - far: > 0.289 m, the L1 τ of 0.22589 units × scale 1.280941.

## Numbers

**Check 1: crop coverage**

| Quantity | Value |
|---|---|
| Training cameras inside the crop | 0 of 219 (camera z −7.568…−6.861 is within the crop's z range −11.159…−4.445, so they fall outside its xy polygon) |
| Gaussians inside the crop | 516,630 of 2,541,226 (20.33 %) |

**Check 2: in-crop Gaussians by depth decile.** Each decile has N ≈ 253,083.

| Decile | Depth (units) | In crop | N in crop | On surface (≤ 2 cm) | Off surface (2–29 cm) | Far (> 29 cm) | L1 unsupported, in crop |
|---|---|---|---|---|---|---|---|
| 1 | 3.05 – 3.81 | 99.63 % | 252,142 | 79.25 % | 20.40 % | 0.36 % | 0.10 % |
| 2 | 3.81 – 4.38 | 86.85 % | 219,813 | 75.67 % | 23.79 % | 0.54 % | 0.50 % |
| 3 | 4.38 – 9.49 | 17.60 % | 44,536 | 75.99 % | 17.51 % | 6.49 % | 0.84 % |
| 4 – 10 | 9.49 – 89.6 | 0 % | 0 | — | — | — | — |

**L1 against "far from scan", inside the crop.** N = 516,491 in-crop Gaussians seen by at least one view.

| | Count |
|---|---|
| Far from scan (> 0.289 m) | 4,985 (0.97 %) |
| L1 unsupported | 1,711 (0.33 %) |
| Both | 1,666 |
| **L1 precision / recall** | **97.37 % / 33.42 %** |

## What this does and does not show
- **L2 is a truck-only label.** It can score features near the truck, which is where the COLMAP label had no positives: 4,985 far-from-scan Gaussians, enough for AUC. It says nothing about the background (deciles 4–10) or the camera ring.
- **Mean depth does not isolate the floaters Floaters No More describes.** A floater just in front of one camera is also seen by other cameras from farther away, so its *mean* depth is not small. And with no camera inside the crop, the free space next to the cameras lies mostly outside it. Finding those floaters needs a different measure, such as depth to the *nearest* seeing camera, or a free-space test against the scan (option L4). Neither has been run.
- **L1 is confirmed as high-precision, low-recall inside the crop.** When it fires, the scan agrees 97 % of the time, but it misses two thirds of the Gaussians that are far from the scan. This supports AGENTS.md §1.3's description and the near-field-blindness concern, and it is the label-agreement measurement that step 1 of the proposed selection rule calls for. Its scope is the crop only.
- **The 2–29 cm off-surface band is large and unexplained** (17.5–23.8 %). The distance is measured from Gaussian *centres* and ignores Gaussian size, so large surface Gaussians, alignment residual and scan noise all contribute, as well as real near-surface artefacts. It may be relevant to dilation (T6), but nothing here shows that.
- **"Far from scan" is not ground truth either.** Scan holes (glass, shiny paint, undersides) make real Gaussians look far. The alignment has about 1 cm of residual error.

## What broke
Nothing errored. After the first run I added exact L1-versus-scan counts to the script, so the precision and recall come from the script rather than from rounded percentages, and reran. The other numbers were unchanged.
