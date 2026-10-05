"""Evaluate and replay all four TRAIN fixture packs through the formal evaluator."""
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from anchored_field import AnchoredField
from evaluate_source import fit_prior,evaluate_case

ROOT=Path(__file__).resolve().parents[1]


def replay(cache,metrics):
    with np.load(cache) as a:
        used=a['scored_level_mask'];xyz=np.linalg.norm(a['predicted_level_xyz_mm']-a['target_level_xyz_mm'],axis=1)
        xz=np.linalg.norm((a['predicted_level_xyz_mm']-a['target_level_xyz_mm'])[:,[0,2]],axis=1)
        prior=np.linalg.norm(a['prior_level_xyz_mm']-a['target_level_xyz_mm'],axis=1)
        ray=abs(a['predicted_ray_delta']-a['ray_target'])*500.
        assert len(np.intersect1d(a['observed_indices'],a['query_indices']))==0
        got=[float(xyz[used].mean()),float(xz[used].mean()),float(prior[used].mean()),float(np.median(ray)),float(np.quantile(ray,.95))]
    expected=[metrics[k] for k in ['case_mean_xyz_mm','case_mean_xz_mm','prior_case_mean_xyz_mm','ray_median_mm','ray_p95_mm']]
    difference=float(np.max(abs(np.array(got)-expected)));assert difference<1e-5
    return difference


def main():
    torch.set_num_threads(4)
    source=ROOT.parent/'anatomical-surface-method-foundation-v1/structure_check'
    rows=json.loads((source/'CASE_MANIFEST.json').read_text())
    for row in rows:row['pack']=str(source/row['case']/'field_pack.npz')
    prior=fit_prior(rows)
    checkpoint=Path(__file__).resolve().parents[5]/'output/reference_anchored_surface_field_v2/STRUCTURE_ONLY_HARD_JOINT.pt'
    model=AnchoredField();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True));model.eval()
    checks=[];output=ROOT/'checks/source_eval';output.mkdir(exist_ok=True)
    for row in rows:
        metrics,arrays,frame=evaluate_case(row,model,'HARD_JOINT',prior,int(row['ct_sha256'][:8],16),0.,'cpu')
        cache=output/(row['case']+'.npz');np.savez_compressed(cache,**arrays)
        checks.append(dict(case=row['case'],metrics=metrics,replay_max_difference=replay(cache,metrics),
                           cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),frame=frame))
    report=dict(status='FOUR_TRAIN_FORMAL_EVALUATOR_PATH_AND_CACHE_REPLAY_PASS',test_images_used=0,
                clinical_accuracy_test=False,prior=prior,records=checks)
    (ROOT/'checks/SOURCE_EVAL_PATH_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['prior','records']}))


if __name__=='__main__':main()
