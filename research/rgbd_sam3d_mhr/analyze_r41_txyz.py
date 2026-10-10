"""Complete paired reporting; no re-selection, alignment, fitting, or training."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from run_r41_txyz import dependencies, METRICS, REGIONS


def mean_sd(values):
    return dict(mean=float(np.mean(values)),sample_sd=float(np.std(values,ddof=1)),values=values)


def native_equal_mean(rows,key):
    return np.mean([np.mean([np.mean([r['native_changes_from_official'][key] for r in rows
        if r['identity']==identity and r['sequence']==sequence],axis=0)
        for sequence in sorted({r['sequence'] for r in rows if r['identity']==identity})],axis=0)
        for identity in sorted({r['identity'] for r in rows})],axis=0).tolist()


def main(work):
    j=json.loads((work/'PAIRED_RESULTS.json').read_text());rows=j['records'];results=j['results'];f=dependencies(work/'code')
    official={r['key']:r for r in rows if r['cell']=='official'}
    frame_pairs=[];identities=[];regions={};response={};subgroups={}
    for cell in sorted(results):
        rr=[r for r in rows if r['cell']==cell]
        for role in ['TRAIN','VAL']:
            for identity,m in results[cell]['after'][role]['per_identity'].items():
                ref=results['official']['after'][role]['per_identity'][identity]['metrics']
                identities.append(dict(cell=cell,role=role,identity=identity,
                    raw=results[cell]['before'][role]['per_identity'][identity]['metrics'],corrected=m['metrics'],official_txyz=ref,
                    delta_from_official_txyz={k:m['metrics'][k]-ref[k] for k in METRICS},
                    fallback_count=sum(r['fallback'] for r in rr if r['identity']==identity),frames=sum(r['identity']==identity for r in rr)))
            subset=[r for r in rr if r['role']==role]
            response.setdefault(cell,{})[role]={k:dict(identity_equal_mean=native_equal_mean(subset,k),
                frame_distribution_median=np.median([r['native_changes_from_official'][k] for r in subset],axis=0).tolist())
                for k in subset[0]['native_changes_from_official'] if k!='camera_delta_xyz_mm'}
            response[cell][role]['camera_delta_xyz_mm']=dict(identity_equal_mean=native_equal_mean(subset,'camera_delta_xyz_mm'),
                frame_distribution_median=np.median([r['native_changes_from_official']['camera_delta_xyz_mm'] for r in subset],axis=0).tolist())
            subgroups.setdefault(cell,{})[role]={}
            for flag in [False,True]:
                ss=[r for r in subset if official[r['key']]['fallback']==flag]
                subgroups[cell][role]['official_fallback' if flag else 'official_applied']=dict(frames=len(ss),
                    frame_paired_mean_delta_mm={k:float(np.mean([r['triangle_after'][k]-official[r['key']]['triangle_after'][k] for r in ss])) for k in METRICS} if ss else {},
                    description='Diagnostic frame means stratified by pre-existing Official fallback; all retained in primary result.')
        for r in rr:
            ref=official[r['key']]
            frame_pairs.append(dict(cell=cell,role=r['role'],identity=r['identity'],sequence=r['sequence'],frame=r['frame'],key=r['key'],
                metrics=r['triangle_after'],official_txyz=ref['triangle_after'],
                delta={k:r['triangle_after'][k]-ref['triangle_after'][k] for k in METRICS},
                txyz_change={k:r['triangle_after'][k]-r['triangle_before'][k] for k in METRICS},
                fallback=r['fallback'],official_fallback=ref['fallback'],raw_norm_mm=r['raw_norm_mm'],applied_norm_mm=r['applied_norm_mm']))
        regions[cell]={}
        for stage in ['before','after']:
            regions[cell][stage]={}
            for role in ['TRAIN','VAL']:
                regions[cell][stage][role]={}
                for region in REGIONS:
                    data=[dict(identity=r['identity'],sequence=r['sequence'],frame=r['frame'],triangle=r['regions_'+stage][region])
                          for r in rr if r['role']==role and region in r['regions_'+stage]]
                    if data:regions[cell][stage][role][region]=dict(summary=f['aggregate_real'](data)['identity_equal_mean'],
                        frames=len(data),identities=len({x['identity'] for x in data}),observed_points=sum(x['triangle']['point_count'] for x in data))
    seed_summary={}
    for mode in ['g0','g1']:
        seed_summary[mode]={role:{stage:{k:mean_sd([results[f'{mode}_seed{s}'][stage][role]['identity_equal_mean'][k] for s in [11,23,37]]) for k in METRICS}
            for stage in ['before','after']} for role in ['TRAIN','VAL']}
    signs={}
    for cell in sorted(results):
        signs[cell]={role:dict(identities=sum(x['cell']==cell and x['role']==role for x in identities),
            identities_median_improved=sum(x['delta_from_official_txyz']['median_mm']<0 for x in identities if x['cell']==cell and x['role']==role),
            identities_p95_improved=sum(x['delta_from_official_txyz']['p95_mm']<0 for x in identities if x['cell']==cell and x['role']==role),
            frames_median_improved=sum(x['delta']['median_mm']<0 for x in frame_pairs if x['cell']==cell and x['role']==role),
            frames_p95_worsened=sum(x['delta']['p95_mm']>0 for x in frame_pairs if x['cell']==cell and x['role']==role),
            frames_p95_worsened_over5mm=sum(x['delta']['p95_mm']>5 for x in frame_pairs if x['cell']==cell and x['role']==role),
            identities_median_better_p95_worse=[x['identity'] for x in identities if x['cell']==cell and x['role']==role and x['delta_from_official_txyz']['median_mm']<0 and x['delta_from_official_txyz']['p95_mm']>0])
            for role in ['TRAIN','VAL']}
    report=dict(seed_summary=seed_summary,paired_identities=identities,frame_signs=signs,regions=regions,
        native_response=response,fallback_stratification=subgroups,
        limitations=['Native parameter differences are not Pose/Shape errors; real corresponding MHR truth unavailable.',
            'Regional assignment is a fixed engineering proxy from historical reference nearest triangles; not anatomical truth.',
            'Subgroups and extra mechanical exchanges are diagnostic, never substitute the full 232-frame primary comparison.'])
    (work/'ANALYSIS.json').write_text(json.dumps(report,indent=2))
    (work/'PAIRED_FRAMES.json').write_text(json.dumps(frame_pairs,indent=2))
    (work/'P95_WORSENING_CASES.json').write_text(json.dumps([r for r in frame_pairs if r['cell']!='official' and r['delta']['p95_mm']>0],indent=2))
    for name,data in [('PER_FRAME.csv',frame_pairs),('PER_IDENTITY.csv',identities)]:
        with (work/name).open('w',newline='',encoding='utf-8-sig') as file:
            writer=csv.writer(file)
            if name=='PER_FRAME.csv':
                writer.writerow(['cell','role','identity','sequence','frame','median_mm','p95_mm','coverage_50mm','delta_median_mm','delta_p95_mm','delta_coverage','fallback','official_fallback','raw_norm_mm','applied_norm_mm'])
                for r in data:writer.writerow([r[k] for k in ['cell','role','identity','sequence','frame']]+[r['metrics'][k] for k in METRICS]+[r['delta'][k] for k in METRICS]+[r[k] for k in ['fallback','official_fallback','raw_norm_mm','applied_norm_mm']])
            else:
                writer.writerow(['cell','role','identity','raw_median_mm','raw_p95_mm','median_mm','p95_mm','coverage_50mm','delta_median_mm','delta_p95_mm','delta_coverage','fallback_count','frames'])
                for r in data:writer.writerow([r[k] for k in ['cell','role','identity']]+[r['raw'][k] for k in METRICS[:2]]+[r['corrected'][k] for k in METRICS]+[r['delta_from_official_txyz'][k] for k in METRICS]+[r[k] for k in ['fallback_count','frames']])
    lines=['# 全部逐身份结果','', 'Δ = corrected model − Official+Txyz；距离负值为改善。所有身份和帧保留。','',
        '|Model/seed|Role|Identity|Raw med/P95|+Txyz med/P95|Official+Txyz med/P95|Δ med/P95|Fallback|', '|---|---|---|---:|---:|---:|---:|---:|']
    for r in identities:
        m,b,d=r['corrected'],r['official_txyz'],r['delta_from_official_txyz'];raw=r['raw']
        lines.append(f"|{r['cell']}|{r['role']}|{r['identity']}|{raw['median_mm']:.2f}/{raw['p95_mm']:.2f}|{m['median_mm']:.2f}/{m['p95_mm']:.2f}|{b['median_mm']:.2f}/{b['p95_mm']:.2f}|{d['median_mm']:.2f}/{d['p95_mm']:.2f}|{r['fallback_count']}/{r['frames']}|")
    (work/'PER_IDENTITY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('ANALYSIS_COMPLETE',json.dumps(seed_summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work)
