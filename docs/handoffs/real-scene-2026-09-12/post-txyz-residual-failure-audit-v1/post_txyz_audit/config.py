from pathlib import Path

EXPECTED_SUBJECTS = {"Sub03", "Sub04", "Sub05", "Sub06", "Sub07"}
EXPECTED_FRAMES = 45
EXPECTED_SEQUENCES = 15
HELDOUT_CAMERAS = ("K1", "K2", "K3")
V23_RELATIVE = Path("docs/handoffs/real-scene-2026-09-11/behave-cheap-txyz-generalization-v2/results-v2.3")
KNOWN_ZERO_OF_THREE = ("Sub07", "Date06_Sub07_stool_sit", "t0038.000")
