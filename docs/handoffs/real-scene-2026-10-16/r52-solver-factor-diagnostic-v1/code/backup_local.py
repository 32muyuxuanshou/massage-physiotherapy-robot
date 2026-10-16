"""Reuse the already verified direct-SFTP range backup implementation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'r51_fine_ablation'))
import backup_windows
backup_windows.OUT=Path('output/r52_solver_factor_diagnostic_v1')
backup_windows.REMOTE='/raid5/xuhd/rgbd_sam3d/r52_solver_factor_diagnostic_v1'


if __name__=='__main__':backup_windows.main('final')
