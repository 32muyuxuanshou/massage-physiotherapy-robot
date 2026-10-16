"""Public review files only; point clouds, body NPZ and private archives stay out."""
import gzip,shutil
from pathlib import Path

ROOT=Path('output/r52_solver_factor_diagnostic_v1')
DEST=Path('docs/handoffs/real-scene-2026-10-16/r52-solver-factor-diagnostic-v1')
SOURCE=Path('research/rgbd_sam3d_mhr/r52_solver_diagnostic')


def main():
    for d in ['code','reports','evidence','historical_code']:(DEST/d).mkdir(parents=True,exist_ok=True)
    for p in SOURCE.iterdir():
        if p.suffix in ['.py','.md','.json']:shutil.copy2(p,DEST/'code'/p.name)
    for p in (ROOT/'reports').iterdir():
        if not p.is_file():continue
        if p.suffix=='.json' and p.stat().st_size>45000000:
            with p.open('rb') as a,gzip.open(DEST/'reports'/(p.name+'.gz'),'wb',compresslevel=6) as b:shutil.copyfileobj(a,b)
        else:shutil.copy2(p,DEST/'reports'/p.name)
    for p in ROOT.glob('*.json'):shutil.copy2(p,DEST/'evidence'/p.name)
    previous=Path('output/r5_focused_diagnostics_v1/geometry/historical_code')
    for p in previous.glob('*.py'):shutil.copy2(p,DEST/'historical_code'/p.name)
    # Two actual corrected preflight errors, retained for audit.
    for name in ['prepare.log','evaluator_qa_initial_reference_key_error.log']:
        if (ROOT/name).exists():shutil.copy2(ROOT/name,DEST/'evidence'/name)
    print('PUBLIC_DELIVERY_READY',sum(p.is_file() for p in DEST.rglob('*')))


if __name__=='__main__':main()
