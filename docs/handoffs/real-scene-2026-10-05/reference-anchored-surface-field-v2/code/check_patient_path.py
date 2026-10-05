"""All twenty previous patient meshes; structural predictions, no accuracy claim."""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from anchored_field import AnchoredField
from patient_interface import infer_patient, frame_and_references
from reference_frame import to_local

ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=ROOT.parent/'prone-reference-rule-workbench-v1'
sys.path.insert(0,str(PREVIOUS/'code'))
from check_pipeline import fixture, verify


def main():
    torch.set_num_threads(4);start=time.time()
    checkpoint=Path(__file__).resolve().parents[5]/'output/reference_anchored_surface_field_v2/STRUCTURE_ONLY_HARD_JOINT.pt'
    model=AnchoredField();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()
    output=ROOT/'patient_paths';output.mkdir(exist_ok=True);records=[]
    for path in sorted((PREVIOUS/'site/cases').glob('*.json')):
        mesh=json.loads(path.read_text());subject=mesh['subject'];all_refs=fixture(mesh)
        refs={k:all_refs[k] for k in ['T3','L2','LEFT_REF','RIGHT_REF']}
        vertices=np.asarray(mesh['vertices_m']);rng=np.random.default_rng(int(hashlib.sha256(subject.encode()).hexdigest()[:8],16))
        observed_idx=rng.choice(len(vertices),512,replace=False)
        result=infer_patient(mesh,vertices[observed_idx],refs,[0.,0.,0.],model)
        reconstruction_error=verify(mesh,result['rules'])
        frame,_=frame_and_references(mesh,refs,[0.,0.,0.]);local=to_local(vertices,frame)
        for slot in result['suggestions'].values():
            ids={g:i for i,g in enumerate(mesh['global_face_ids'])};xyz=np.asarray(slot['barycentric'])@vertices[np.asarray(mesh['faces'])[ids[slot['face_id']]]]
            assert np.linalg.norm(xyz-slot['xyz_m'])<1e-10
        cache=output/(subject+'.npz')
        np.savez_compressed(cache,vertices_m=vertices,faces=mesh['faces'],global_face_ids=mesh['global_face_ids'],
                            observed_vertex_indices=observed_idx,local_query=local,
                            learned_field=result.pop('learned_field'),ray_delta_mm=result.pop('ray_delta_mm'))
        result.update(subject=subject,mesh_sha256=mesh['mesh_sha256'],public_input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
                      max_rule_reconstruction_error_m=reconstruction_error,
                      observation_origin='MESH_SAMPLED_INTERFACE_FIXTURE_NOT_SENSOR_DEPTH',
                      reference_origin='FOUR_GEOMETRY_FIXTURES_NOT_MEDICAL_REFERENCES')
        (output/(subject+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        with np.load(cache) as z:field=z['learned_field'];ray_delta=z['ray_delta_mm']
        fig,axes=plt.subplots(1,3,figsize=(12,4))
        axes[0].scatter(local[:,0]*500,local[:,2]*500,c='lightgray',s=3)
        for key,slot in result['suggestions'].items():
            point=to_local(np.asarray(slot['xyz_m'])[None],frame)[0]
            axes[0].scatter(point[0]*500,point[2]*500,s=25);axes[0].annotate(key,(point[0]*500,point[2]*500),fontsize=7)
        axes[0].set_title('Actual mesh / structural proxy slots')
        sc=axes[1].scatter(local[:,0]*500,local[:,2]*500,c=field[:,0],s=4,cmap='viridis');fig.colorbar(sc,ax=axes[1]);axes[1].set_title('Coordinate field; accuracy not tested')
        sc=axes[2].scatter(local[:,0]*500,local[:,2]*500,c=ray_delta,s=4,cmap='coolwarm');fig.colorbar(sc,ax=axes[2]);axes[2].set_title('Raw ray delta; NOT applied (mm)')
        for ax in axes:ax.set_aspect('equal');ax.invert_yaxis();ax.set_xlabel('local right (mm)');ax.set_ylabel('local inferior (mm)')
        fig.suptitle(subject+' | 4 TRAIN source check weights | reference fixtures | NOT clinical',fontsize=9)
        fig.tight_layout();fig.savefig(ROOT/'figures'/(subject+'.png'),dpi=120);plt.close(fig)
        records.append(dict(subject=subject,cache_sha256=result['cache_sha256'],max_rule_reconstruction_error_m=reconstruction_error,
                            ambiguous_suggestion_slots=sum(s['exact_chart_candidate_faces']>1 for s in result['suggestions'].values())))
    report=dict(status='TWENTY_ACTUAL_MESH_INTERFACE_PATH_PASS_NOT_ACCURACY_VALIDATION',patients=len(records),
                suggestions=len(records)*3,rules=len(records)*8,reference_count_per_patient=4,
                real_sensor_observations_used=False,clinical_targets_used=False,geometry_correction_applied=False,
                checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),seconds=time.time()-start,records=records)
    (ROOT/'checks/PATIENT_PATH_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
