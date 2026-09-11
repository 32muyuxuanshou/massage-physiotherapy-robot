"""Static Track C readiness check; deliberately refuses formal benchmark execution."""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

def main() -> None:
    readiness = json.loads((HERE / "SYNTHETIC_DMD37_READINESS_V2.json").read_text(encoding="utf-8"))
    protocol = json.loads((HERE / "SYNTHETIC_DMD37_PROTOCOL_V2.json").read_text(encoding="utf-8"))
    assert readiness["status"] == "SYNTHETIC_DMD37_NOT_READY"
    assert readiness["formal_benchmark_generated"] is False
    assert readiness["atlas_release_gate"]["status"] == "BLOCKED"
    assert protocol["gt_contract"]["bridge_forbidden_in_gt"] is True
    assert protocol["systems"] == ["O", "A", "C", "G"]
    required = ["C_camera_projection_contract", "D_rendered_depth_z_contract", "E_rgb_depth_mask_alignment", "F_visibility_contract_frozen", "I_evaluation_metrics_frozen"]
    assert all(readiness["checks"][key]["status"].startswith("PASS") for key in required)
    print("SYNTHETIC_DMD37_READINESS_V2=PASS_CONTRACTS_ONLY_ATLAS_BLOCKED")

if __name__ == "__main__":
    main()
