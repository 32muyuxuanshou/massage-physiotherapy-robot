"""PVE and fixed held-out sensor evaluation; only Official gets historical Txyz."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from metrics import map_mhr_to_smpl,evaluate_vertices,sha256

def summary_mm(distance_m):
    d=distance_m*1000
    return {'median_mm':float(np.median(d)),'p95_mm':float(np.percentile(d,95)),
            'coverage_50mm':float(np.mean(d<=50)),'count':len(d)}

def main():
    p=argparse.ArgumentParser()
    for n in ['root','r41-code','prediction-manifest']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--official',action='store_true');a=p.parse_args()
    a.root=a.root.resolve()
    sys.path.insert(0,str(a.r41_code))
    from run_r41_txyz import dependencies
    functions=dependencies(a.r41_code)
    paths=json.loads((a.root/'PATHS.json').read_text());faces=np.load(paths['faces'])
    mapping=Path(paths['mhr_to_smpl_mapping'])
    source=json.loads(a.prediction_manifest.read_text());seed=source['seed']
    cell=f'official_s{seed}' if a.official else f"{source['mode']}_s{seed}_{source['checkpoint']}"
    out=a.root/'evaluation'/cell;out.mkdir(parents=True,exist_ok=True);records=[]
    with np.load(paths['anchors']) as z:fi,bc=z['face_index'],z['barycentric']
    for row in source['records']:
        if sha256(row['prediction_file'])!=row['prediction_sha256']:raise ValueError('Prediction changed before evaluation')
        with np.load(row['prediction_file']) as z:
            vertices=z['vertices_camera_A'].astype(np.float64)
            native={k:z[k] for k in z.files if k not in ['pred_keypoints_2d','pred_keypoints_2d_verts']}
        with np.load(row['input_file']) as z:
            A_points=z['K0_points_m'];R0=z['K0_R'];t0=z['K0_t']
        methods={cell:vertices};translation=None
        if a.official:
            anchors=(vertices[faces[fi]]*bc[:,:,None]).sum(1)
            raw,applied,trace,fallback=functions['fit_txyz'](A_points,anchors)
            methods[cell+'_txyz']=vertices+applied
            translation={'raw_m':raw.tolist(),'applied_m':applied.tolist(),'fallback':fallback,'trace':trace}
            corrected=dict(native,vertices_camera_A=vertices+applied,pred_cam_t=native['pred_cam_t']+applied,
                           raw_translation_m=raw,applied_translation_m=applied)
            np.savez_compressed(out/(row['sequence']+'_'+row['frame']+'_txyz.npz'),**corrected)
        # Reference and held-out sensor files are opened only after A fit is fixed.
        if sha256(row['reference_file'])!=row['reference_sha256'] or sha256(row['heldout_file'])!=row['heldout_sha256']:
            raise ValueError('Frozen evaluation evidence changed')
        reference=np.load(row['reference_file'])['vertices_camera_m']
        with np.load(row['heldout_file']) as heldout:
            for name,v in methods.items():
                mapped=map_mhr_to_smpl(v,faces,mapping);pve=evaluate_vertices(mapped,reference)
                per={};residual={'mapped_smpl_vertices_camera_m':mapped,
                                  'corresponding_vertex_error_mm':np.linalg.norm(mapped-reference,axis=1)*1000}
                for k in [1,2,3]:
                    points=heldout[f'K{k}_points_m'];R=heldout[f'K{k}_R'];t=heldout[f'K{k}_t']
                    target=(v@R0.T+t0-t)@R
                    distances=functions['distance'](points,target,faces)
                    per[f'K{k}']=summary_mm(distances);residual[f'K{k}_distance_mm']=distances*1000
                key=row['sequence']+'_'+row['frame']
                dist_path=out/(key+'_'+name+'_distances.npz');np.savez_compressed(dist_path,**residual)
                records.append({'cell':name,'seed':seed,'subject':row['subject'],'sequence':row['sequence'],'frame':row['frame'],
                    'pve':pve,'heldout_surface':per,'frame_surface_camera_equal_mean':{
                    k:float(np.mean([x[k] for x in per.values()])) for k in ['median_mm','p95_mm','coverage_50mm']},
                    'prediction_sha256':row['prediction_sha256'],'heldout_sha256':row['heldout_sha256'],
                    'reference_sha256':row['reference_sha256'],'txyz':translation if name.endswith('_txyz') else None,
                    'distances_file':str(dist_path)})
        if len(records)%20==0:print('EVALUATED_RECORDS',cell,len(records),flush=True)
    report={'status':'EVALUATION_COMPLETE','records':records,'source_manifest_sha256':sha256(a.prediction_manifest),
            'mapping_sha256':sha256(mapping),'new_model_Txyz':False,'camera_B_fit':False,
            'pve_scope':'Fixed official approximate MHR→SMPL mapping against fitted reference; M3 exact protocol unconfirmed',
            'surface_scope':'Same original fixed K1/K2/K3 points to exact triangles; no B fitting'}
    (out/'RESULTS.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
