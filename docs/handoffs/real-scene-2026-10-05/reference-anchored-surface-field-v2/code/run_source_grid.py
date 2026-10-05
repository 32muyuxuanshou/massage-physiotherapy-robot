"""Run frozen three-model, three-initialization source comparisons on GPU 0/1/2."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUTPUT=Path('/raid5/xuhd/datasets/reference_anchored_surface_field_v2_20261005')
MODELS=['SOFT_ANATOMY','HARD_ANATOMY','HARD_JOINT']


def aggregate():
    groups={}
    for mode in MODELS:
        for noise in [0,5]:
            by_case={}
            for seed in [0,1,2]:
                path=OUTPUT/(mode+'_seed'+str(seed))/('test_refnoise'+str(noise))/'RESULTS.json'
                data=json.loads(path.read_text())
                for row in data['results']:by_case.setdefault(row['case'],[]).append(row)
            import numpy as np
            cases=[]
            for case,rows in by_case.items():
                assert {r['seed'] for r in rows}=={0,1,2}
                cases.append(dict(case=case,case_mean_xyz_mm=float(np.median([r['case_mean_xyz_mm'] for r in rows])),
                                  case_mean_xz_mm=float(np.median([r['case_mean_xz_mm'] for r in rows])),
                                  prior_case_mean_xyz_mm=rows[0]['prior_case_mean_xyz_mm'],
                                  ray_median_mm=float(np.median([r['ray_median_mm'] for r in rows]))))
            assert cases, 'NO_QUALIFIED_TEST_IMAGES'
            groups[mode+'_REF'+str(noise)]=dict(cases=cases,images=len(cases),
                    image_equal_median_xyz_mm=float(np.median([r['case_mean_xyz_mm'] for r in cases])),
                    image_equal_mean_xyz_mm=float(np.mean([r['case_mean_xyz_mm'] for r in cases])),
                    image_equal_p95_xyz_mm=float(np.quantile([r['case_mean_xyz_mm'] for r in cases],.95)))
    # Both input conditions and all models must score the same qualified cases.
    assert len({tuple(sorted(r['case'] for r in g['cases'])) for g in groups.values()})==1
    result=dict(aggregation='valid non-reference levels -> mean per image -> median 3 seeds -> image-equal',
                evidence='paired CT-source proxy; not independent sensor or clinical accuracy',groups=groups)
    (OUTPUT/'AGGREGATED.json').write_text(json.dumps(result,indent=2)+'\n')


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for seed in [0,1,2]:
        jobs=[]
        for gpu,mode in enumerate(MODELS):
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu))
            log=open(OUTPUT/(mode+'_seed'+str(seed)+'.log'),'a')
            process=subprocess.Popen([sys.executable,str(ROOT/'train_source.py'),'--model',mode,'--seed',str(seed)],env=env,stdout=log,stderr=subprocess.STDOUT)
            jobs.append((process,log))
        for process,log in jobs:assert process.wait()==0;log.close()
        for gpu,mode in enumerate(MODELS):
            for noise in [0,5]:
                subprocess.run([sys.executable,str(ROOT/'evaluate_source.py'),'--model',mode,'--seed',str(seed),'--reference-noise-mm',str(noise)],
                               env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu)),check=True)
    aggregate()


if __name__=='__main__':main()
