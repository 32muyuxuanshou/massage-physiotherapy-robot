"""Finish authorized acquisition, then construct the adult CT source dataset.

This executes source preparation only. It does not launch a model experiment.
"""
import json
import os
import subprocess
import sys
import time

from acquire_full_v3 import ROOT, MD5, BYTES


def main():
    parent_download_pid = int(sys.argv[1])
    while not (ROOT/'DOWNLOAD_RESULT.json').exists():
        # Stop on a real failed download; do not silently create alternate data.
        state = subprocess.run(['ps', '-p', str(parent_download_pid), '-o', 'stat='], capture_output=True, text=True).stdout.strip()
        if not state or state.startswith('Z'):
            raise RuntimeError('DOWNLOAD_PROCESS_ENDED_WITHOUT_AUTHOR_CHECKSUM_PASS')
        time.sleep(30)
    receipt = json.loads((ROOT/'DOWNLOAD_RESULT.json').read_text())
    assert receipt['status']=='PASS' and receipt['actual_md5']==MD5
    assert (ROOT/receipt['filename']).stat().st_size==BYTES
    print('OFFICIAL_SOURCE_CHECKSUM_PASS; starting adult source preparation', flush=True)
    env=os.environ.copy()
    env['TMPDIR']=str(ROOT/'tmp');env['MPLCONFIGDIR']=str(ROOT/'mpl_cache')
    env['PYTHONPATH']='/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005/deps'
    env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
    subprocess.run([sys.executable, str(ROOT/'code/build_field_dataset.py'), '--all-adult', '--workers', '8', '--resume'],
                   env=env, check=True)
    print('ADULT_CT_SOURCE_PREPARATION_COMPLETE; no new model evaluation launched', flush=True)


if __name__=='__main__':
    main()
