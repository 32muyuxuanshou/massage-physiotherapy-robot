"""A-only mechanical output exchanges on the 16 old prespecified frames.

Supporting diagnostic only; every translation uses saved Camera A mesh/camera,
never observed Camera B data. No fitting or new model inference.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import numpy as np
from run_r41_txyz import dependencies,summary


def one(task):
    work,key,seed=task;work=Path(work);assets=work/'assets';f=dependencies(work/'code')
    o=np.load(assets/'original_assets/official'/(key+'.npz'))
    g=np.load(assets/f'r4/formal/g1_seed{seed}/real'/(key+'.npz'))
    corrected_g=np.load(work/f'corrected/g1_seed{seed}'/(key+'.npz'))
    corrected_o=np.load(work/'corrected/official'/(key+'.npz'))
    camera_delta=(g['pred_cam_t']-o['pred_cam_t']).reshape(3)
    centroid_delta=corrected_o['vertices_camera_A'].mean(0)-corrected_g['vertices_camera_A'].mean(0)
    meshes=dict(official_body_g1_camera=o['vertices_camera_A']+camera_delta,
        g1_body_official_camera=g['vertices_camera_A']-camera_delta,
        g1_corrected_centroid_to_official_corrected=corrected_g['vertices_camera_A']+centroid_delta)
    a=np.load(assets/'original_assets/inputs'/(key+'.npz'));ca={k:a['A_'+k] for k in ['R','T']};cb={k:a['B_'+k] for k in ['R','T']}
    faces=np.load(assets/'original_assets/official/faces.npy')
    # Only evaluate after all three mechanical transformations are fixed.
    points=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    metrics={name:summary(f['distance'](points,f['transform_camera'](v,ca,cb),faces)*1000) for name,v in meshes.items()}
    return dict(key=key,seed=seed,metrics=metrics,camera_delta_xyz_mm=(camera_delta*1000).tolist(),
        centroid_normalization_xyz_mm=(centroid_delta*1000).tolist())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    selected=json.loads((a.work/'assets/original_assets/VISUAL_SELECTION.json').read_text())['records']
    tasks=[(str(a.work),f"{r['sequence']}_{r['frame']:06d}",s) for s in [11,23,37] for r in selected]
    with ProcessPoolExecutor(max_workers=6) as pool:records=list(pool.map(one,tasks))
    (a.work/'AUXILIARY_COMPONENTS.json').write_text(json.dumps(dict(status='COMPLETE',selection='16 unchanged R3.1 historical development frames x 3 seeds',
        camera_B_alignment=False,records=records,limitation='Mechanical saved-output diagnostic on selected frames; not causal training decomposition, not primary 232-frame result.'),indent=2))
    print('AUXILIARY_COMPLETE',len(records),flush=True)
