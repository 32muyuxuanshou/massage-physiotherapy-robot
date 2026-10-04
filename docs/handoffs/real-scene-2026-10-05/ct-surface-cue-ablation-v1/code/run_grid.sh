#!/usr/bin/env bash
set -euo pipefail
ROOT=/raid5/xuhd/datasets/ct_surface_cue_ablation_20261005
PYTHON=/raid5/xuhd/sam3d_s01_pilot_20260906/venv/bin/python
cd "$ROOT/code"
mkdir -p "$ROOT/logs"
run_branch() {
    for seed in 0 1 2; do
        CUDA_VISIBLE_DEVICES="$3" "$PYTHON" -u run_cue.py --method "$1" --mode "$2" --seed "$seed"
    done
}
run_branch GLOBAL_REGRESSION MASK_COORDS 0 > "$ROOT/logs/global_mask.log" 2>&1 & p1=$!
run_branch GLOBAL_REGRESSION COORDS_ONLY 1 > "$ROOT/logs/global_coords.log" 2>&1 & p2=$!
run_branch ORDERED_QUERY MASK_COORDS 2 > "$ROOT/logs/query_mask.log" 2>&1 & p3=$!
run_branch ORDERED_QUERY COORDS_ONLY 3 > "$ROOT/logs/query_coords.log" 2>&1 & p4=$!
wait "$p1"
wait "$p2"
wait "$p3"
wait "$p4"
CUDA_VISIBLE_DEVICES=0 "$PYTHON" -u evaluate_cue.py
