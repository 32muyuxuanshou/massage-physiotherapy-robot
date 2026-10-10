"""Restore exact private R4.1 geometry plus its existing R3.1/R4 dependencies."""
import argparse
import shutil
import tarfile
from pathlib import Path


def extract_selected(archive,root,accept,prefix=''):
    with tarfile.open(archive) as t:
        for m in t:
            if m.isfile() and accept(m.name):
                target=root/prefix/m.name
                assert target.resolve().is_relative_to(root.resolve())
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('wb') as out:shutil.copyfileobj(t.extractfile(m),out)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--r41',type=Path,required=True);p.add_argument('--r31',type=Path,required=True)
    p.add_argument('--r4',type=Path,required=True);p.add_argument('--historical-results',type=Path,required=True)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False)
    extract_selected(a.r41,a.work,lambda n:True)
    extract_selected(a.work/'original_assets.tar.gz',a.work/'assets',lambda n:True)
    extract_selected(a.r31,a.work/'assets',lambda n:n in ['runs/r31_diagnosis_pilot_v1/txyz/FROZEN_ANCHORS.npz',
        'runs/r31_diagnosis_pilot_v1/txyz/CAMERA_A_FIT_INDICES.json'] or '/txyz/txyz/official/' in n)
    extract_selected(a.r4,a.work/'assets/r4',lambda n:n.startswith('formal/') and '/real/' in n and
        (n.endswith('.npz') or n.endswith('faces.npy') or n.endswith('HUMMAN_RESULTS.json')))
    shutil.copyfile(a.historical_results,a.work/'HISTORICAL_TXYZ.json')
    print('RESTORE_COMPLETE_NO_TEST_OR_TRAINING_ASSETS_EXTRACTED')
