#!/usr/bin/env bash
# Protocol v1 pipeline for one scene: T1 features -> extra signals ->
# T3/T4 evaluation -> T6/T7 -> T5. Logs go to out/reports/protocol_v1/<scene>_*.txt
# (progress bars stripped). Usage: bash src/run_scene.sh <scene>
set -euo pipefail
s=$1
cfg=configs/T1_$s.yaml
log=out/reports/protocol_v1
mkdir -p "$log"
strip() { grep -v -E '(it/s|s/it)\]' ; }
python src/extract_features.py --config "$cfg" 2>&1 | strip | tee "$log/${s}_T1_stdout.txt"
python src/extra_signals.py    --config "$cfg" 2>&1 | strip | tee "$log/${s}_extra_stdout.txt"
python src/evaluate_scene.py   --config "$cfg" 2>&1 | strip | tee "$log/${s}_stdout.txt"
python src/t6_t7_scene.py      --config "$cfg" 2>&1 | strip | tee "$log/${s}_T6T7_stdout.txt"
python src/t5_needles.py      --config "$cfg" 2>&1 | strip | tee "$log/${s}_T5_stdout.txt"
echo "SCENE_DONE $s"
