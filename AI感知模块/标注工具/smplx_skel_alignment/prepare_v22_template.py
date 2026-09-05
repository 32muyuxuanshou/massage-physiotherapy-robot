"""Stamp a full SMPL-X template with v2.2 identity without altering topology."""

from __future__ import annotations

import argparse
import os
import sys

import bpy


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gender", choices=("neutral", "female", "male"), required=True)
    parser.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def main():
    args = parse_args()
    candidates = [
        obj for obj in bpy.data.objects
        if obj.type == "MESH" and len(obj.data.vertices) == 10475
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one SMPL-X mesh, got {len(candidates)}")
    target = candidates[0]
    target["body_model"] = "smplx"
    target["smplx_gender"] = args.gender
    target["gender"] = args.gender
    target["smplx_template_target"] = True
    target["smplx_template_release"] = "2.2.0"
    target["smplx_template_id"] = f"smplx-{args.gender}-full-v2.2"
    target["annotation_surface"] = True
    target["skel_annotation_target"] = False
    bpy.context.scene["smplx_skel_v22_gender"] = args.gender
    bpy.context.scene["smplx_skel_reference_policy"] = (
        "none-for-neutral" if args.gender == "neutral" else "optional-display-only"
    )
    output = os.path.abspath(args.output)
    bpy.ops.wm.save_as_mainfile(filepath=output, check_existing=False)
    print(f"SMPLX_V22_TEMPLATE=PASS gender={args.gender} output={output}")


main()
