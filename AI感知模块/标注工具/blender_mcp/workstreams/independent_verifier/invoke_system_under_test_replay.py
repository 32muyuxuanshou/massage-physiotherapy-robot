"""Invoke the integrated exporter as a black-box to create a replay sample.

This harness only creates a second system-under-test output.  All expected-value
math and comparisons remain in verify_sample.py and blender_scene_probe.py.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--camera", required=True)
    parser.add_argument("--point-id", default="11_MIDLINE")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--addons-root", required=True, type=Path)
    parser.add_argument("--snapshot-sha256", required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"Replay output is not empty: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.addons_root))
    sys.path.insert(0, str(args.addons_root / "modules"))
    bridge = importlib.import_module("acupoint_blender_mcp_bridge")
    result = bridge.command_export_training_sample(
        {
            "atlas_path": args.atlas,
            "output_dir": str(args.output_dir),
            "camera_name": args.camera,
            "point_ids": [args.point_id],
            "width": args.width,
            "height": args.height,
            "source_scene_snapshot_sha256": args.snapshot_sha256,
        }
    )
    print("__ACU_REPLAY_RESULT__" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
