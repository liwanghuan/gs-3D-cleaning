# Cluster-level human review of the overhead layer — truck
Run: 2026-11-24 · configs: `configs/cluster_review.yaml` (round 1), `configs/cluster_review_wide.yaml` (round 2) · commit: 677b576 (code that produced these numbers)

**In one sentence:** of the 1,495 non-wire layer Gaussians shown (the 12 largest clusters), the researcher judged 1,247 to be floaters, 185 a second wire and 63 an object. But **every cluster judged "object" on adjacent frames that could be re-checked from views 34–65° apart (4 of 4) was re-judged a floater.** Human inspection on near-identical views is unreliable, and only 568 of the 1,495 judgements rest on wide-angle evidence.

## What I did
- **Clustering:** the overhead layer's non-wire part (1,838 Gaussians) was grouped into connected components with a 0.10 m link: 160 components. The 12 largest (1,495 Gaussians, 81.3 %) were shown; 292 Gaussians in components under 20 members were not.
- **Round 1:** the 3 training views where each cluster had the most members in frame. These turned out to be mostly adjacent frames.
- **Round 2:** agreed after round 1 and fixed before rendering. Among views with ≥ 50 % of the cluster in frame, the 3 whose smallest pairwise angle from the cluster centroid is largest.
- **Judgements:** all made by the researcher (the user) on 2026-11-24 and recorded verbatim in `out/reports/cluster_judgements.csv` (round 1, with the C7/C12 revisions and reasons) and `out/reports/cluster_judgements_round2.csv`. They are combined in `out/reports/cluster_judgements_final.csv`, which uses round 2 where it exists.

## Numbers

| Cluster | N | Round 1 (adjacent views) | Round 2 (wide views; min angle) | Final | Evidence |
|---|---|---|---|---|---|
| C1 | 372 | floater | — (2 candidate views, 1.6°) | floater | narrow only |
| C2 | 185 | wire | wire (43.7°) | wire | wide |
| C3 | 138 | floater | — (3 candidates, 4.9°) | floater | narrow only |
| C4 | 132 | floater | — (1 candidate) | floater | narrow only |
| C5 | 127 | object | **floater** (55.2°) | floater | wide |
| C6 | 117 | object | **floater** (46.2°) | floater | wide |
| C7 | 111 | object → floater (revised: sky lies at infinity) | — (2 candidates, 5.7°) | floater | narrow only |
| C8 | 111 | floater | — (2 candidates, 3.8°) | floater | narrow only |
| C9 | 63 | object | — (3 candidates, 0.2°) | object | narrow only |
| C10 | 55 | object | **floater** (54.6°) | floater | wide |
| C11 | 47 | object | **floater** (64.8°) | floater | wide |
| C12 | 37 | object → floater (revised: sky) | floater (34.3°) | floater | wide |

| Final | Evidence | Clusters | Gaussians |
|---|---|---|---|
| Floater | wide views | 5 | 383 |
| Floater | narrow views only | 5 | 864 |
| Wire (real thin structure) | wide views | 1 | 185 |
| Object | narrow views only | 1 | 63 |
| **Total shown** | | 12 | 1,495 |

## What this does and does not show
- **Adjacent frames mislead human inspection.** All 4 clusters judged "object" in round 1 that could be re-shown from wide views (C5, C6, C10, C11) flipped to floater. On views a few degrees apart, a mark stays on the same image content whether or not anything is there. The round-1 design (most members in frame) was my error. A review protocol needs wide-baseline views. This lesson carries directly into the human-in-the-loop part of the planned cleaning agent.
- **The earlier region-level judgement is overturned.** `out/reports/inspect_layer.md` recorded that the scattered points over the near tree were "real foliage". At cluster level, with wide views, those that could be re-checked are floaters.
- **Five floater clusters (864 Gaussians) and the one "object" cluster (C9, 63) rest on narrow views only.** They are mostly in frame only within a 0.2–5.7° cone of training views. Being visible only from a narrow cone is consistent with being poorly constrained, which is how floaters survive, but it does not prove it. C9's "object" verdict is weak evidence for the same reason.
- **C2 is a second wire segment.** The single-line RANSAC rule missed it, so it is still counted as an L2 positive in `out/reports/T4_floaters_wire_excluded.md`. Like the first wire, it is a label failure.
- **For the L2 label this means:** inside the overhead layer, most non-wire L2 positives that were reviewed are floaters, so L2 is right about them. Its failures there are the two wire segments (2,103 + 185 Gaussians).
- **Not covered:** 292 Gaussians in small fragments, and the 1,044 L2 positives outside the overhead layer.
- **One reviewer, one session, one scene.** There is no inter-rater agreement. A second reviewer, for example the professor, would strengthen this.

## What broke
- **Round 1's view selection** (most members in frame) picked near-identical frames. That is a design error, caught in discussion and corrected in round 2. Round 1 is kept on record.
- **The single-line RANSAC rule** found only the longest wire segment, and the human review found a second one (C2).
