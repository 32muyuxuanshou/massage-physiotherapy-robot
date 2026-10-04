#!/usr/bin/env bash
set -euo pipefail
ROOT=/raid5/xuhd/datasets/ct_anatomical_query_pilot_20261005
PYTHON=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
cd "$ROOT/code"
mkdir -p "$ROOT/logs"
run_branch() {
    local method="$1" gpu="$2"
    for seed in 0 1 2; do
        CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON" -u train_pilot.py --method "$method" --seed "$seed"
    done
}
run_branch GLOBAL_REGRESSION 4 > "$ROOT/logs/global.log" 2>&1 & p1=$!
run_branch INDEPENDENT_HEATMAP 5 > "$ROOT/logs/heatmap.log" 2>&1 & p2=$!
run_branch ORDERED_QUERY 6 > "$ROOT/logs/query.log" 2>&1 & p3=$!
wait "$p1"
wait "$p2"
wait "$p3"
CUDA_VISIBLE_DEVICES=4 "$PYTHON" -u evaluate_pilot.py
"$PYTHON" -u replay_and_common_hits.py
"$PYTHON" -u summarize_pilot.py
