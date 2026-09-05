"""Blender-side entry point for the integrated one-point RGB-D export."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import acupoint_blender_mcp_bridge as bridge


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(argv)


def main() -> None:
    args = _arguments()
    snapshot_path = Path(bpy.data.filepath).resolve()
    if not snapshot_path.is_file():
        raise FileNotFoundError(snapshot_path)
    validation = bridge.command_validate_atlas({"atlas_path": args.atlas})
    if not validation["valid"]:
        raise RuntimeError(validation)
    result = bridge.command_export_training_sample(
        {
            "atlas_path": args.atlas,
            "output_dir": args.output,
            "point_ids": ["11_MIDLINE"],
            "camera_name": "ACU_TRAIN_CAMERA_TEST",
            "width": args.width,
            "height": args.height,
            "source_scene_snapshot_sha256": _sha256(snapshot_path),
        }
    )
    required = {
        "rgb_path",
        "scene_depth_z_path",
        "depth_valid_mask_path",
        "skin_mask_path",
        "labels_path",
    }
    missing = sorted(required.difference(result))
    if missing:
        raise RuntimeError(f"integrated exporter omitted result keys: {missing}")
    for key in required:
        if not Path(result[key]).is_file():
            raise FileNotFoundError(result[key])
    if result.get("point_count") != 1:
        raise RuntimeError(result)
    Path(args.result).write_text(
        json.dumps(
            {
                "passed": True,
                "sample": result,
                "blend_path": bpy.data.filepath,
                "blend_dirty_after_export": bool(bpy.data.is_dirty),
                "blend_saved_by_exporter": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("ACU_EXPORT_INTEGRATED_SAMPLE=PASS")


if __name__ == "__main__":
    main()
