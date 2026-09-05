"""Freeze or apply the complete light contract in one B-line snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


LIGHT_NAMES = ("ACU_PRONE_KEY", "ACU_PRONE_FILL")


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("freeze", "apply"), required=True)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def serialize(obj) -> dict:
    if obj is None or obj.type != "LIGHT":
        raise RuntimeError("fixed light object is missing")
    data = obj.data
    return {
        "name": obj.name,
        "matrix_world": rows(obj.matrix_world),
        "data": {
            "name": data.name,
            "type": data.type,
            "energy": float(data.energy),
            "color": [float(value) for value in data.color],
            "shape": str(data.shape),
            "size": float(data.size),
            "size_y": float(data.size_y),
        },
    }


def compare_contract(expected: list[dict], actual: list[dict]) -> tuple[bool, float, bool]:
    if [item["name"] for item in expected] != [item["name"] for item in actual]:
        return False, float("inf"), False
    matrix_error = max(
        abs(float(left) - float(right))
        for expected_light, actual_light in zip(expected, actual)
        for expected_row, actual_row in zip(expected_light["matrix_world"], actual_light["matrix_world"])
        for left, right in zip(expected_row, actual_row)
    )
    data_equal = all(
        expected_light["data"] == actual_light["data"]
        for expected_light, actual_light in zip(expected, actual)
    )
    return matrix_error <= 1e-6 and data_equal, matrix_error, data_equal


def main() -> None:
    args = arguments()
    lights = [bpy.data.objects.get(name) for name in LIGHT_NAMES]
    if any(light is None for light in lights):
        raise RuntimeError("expected fixed scene lights are missing")
    if args.mode == "freeze":
        if args.contract.exists():
            raise FileExistsError(f"refusing to overwrite frozen light contract: {args.contract}")
        contract = {
            "schema": "skel-pose-fixed-light-contract-v1",
            "source_blend": bpy.data.filepath,
            "lights": [serialize(light) for light in lights],
            "notice": "Frozen from P0_BASE after the shared preparer; reused exactly for every B-line profile."
        }
        args.contract.parent.mkdir(parents=True, exist_ok=True)
        args.contract.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        contract = json.loads(args.contract.read_text(encoding="utf-8-sig"))
        by_name = {item["name"]: item for item in contract["lights"]}
        for light in lights:
            frozen = by_name[light.name]
            light.matrix_world = Matrix(frozen["matrix_world"])
            data = frozen["data"]
            light.data.energy = float(data["energy"])
            light.data.color = tuple(float(value) for value in data["color"])
            light.data.shape = data["shape"]
            light.data.size = float(data["size"])
            light.data.size_y = float(data["size_y"])
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, check_existing=False)
    actual = [serialize(bpy.data.objects.get(name)) for name in LIGHT_NAMES]
    expected = contract["lights"]
    passed, matrix_error, data_equal = compare_contract(expected, actual)
    result = {
        "schema": "skel-pose-fixed-light-application-v1",
        "mode": args.mode,
        "passed": passed,
        "matrix_tolerance": 1e-6,
        "max_matrix_abs_error": matrix_error,
        "light_data_exact_equal": data_equal,
        "contract_sha256": sha256(args.contract),
        "expected": expected,
        "actual": actual,
        "blend": bpy.data.filepath,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise RuntimeError("light contract application mismatch")
    print("ACU_FIXED_LIGHT_CONTRACT=PASS")


if __name__ == "__main__":
    main()
