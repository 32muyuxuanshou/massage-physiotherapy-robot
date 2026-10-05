"""Replay every dense field from cached CT proxy coordinates, no CT decoding."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = json.loads((ROOT/'structure_check/CASE_MANIFEST.json').read_text())
    maximum = 0.; valid_points = 0
    canvas = Image.new('RGB', (1800, 1680), 'white')
    for i, row in enumerate(rows):
        case = row['case']; path=ROOT/'structure_check'/case/'field_pack.npz'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['pack_sha256']
        with np.load(path) as data:
            points=data['points_ras_mm']; xyz=data['level_xyz_mm']; flags=data['level_valid']
            reverse=np.flatnonzero(flags)[::-1]; zz=xyz[reverse,2]
            longitudinal=(np.interp(points[:,2],zz,reverse)-3.)/11.
            lateral=points[:,0]-np.interp(points[:,2],zz,xyz[reverse,0])
            expected=np.column_stack([longitudinal,lateral/500.])
            maximum=max(maximum,float(np.abs(expected-data['anatomical_coordinates']).max()))
            mask=(points[:,2]>=zz[0])&(points[:,2]<=zz[-1])&(np.abs(lateral)<150)
            assert np.array_equal(mask,data['anatomy_valid'])
            assert np.array_equal(flags[[3,14]],data['reference_present'])
            assert len(np.unique(data['sample_surface_indices']))==len(points)==8192
            valid_points+=int(mask.sum())
        im=Image.open(ROOT/'structure_check'/case/'CT_SURFACE_REFERENCE.png');im.thumbnail((1800,420))
        canvas.paste(im,(0,i*420))
    assert maximum<1e-6
    canvas.save(ROOT/'figures/source_18_level_montage.jpg',quality=90)
    receipt=dict(status='PASS',cases=len(rows),points=len(rows)*8192,anatomy_valid_points=valid_points,
                 max_field_difference=maximum,clinical_GT=False,source='four previously used v2 TRAIN images, not V3 or test')
    (ROOT/'structure_check/CACHE_REPLAY.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    main()
