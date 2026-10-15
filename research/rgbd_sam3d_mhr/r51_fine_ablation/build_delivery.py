"""Public audit package only: no data, mesh NPZ, or checkpoints."""
import json,shutil
from pathlib import Path

ROOT=Path('output/r51_fine_supervision_ablation_v1')
DEST=Path('docs/handoffs/real-scene-2026-10-15/r51-fine-supervision-ablation-v1')
SOURCE=Path('research/rgbd_sam3d_mhr/r51_fine_ablation')


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    for directory in ['code','reports','evidence','historical_code']:(DEST/directory).mkdir(exist_ok=True)
    for p in SOURCE.iterdir():
        if p.suffix in ['.py','.json','.md']:shutil.copy2(p,DEST/'code'/p.name)
    for p in (ROOT/'reports').iterdir():
        if p.is_file():shutil.copy2(p,DEST/'reports'/p.name)
    for p in (ROOT/'historical_code').glob('*.py'):shutil.copy2(p,DEST/'historical_code'/p.name)
    names=['DATA_MANIFEST.json','DATA_RESTORE_RECEIPT.json','SCAN_TRANSFER_RECEIPT.json','DATA_READY.json',
        'EXECUTION_LEDGER.json','EXECUTION_ENVIRONMENT.txt','L2_CALIBRATION.json','SCIENCE_FREEZE.json',
        'SELECTION_FREEZE.json','PREFLIGHT.json','FULL_FORWARD_REINSERTION_QA.json','REAL_EVALUATOR_PILOT.json',
        'REAL_EVALUATION_INDEX.json','REAL_EVALUATION_COMPLETE.json','POST_INTEGRITY.json','FIGURE_SELECTION.json',
        'BACKUP_RECEIPT_training.json','BACKUP_RECEIPT_inputs.json','BACKUP_RECEIPT_final.json']
    for name in names:
        p=ROOT/name
        if p.exists():shutil.copy2(p,DEST/'evidence'/name)
    # Keep all evaluated synthetic epoch records, not only aggregate selections.
    (DEST/'synthetic_validation').mkdir(exist_ok=True)
    for p in ROOT.glob('BASELINE_s*.json'):shutil.copy2(p,DEST/'synthetic_validation'/p.name)
    for d in (ROOT/'runs').iterdir():
        if not d.is_dir():continue
        target=DEST/'synthetic_validation'/d.name;target.mkdir(exist_ok=True)
        for p in d.glob('*.json'):shutil.copy2(p,target/p.name)
    print('PUBLIC_PACKAGE_READY',len([p for p in DEST.rglob('*') if p.is_file()]))


if __name__=='__main__':main()
