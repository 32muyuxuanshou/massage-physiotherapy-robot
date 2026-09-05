"""Independent file-level verification for one isolated RGB-D prototype output."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import OpenImageIO as oiio


def read_image(path: Path) -> np.ndarray:
    image_input = oiio.ImageInput.open(str(path))
    if image_input is None:
        raise RuntimeError(f"Cannot open {path}")
    try:
        spec = image_input.spec()
        pixels = np.asarray(image_input.read_image(oiio.UINT8), dtype=np.uint8)
        return pixels.reshape(spec.height, spec.width, spec.nchannels)
    finally:
        image_input.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sample(path: Path) -> dict:
    scene_depth = np.load(path / "scene_depth_z.npy", allow_pickle=False)
    body_depth = np.load(path / "body_only_depth_z.npy", allow_pickle=False)
    skin_png = read_image(path / "visible_skin_mask.png")[..., 0]
    valid_png = read_image(path / "depth_valid_mask.png")[..., 0]
    preview_png = read_image(path / "scene_depth_preview.png")[..., 0]
    rgb_png = read_image(path / "rgb.png")
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    expected_shape = (
        metadata["camera"]["intrinsics"]["height"],
        metadata["camera"]["intrinsics"]["width"],
    )
    valid = scene_depth > 0.0
    body_valid = body_depth > 0.0
    expected_skin = valid & body_valid & (np.abs(scene_depth - body_depth) <= 1e-4)
    checks = {
        "depth_dtype_float32": str(scene_depth.dtype) == "float32",
        "body_depth_dtype_float32": str(body_depth.dtype) == "float32",
        "all_pixel_shapes_equal": bool(
            scene_depth.shape
            == body_depth.shape
            == skin_png.shape
            == valid_png.shape
            == preview_png.shape
            == rgb_png.shape[:2]
            == expected_shape
        ),
        "skin_png_binary": set(np.unique(skin_png).tolist()).issubset({0, 255}),
        "valid_png_binary": set(np.unique(valid_png).tolist()).issubset({0, 255}),
        "skin_png_exactly_matches_depth_derivation": bool(
            np.array_equal(skin_png, expected_skin.astype(np.uint8) * 255)
        ),
        "valid_png_exactly_matches_depth": bool(np.array_equal(valid_png, valid.astype(np.uint8) * 255)),
        "background_depth_exactly_zero": bool(np.all(scene_depth[~valid] == 0.0)),
        "skin_pixel_count_matches_metadata": int(expected_skin.sum())
        == int(metadata["statistics"]["skin_pixel_count"]),
        "valid_pixel_count_matches_metadata": int(valid.sum())
        == int(metadata["statistics"]["valid_pixel_count"]),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "shape": list(expected_shape),
        "skin_pixel_count": int(expected_skin.sum()),
        "valid_pixel_count": int(valid.sum()),
    }


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(argv) != 2:
        raise SystemExit("Usage: blender --background --python verify_outputs_blender.py -- OUTPUT_DIR SOURCE_BLEND")
    root = Path(argv[0]).resolve()
    source_blend = Path(argv[1]).resolve()
    run_summary = json.loads((root / "run_summary.json").read_text(encoding="utf-8"))
    samples = {
        name: verify_sample(root / name)
        for name in ("known_plane", "skel_baseline", "skel_occluded")
    }
    source_hash = sha256(source_blend)
    expected_source_hash = run_summary["source_blend_sha256_at_end"]
    result = {
        "passed": bool(
            run_summary["passed"]
            and all(sample["passed"] for sample in samples.values())
            and source_hash == expected_source_hash
        ),
        "independent_of_prototype_core": True,
        "samples": samples,
        "source_blend": str(source_blend),
        "source_blend_sha256": source_hash,
        "source_hash_matches_run_summary": source_hash == expected_source_hash,
        "visual_review_required_separately": True,
    }
    (root / "output_integrity_verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("RGBD_OUTPUT_INTEGRITY=" + json.dumps({"passed": result["passed"], "root": str(root)}))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
