"""Reopen every actual input/prediction; report all-method common-hit comparisons."""
import json
from pathlib import Path

import numpy as np

from evaluate_pilot import surface_position
from prepare_pilot import OUT, sha, write


def main():
    rows=json.loads((OUT/'PER_CASE_RESULTS.json').read_text())
    manifest={r['subject']:r for r in json.loads((OUT/'CASE_MANIFEST.json').read_text()) if r['eligible']}
    checks=[];common=[]
    for subject,m in manifest.items():
        data=dict(np.load(m['path']));assert sha(Path(m['path']))==m['input_sha256']
        current=[r for r in rows if r['subject']==subject];caches=[]
        for row in current:
            cache=dict(np.load(row['path']));assert sha(Path(row['path']))==row['cache_sha256']
            assert np.array_equal(cache['target_valid'],data['target_valid'])
            assert np.array_equal(cache['target_xyz_mm'],data['target_xyz_mm'])
            scale=np.diff(data['xz_bounds_mm'].reshape(2,2),axis=1).ravel()
            expected=np.linalg.norm((cache['pred_uv']-data['target_uv'])*scale[None],axis=1)
            assert np.allclose(expected,cache['xz_error_mm'],rtol=0,atol=1e-6)
            for i,p in enumerate(cache['pred_uv']):
                position=surface_position(p,data)
                assert (position is not None)==bool(cache['surface_hit'][i])
                if position is not None:
                    assert np.allclose(position,cache['pred_xyz_mm'][i],rtol=0,atol=1e-6)
            caches.append((row,cache));checks.append(dict(subject=subject,method=row['method'],seed=row['seed'],status='PASS'))
        valid=data['target_valid'].astype(bool)
        shared=valid & np.logical_and.reduce([c['surface_hit'] for _,c in caches])
        for method in sorted(set(r['method'] for r in current)):
            values=[c['xyz_error_mm'][shared] for r,c in caches if r['method']==method]
            common.append(dict(subject=subject,role=m['role'],method=method,valid_targets=int(valid.sum()),common_hits=int(shared.sum()),
                               common_hit_fraction=float(shared.sum()/valid.sum()),
                               seed_mean_xyz_mm=[float(v.mean()) if len(v) else None for v in values],
                               all_method_shared_level_ids=np.flatnonzero(shared).tolist()))
    write(OUT/'CACHE_REPLAY.json',dict(status='PASS',actual_inputs=len(manifest),actual_predictions=len(checks),checks=checks,
          scope='actual bytes and X/Z metrics plus native CT surface interpolation; no new fitting'))
    write(OUT/'COMMON_HIT_RESULTS.json',common)
    print('REPLAY_PASS',len(manifest),len(checks),flush=True)


if __name__=='__main__':main()
