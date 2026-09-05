from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from boundary_hybrid_decoder import decode_guarded  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", required=True, type=Path); args = parser.parse_args()
    cases = []; yy, xx = np.mgrid[0:32, 0:40]
    for cx, cy in [(-0.25, -0.20), (39.20, -0.10), (-0.15, 31.25), (39.25, 31.20)]:
        logits = (-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 1.35 ** 2))[None, None].astype(np.float32)
        out = decode_guarded(logits); cases.append({"center": [cx, cy], "branch_used": bool(out["branch_used"][0, 0]), "fallback": int(out["fallback_code"][0, 0])})
    flat = decode_guarded(np.zeros((1, 1, 32, 40), np.float32))
    checks = {"four_corners_accepted": all(c["branch_used"] and c["fallback"] == 0 for c in cases),
              "flat_logits_fallback": int(flat["fallback_code"][0, 0]) != 0 and not bool(flat["branch_used"][0, 0])}
    payload = {"schema": "boundary-hybrid-decoder-unit-tests-v1", "passed": all(checks.values()), "checks": checks,
               "corner_cases": cases, "flat_fallback_code": int(flat["fallback_code"][0, 0])}
    path = args.root.resolve() / "decoder_guard_unit_tests.json"; path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(payload)
    if not payload["passed"]: raise SystemExit(2)


if __name__ == "__main__": main()
