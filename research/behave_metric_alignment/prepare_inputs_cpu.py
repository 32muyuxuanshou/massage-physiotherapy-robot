"""Freeze model input and A/B/C/D sensor indices before any new model forward."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import trimesh
from dataset_io import camera,sensor,fixed_indices,world_to_local,pinhole_input

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--limit',type=int);a=p.parse_args()
    a.root=a.root.resolve()
    data=a.root/'data';manifest=json.loads((data/'FROZEN_INPUT_MANIFEST.json').read_text())
    out=a.root/('inputs_smoke' if a.limit else 'inputs');out.mkdir(parents=True,exist_ok=True);cams=[camera(data/'calibs','Date03',k) for k in range(4)]
    results=[]
    selected=manifest['rows'][:a.limit] if a.limit else manifest['rows']
    for r in selected:
        key=r['sequence']+'_'+r['frame'];frame=data/'sequences'/r['sequence']/r['frame']
        file=out/(key+'.npz');values={};QA=[]
        for k,cam in enumerate(cams):
            rgb,d,m,points,flat=sensor(frame,k,cam)
            indices=fixed_indices(len(points),key+f':K{k}',5000 if k==0 else 2048)
            if len(indices)==0:raise ValueError('Empty actual sensor support: '+key+f' K{k}')
            values.update({f'K{k}_points_m':points[indices].astype(np.float32),f'K{k}_source_pixel_indices':flat[indices],
                           f'K{k}_R':cam['R'],f'K{k}_t':cam['t']})
            QA.append({'camera':f'K{k}','valid_point_count':len(points),'sample_count':len(indices),
                       'selected_source_indices_sha256':hashlib.sha256(flat[indices].tobytes()).hexdigest()})
            if k==0:
                image,depth,mask,bbox=pinhole_input(rgb,d,m,cam)
                values.update(rgb=image,depth_m=depth,mask=mask,bbox=bbox,K=cam['K'],original_dist=cam['dist'])
        ref=trimesh.load(frame/'person/fit02/person_fit.ply',process=False)
        if ref.vertices.shape!=(6890,3):raise ValueError('Reference topology changed')
        # Reference and held-out points are evaluation-only, never in the model input NPZ.
        reference=world_to_local(np.asarray(ref.vertices),cams[0]);ref_file=out/(key+'_reference.npz')
        np.savez_compressed(ref_file,vertices_camera_m=reference,faces=np.asarray(ref.faces))
        heldout={k:values.pop(k) for k in list(values) if k.startswith(('K1_','K2_','K3_'))}
        B_file=out/(key+'_heldout.npz');np.savez_compressed(B_file,**heldout)
        np.savez_compressed(file,**values)
        results.append(dict(r,input_file=str(file),input_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                            reference_file=str(ref_file),reference_sha256=hashlib.sha256(ref_file.read_bytes()).hexdigest(),
                            heldout_file=str(B_file),heldout_sha256=hashlib.sha256(B_file.read_bytes()).hexdigest(),sensor_qa=QA))
        if len(results)%20==0:print('INPUTS_PREPARED',len(results),len(manifest['rows']),flush=True)
    report={'status':'SMOKE_CPU_INPUTS' if a.limit else 'FROZEN_CPU_INPUTS_BEFORE_NEW_MODEL_INFERENCE','records':results,
            'source_manifest_sha256':hashlib.sha256((data/'FROZEN_INPUT_MANIFEST.json').read_bytes()).hexdigest(),
            'input_domain':'All methods: K0 RGB LINEAR undistortion, registered axial Z and person mask NEAREST undistortion, destination K equals released K; 25 px mask bbox padding; no detector',
            'sensor_evaluation_domain':'Original measured color-camera coordinates, precomputed original ray table, no geometric fitting or depth interpolation',
            'K0_point_limit':5000,'heldout_camera_point_limit':2048,
            'reference_and_heldout_in_model_input':False,'models_trained':False,'HuMMan_TEST_read':False}
    (out/'INPUT_MANIFEST.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'status':report['status'],'frames':len(results)},indent=2),flush=True)

if __name__=='__main__':main()
