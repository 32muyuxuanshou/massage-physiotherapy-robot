from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--evidence", required=True, type=Path); parser.add_argument("--delivery", required=True, type=Path); args = parser.parse_args()
    evidence = args.evidence.resolve(); delivery = args.delivery.resolve(); attachments = delivery / "附件"; attachments.mkdir(parents=True, exist_ok=True)
    mapping = {
        "01_最终验证.json": evidence / "verification.json",
        "02_冻结解码合同.json": evidence / "BOUNDARY_HYBRID_DECODER_CONTRACT_V1.json",
        "03_冻结时间与保护输入.json": evidence / "decoder_contract_freeze_receipt.json",
        "04_Validation评估.json": evidence / "validation_decoder_evaluation.json",
        "05_UntouchedTest评估.json": evidence / "untouched_test_decoder_evaluation.json",
        "06_核心指标.csv": evidence / "decoder_contract_summary.csv",
        "07_新人体选择与拒绝记录.json": evidence / "qualified_new_geometry.json",
        "08_新人体几何确定性.json": evidence / "selected_geometry_determinism.json",
        "09_结果总览.png": evidence / "visuals" / "decoder_contract_untouched_test_summary.png",
        "10_未触碰测试代表图.png": evidence / "visuals" / "untouched_test_montage.png",
        "11_Validation预测确定性.json": evidence / "validation_decoder_determinism.json",
        "12_UntouchedTest预测确定性.json": evidence / "untouched_test_decoder_determinism.json",
        "13_数值保护单元测试.json": evidence / "decoder_guard_unit_tests.json",
    }
    for name, source in mapping.items(): shutil.copy2(source, attachments / name)
    main_doc = next(delivery.glob("*.md")); files = [main_doc, *sorted(attachments.iterdir())]
    manifest = attachments / "14_SHA256SUMS.txt"
    manifest.write_text("".join(f"{sha(path)}  {path.relative_to(delivery).as_posix()}\n" for path in files), encoding="utf-8")
    print(f"main={main_doc}\nattachments={len(list(attachments.iterdir()))}\nmain_sha256={sha(main_doc)}")


if __name__ == "__main__": main()
