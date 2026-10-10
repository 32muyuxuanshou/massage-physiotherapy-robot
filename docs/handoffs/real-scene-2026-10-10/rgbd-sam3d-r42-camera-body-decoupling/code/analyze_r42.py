"""All-frame/identity/region reporting for R4.2; no selection or fitting."""
import argparse
import csv
import json
from pathlib import Path
from run_r41_txyz import dependencies, np, METRICS, REGIONS


def main(a):
    w=a.work;j=json.loads((w/'ALL_RESULTS.json').read_text());rows=j['records'];results=j['results']
    f=dependencies(a.source/'code');official={r['key']:r for r in rows if r['cell']=='official'}
    frame_rows=[];identities=[];regions={};signs={};init_effect={};subgroups={}
    for cell in results:
        rr=[r for r in rows if r['cell']==cell];signs[cell]={};regions[cell]={};subgroups[cell]={}
        for stage in ['before','after']:
            regions[cell][stage]={}
            for role in ['TRAIN','VAL']:
                subset=[r for r in rr if r['role']==role];regional_results={}
                for region in REGIONS:
                    rrows=[dict(identity=r['identity'],sequence=r['sequence'],frame=r['frame'],triangle=r['regions_'+stage][region])
                           for r in subset if region in r['regions_'+stage]]
                    if rrows:regional_results[region]=dict(metrics=f['aggregate_real'](rrows)['identity_equal_mean'],
                                                          frames=len(rrows),points=sum(x['triangle']['point_count'] for x in rrows))
                regions[cell][stage][role]=regional_results
        for role in ['TRAIN','VAL']:
            subset=[r for r in rr if r['role']==role]
            paired=[]
            for identity,m in results[cell]['after'][role]['per_identity'].items():
                ref=results['official']['after'][role]['per_identity'][identity]['metrics']
                r=dict(cell=cell,role=role,identity=identity,raw=results[cell]['before'][role]['per_identity'][identity]['metrics'],
                       corrected=m['metrics'],official_txyz=ref,delta={k:m['metrics'][k]-ref[k] for k in METRICS})
                identities.append(r);paired.append(r)
            signs[cell][role]=dict(identities=len(paired),identity_median_better=sum(r['delta']['median_mm']<0 for r in paired),
                identity_p95_better=sum(r['delta']['p95_mm']<0 for r in paired),
                frames_p95_worse=sum(r['triangle_after']['p95_mm']>official[r['key']]['triangle_after']['p95_mm'] for r in subset),
                frames_p95_worse_over5mm=sum(r['triangle_after']['p95_mm']>official[r['key']]['triangle_after']['p95_mm']+5 for r in subset))
            subgroups[cell][role]={}
            for flag in [False,True]:
                ss=[r for r in subset if official[r['key']]['fallback']==flag]
                subgroups[cell][role]['official_fallback' if flag else 'official_applied']=dict(frames=len(ss),
                    identities=sorted({r['identity'] for r in ss}),fallback_count=sum(r['fallback'] for r in ss),
                    diagnostic_frame_mean_delta_mm={k:float(np.mean([r['triangle_after'][k]-official[r['key']]['triangle_after'][k] for r in ss])) for k in METRICS} if ss else {})
        for r in rr:
            ref=official[r['key']]
            frame_rows.append(dict(cell=cell,role=r['role'],identity=r['identity'],key=r['key'],frame=r['frame'],sequence=r['sequence'],
                raw=r['triangle_before'],corrected=r['triangle_after'],delta_from_official_txyz={k:r['triangle_after'][k]-ref['triangle_after'][k] for k in METRICS},
                fallback=r['fallback'],official_fallback=ref['fallback'],raw_translation_m=r['raw_translation_m'],applied_translation_m=r['applied_translation_m']))
        if cell.startswith('official_body_g1_camera') or cell in ['camera_only','metric_base_no_learned_offset']:
            init_effect[cell]={}
            for role in ['TRAIN','VAL']:
                ss=[r for r in rr if r['role']==role];data=[]
                for r in ss:
                    key=r['key'];new=np.load(w/'corrected'/cell/(key+'.npz'));old=np.load(a.source/'corrected/official'/(key+'.npz'))
                    delta=(new['pred_cam_t']-old['pred_cam_t']).reshape(3)
                    assert np.max(np.abs((new['vertices_camera_A']-old['vertices_camera_A'])-delta))<1e-6
                    data.append(dict(key=key,final_camera_difference_xyz_mm=(delta*1000).tolist(),norm_mm=float(np.linalg.norm(delta)*1000),
                                     last_step_norm_mm=float(np.linalg.norm(r['trace'][-1]['step_m'])*1000),
                                     p95_delta_mm=r['triangle_after']['p95_mm']-official[key]['triangle_after']['p95_mm']))
                init_effect[cell][role]=dict(frame_median_final_camera_difference_mm=float(np.median([d['norm_mm'] for d in data])),
                    frame_p95_final_camera_difference_mm=float(np.quantile([d['norm_mm'] for d in data],.95)),
                    max_body_preservation_roundoff_m=max(r['body_relative_vertex_roundoff_max_m'] for r in ss),records=data,
                    explanation='Body is identical to Official; differences between these final meshes and Official+Txyz are only translation plus float32 roundoff. Different initialization of finite nearest-anchor Txyz can yield different final Camera.')
    multiseed={m:{role:{stage:{k:dict(mean=float(np.mean([results[f'{m}_seed{s}'][stage][role]['identity_equal_mean'][k] for s in [11,23,37]])),
                                          sample_sd=float(np.std([results[f'{m}_seed{s}'][stage][role]['identity_equal_mean'][k] for s in [11,23,37]],ddof=1))) for k in METRICS}
                           for stage in ['before','after']} for role in ['TRAIN','VAL']}
               for m in ['g1','official_body_g1_camera','g1_body_official_camera']}
    probes={}
    for cell in ['camera_only','metric_base_no_learned_offset']:
        rr=[r for r in rows if r['cell']==cell]
        probes[cell]=dict(max_xyz_translation_error_mm=max(r['depth_response']['xyz_translation_200mm']['max_error_mm'] for r in rr),
             body_arrays_exact=all(r['body_parameter_arrays_exact'] for r in rr),missing_depth_exact=all(r['missing_depth_camera_exact'] for r in rr),
             depth_offsets={str(offset):{role:dict(frame_median_camera_delta_xyz_mm=np.median([r['depth_response'][f'depth_offset_{offset}_fixed_RGB']['camera_delta_mm'] for r in rr if r['role']==role],axis=0).tolist())
                          for role in ['TRAIN','VAL']} for offset in [-.2,.2]},
             interpretation='Point translation equivariance and numerical fixed-RGB depth sensitivity, not physical camera GT or clinical accuracy.')
    report=dict(status='COMPLETE',total_frame_method_pairs=len(rows),frame_method_stage_evaluations=len(rows)*2,
        multi_seed=multiseed,signs=signs,regions=regions,fallback_subgroups=subgroups,camera_initialization_effect=init_effect,depth_probes=probes,
        original_fallback_cases=[r['key'] for r in rows if r['cell']=='official' and r['fallback']],
        failures=[r for r in frame_rows if r['cell']!='official' and r['delta_from_official_txyz']['p95_mm']>0])
    (w/'ANALYSIS.json').write_text(json.dumps(report,indent=2))
    (w/'PAIRED_FRAMES.json').write_text(json.dumps(frame_rows,indent=2))
    (w/'PER_IDENTITY.json').write_text(json.dumps(identities,indent=2))
    for name,data in [('PER_IDENTITY.csv',identities),('PER_FRAME.csv',frame_rows)]:
        with (w/name).open('w',newline='',encoding='utf-8') as file:
            fields=['cell','role','identity']+(['key'] if name=='PER_FRAME.csv' else [])
            fields+=['raw_median_mm','raw_p95_mm','median_mm','p95_mm','coverage_50mm','delta_median_mm','delta_p95_mm']
            writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader()
            for r in data:
                delta=r['delta'] if name=='PER_IDENTITY.csv' else r['delta_from_official_txyz']
                line={k:r[k] for k in fields if k in r}
                line.update(raw_median_mm=r['raw']['median_mm'],raw_p95_mm=r['raw']['p95_mm'],median_mm=r['corrected']['median_mm'],
                            p95_mm=r['corrected']['p95_mm'],coverage_50mm=r['corrected']['coverage_50mm'],delta_median_mm=delta['median_mm'],delta_p95_mm=delta['p95_mm'])
                writer.writerow(line)
    lines=['# 所有逐身份结果','', '距离 Δ = 当前＋Txyz − Official＋Txyz；负值改善。原始列不含Txyz。','',
           '|Method|Role|Identity|Raw med/P95|+Txyz med/P95|Δ med/P95|','|---|---|---|---:|---:|---:|']
    for r in identities:
        b,c,d=r['raw'],r['corrected'],r['delta'];lines.append(f"|{r['cell']}|{r['role']}|{r['identity']}|{b['median_mm']:.2f}/{b['p95_mm']:.2f}|{c['median_mm']:.2f}/{c['p95_mm']:.2f}|{d['median_mm']:.2f}/{d['p95_mm']:.2f}|")
    (w/'PER_IDENTITY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('ANALYSIS_COMPLETE',len(rows),len(identities),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True);main(p.parse_args())
