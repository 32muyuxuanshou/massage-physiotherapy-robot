from __future__ import annotations

import json

from triangle_narrow_phase import analyze_triangle_pair


def main() -> int:
    cases = {
        "parallel_separate": (
            [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            [(0, 0, 1), (1, 0, 1), (0, 1, 1)],
            False,
        ),
        "aabb_overlap_but_coplanar_disjoint": (
            [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            [(.75, .75, 0), (1.75, .75, 0), (.75, 1.75, 0)],
            False,
        ),
        "noncoplanar_crossing": (
            [(-1, -1, 0), (1, -1, 0), (0, 1, 0)],
            [(0, -.5, -1), (0, -.5, 1), (0, .8, 0)],
            True,
        ),
        "coplanar_area": (
            [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            [(.2, .2, 0), (.8, .2, 0), (.2, .8, 0)],
            True,
        ),
        "point_contact": (
            [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            [(0, 0, 0), (0, 0, 1), (-1, 0, 0)],
            False,
        ),
    }
    rows = {}
    for name, (first, second, expected) in cases.items():
        result = analyze_triangle_pair(first, second)
        rows[name] = {
            "expected_confirmed": expected,
            "actual_confirmed": result.confirmed_overlap,
            "classification": result.classification,
            "passed": result.confirmed_overlap is expected,
        }
    report = {"schema": "triangle-narrow-phase-self-test-v1", "passed": all(row["passed"] for row in rows.values()), "cases": rows}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
