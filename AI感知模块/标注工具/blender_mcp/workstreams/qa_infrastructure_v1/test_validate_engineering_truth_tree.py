from __future__ import annotations

from validate_engineering_truth_tree import walk


def main() -> int:
    findings: list[dict] = []
    warnings: list[dict] = []

    # `truth_status` is intentionally an object in current delivery reports.
    # The validator must recurse into it rather than attempting a set lookup.
    walk(
        {
            "truth_status": {
                "kind": "engineering_reference",
                "medical_truth": False,
                "medical_validated": False,
            }
        },
        "",
        findings,
        warnings,
    )
    assert findings == []

    walk({"medical_truth": True}, "", findings, warnings)
    assert findings == [
        {"path": "medical_truth", "reason": "medical truth flag must remain false"}
    ]
    print("truth-tree validator regression tests: 2/2 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
