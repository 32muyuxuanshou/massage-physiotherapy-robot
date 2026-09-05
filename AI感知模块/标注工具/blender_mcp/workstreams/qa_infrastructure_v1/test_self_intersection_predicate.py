from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from self_intersection_probe import nonadjacent_overlaps


def main() -> int:
    cases = {}

    separate_vertices = [
        (-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0),
        (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (0.0, 1.0, 1.0),
    ]
    separate_triangles = [(0, 1, 2), (3, 4, 5)]
    separate, _, _ = nonadjacent_overlaps(separate_vertices, separate_triangles, 1e-7)
    cases["separate_triangles"] = {"passed": not separate, "pairs": separate}

    crossing_vertices = [
        (-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0),
        (0.0, -0.5, -1.0), (0.0, -0.5, 1.0), (0.0, 0.8, 0.0),
    ]
    crossing_triangles = [(0, 1, 2), (3, 4, 5)]
    crossing, _, _ = nonadjacent_overlaps(crossing_vertices, crossing_triangles, 1e-7)
    cases["crossing_triangles"] = {"passed": crossing == [(0, 1)], "pairs": crossing}

    adjacent_vertices = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)
    ]
    adjacent_triangles = [(0, 1, 2), (1, 3, 2)]
    adjacent, _, _ = nonadjacent_overlaps(adjacent_vertices, adjacent_triangles, 1e-7)
    cases["adjacent_surface"] = {"passed": not adjacent, "pairs": adjacent}

    report = {
        "schema": "self-intersection-predicate-self-test-v1",
        "passed": all(case["passed"] for case in cases.values()),
        "cases": cases,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
