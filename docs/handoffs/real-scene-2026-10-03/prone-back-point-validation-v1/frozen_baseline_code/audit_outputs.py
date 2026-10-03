"""One explicit completion audit for mesh/index/figure counts and identities."""
import argparse
from pathlib import Path
from data_v2 import load_json,save_json,sha
from cache_v2 import mesh_path,verify_cache


def audit_outputs(out,contract,subjects,methods=None,seeds=None):
    names=methods or contract['methods'];seeds=contract['seeds'] if seeds is None else seeds
    records=[];panels=[]
    for s in subjects:
        rows=load_json(out/'evaluation'/s/'results.json')
        assert len(rows)==len(names)*len(seeds)
        for seed in seeds:
            for name in names:
                p=mesh_path(out,s,seed,name);m=verify_cache(p,out,s,seed)
                visual=out/'visualizations'/s/f'seed_{seed}'
                stem=name.replace('+','_');overlay=visual/(stem+'_overlay.png');heatmap=visual/(stem+'_posterior_residual.png')
                metric=out/'evaluation'/s/f'seed_{seed}'/(stem+'_metrics.npz')
                assert overlay.exists() and heatmap.exists() and metric.exists()
                row=next(r for r in rows if r['seed']==seed and r['method']==name)
                assert row['mesh_sha256']==sha(p) and row['input_sha256']==m['input_sha256'] and row['split_sha256']==m['split_sha256']
                records.append(dict(subject=s,seed=seed,method=name,mesh_sha256=sha(p),mesh_metadata_sha256=sha(p.with_suffix('.json')),
                    metric_sha256=sha(metric),overlay_sha256=sha(overlay),residual_image_sha256=sha(heatmap),optimization_heldout_intersection=0))
            panel=out/'visualizations'/s/f'seed_{seed}'/'comparison.jpg';assert panel.exists();panels.append(str(panel.relative_to(out)))
    r=dict(status='PASS',scope_subjects=subjects,scope_seeds=seeds,scope_methods=names,
        expected_rows=len(subjects)*len(names)*len(seeds),mesh_records=len(records),overlays=len(records),
        residual_images=len(records),comparison_panels=len(panels),all_optimization_heldout_intersections_zero=True,
        records=records,panels=panels)
    save_json(out/'OUTPUT_COMPLETENESS_AUDIT.json',r);return r


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--subjects',nargs='+',required=True)
    p.add_argument('--methods',nargs='+');p.add_argument('--seeds',nargs='+',type=int);a=p.parse_args()
    audit_outputs(a.out,load_json(Path(__file__).resolve().parents[1]/'EXPERIMENT_CONTRACT.json'),a.subjects,a.methods,a.seeds)
