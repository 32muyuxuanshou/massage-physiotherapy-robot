import hashlib
import json
import sys


EXPECTED_ATLAS_SHA256 = "F29E5BCD9C8CEF0E015924486FD81F5E8F6748B7D2EA35B10D6E3F9A16CE2E2A"
EXPECTED = {
    "GB21_LEFT": {
        "body_region": "NECK",
        "rule": "C7-to-acromion midpoint approximate",
    },
    "GB21_RIGHT": {
        "body_region": "NECK",
        "rule": "C7-to-acromion midpoint approximate",
    },
    "SI15_LEFT": {
        "body_region": "TORSO",
        "rule": "same C7 level as GV14; 2 B-cun approximate",
    },
    "SI15_RIGHT": {
        "body_region": "TORSO",
        "rule": "same C7 level as GV14; 2 B-cun approximate",
    },
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    atlas_path, output_path = sys.argv[1:]
    with open(atlas_path, "r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    by_point = {item["point_id"]: item for item in payload["annotations"]}
    failures = []
    atlas_hash = sha256_file(atlas_path)
    if atlas_hash != EXPECTED_ATLAS_SHA256:
        failures.append(
            f"atlas sha256 {atlas_hash} != expected {EXPECTED_ATLAS_SHA256}"
        )

    details = {}
    for point_id, expected in EXPECTED.items():
        item = by_point.get(point_id)
        if item is None:
            failures.append(f"missing {point_id}")
            continue
        notes = str(item.get("notes", ""))
        detail = {
            "body_region": item.get("body_region"),
            "expected_body_region": expected["body_region"],
            "notes": notes,
            "expected_approximation_rule": expected["rule"],
            "face_index": item.get("face_index"),
            "vertex_indices": item.get("vertex_indices"),
            "barycentric": item.get("barycentric"),
            "canonical_local_position_m": item.get("canonical_local_position_m"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }
        details[point_id] = detail
        if detail["body_region"] != expected["body_region"]:
            failures.append(
                f"{point_id} body_region {detail['body_region']} != {expected['body_region']}"
            )
        for marker in (
            "SIMULATED_FROM_REFERENCE",
            "medical_validated=false",
            expected["rule"],
        ):
            if marker not in notes:
                failures.append(f"{point_id} notes missing {marker!r}")

    level_ids = ["GV14_MIDLINE", "SI15_LEFT", "SI15_RIGHT"]
    level_y = {
        point_id: float(by_point[point_id]["canonical_local_position_m"][1])
        for point_id in level_ids
        if point_id in by_point
    }
    if len(level_y) != 3:
        failures.append("cannot compute GV14/SI15 canonical local Y range")
        level_range_m = None
        pairwise = {}
    else:
        level_range_m = max(level_y.values()) - min(level_y.values())
        pairwise = {
            "GV14_to_SI15_LEFT_abs_m": abs(
                level_y["GV14_MIDLINE"] - level_y["SI15_LEFT"]
            ),
            "GV14_to_SI15_RIGHT_abs_m": abs(
                level_y["GV14_MIDLINE"] - level_y["SI15_RIGHT"]
            ),
            "SI15_LEFT_to_RIGHT_abs_m": abs(
                level_y["SI15_LEFT"] - level_y["SI15_RIGHT"]
            ),
        }

    result = {
        "pass": not failures,
        "failures": failures,
        "atlas_sha256": atlas_hash,
        "expected_atlas_sha256": EXPECTED_ATLAS_SHA256,
        "reselected_points": details,
        "canonical_local_y_m": level_y,
        "canonical_local_y_pairwise_abs_m": pairwise,
        "canonical_local_y_max_range_m": level_range_m,
        "canonical_local_y_max_range_mm": (
            level_range_m * 1000.0 if level_range_m is not None else None
        ),
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
