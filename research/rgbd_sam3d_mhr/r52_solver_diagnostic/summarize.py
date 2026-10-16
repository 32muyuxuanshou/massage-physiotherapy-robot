"""Cohort/seed separated paired contrasts, never selecting a model."""
from collections import defaultdict
import csv,json
import numpy as np
from common import W,CFG,dump


def hierarchical(rows,field):
    identities={}
    for identity in sorted({r['identity'] for r in rows}):
        rr=[r for r in rows if r['identity']==identity];seq={}
        for s in sorted({r['sequence'] for r in rr}):seq[s]=float(np.mean([r[field] for r in rr if r['sequence']==s]))
        identities[identity]=dict(mean=float(np.mean(list(seq.values()))),sequences=seq)
    return dict(equal_mean=float(np.mean([r['mean'] for r in identities.values()])),per_identity=identities,frame_equal_mean=float(np.mean([r[field] for r in rows])))


def main():
    assert json.loads((W/'EVALUATION_COMPLETE.json').read_text())['status']=='COMPLETE'
    frames=[];fit_rows=[];points=[]
    for p in sorted((W/'evaluation').glob('*.json')):
        result=json.loads(p.read_text());meta=result['task'];tag=p.stem
        fit=json.loads((W/'fits'/(tag+'.json')).read_text())
        for method,r in result['methods'].items():
            row=dict(meta,method=method,**r['metrics'])
            if 'pve_mm' in r:row['pve_mm']=r['pve_mm']
            camera=fit['methods'][method];row.update(raw_norm_mm=float(np.linalg.norm(camera['raw_delta_m'])*1000),applied_norm_mm=float(np.linalg.norm(camera['applied_delta_m'])*1000),fallback=camera['fallback'],camera_m=camera['camera_m'],delta_from_Official_m=camera['displacement_from_official_m'])
            frames.append(row)
            for region,v in r.get('regions',{}).items():fit_rows.append(dict(meta,method=method,region=region,**v))
        points.append(dict(tag=tag,official_reproduction=fit['official_reproduction']))
    assert len(frames)==2706*len(CFG['methods'])
    cells=[]
    for dataset,role,seed in sorted({(r['dataset'],r['role'],r['seed']) for r in frames}):
        for method in CFG['methods']:
            rr=[r for r in frames if r['dataset']==dataset and r['role']==role and r['seed']==seed and r['method']==method]
            fields=['vertex_camera_mm','vertex_p95_mm','camera_mm'] if dataset=='native' else ['median_mm','p95_mm','coverage_50mm']+(['pve_mm'] if dataset=='behave' else [])
            metrics={f:hierarchical(rr,f) for f in fields}
            cells.append(dict(dataset=dataset,role=role,seed=seed,method=method,frames=len(rr),metrics=metrics,fallback=sum(r['fallback'] for r in rr),raw_norm_median_mm=float(np.median([r['raw_norm_mm'] for r in rr])),applied_norm_median_mm=float(np.median([r['applied_norm_mm'] for r in rr]))))
    # Predefined one-factor contrasts, plus primary system comparisons.
    contrasts=[('PRIMARY_fine_to_dense6','fine','hist_med6'),('START_official_to_coarse','official_hist6','hist_med6'),
        ('STEPS_1_to_2','hist_med1','hist_med2'),('STEPS_2_to_3','hist_med2','hist_med3'),('STEPS_3_to_6','hist_med3','hist_med6'),
        ('COUNT_16384_to_256','hist_med6','all256_o2m_med6'),('VISIBILITY_all_to_visible','all256_o2m_med6','vis256_o2m_med6'),
        ('DIRECTION_o2m_to_m2o','vis256_o2m_med6','vis256_m2o_med6'),('OPERATOR_median_to_mean','hist_med6','hist_mean6'),
        ('OPERATOR_median_to_plane','hist_med6','hist_plane6'),('GATE_plane_to_filtered','hist_plane6','hist_plane_gate6'),
        ('RAY_ASSIGNMENT_query_to_pixel','proj_vis_med1','proj_lattice_vis_med1'),
        ('MATCH_projective_to_NN','proj_lattice_vis_med1','lattice_nn_vis_med1'),('LATTICE_median_to_mean','lattice_nn_vis_med1','lattice_nn_vis_mean1'),
        ('LATTICE_median_to_plane','lattice_nn_vis_med1','lattice_nn_vis_plane1')]
    pairs=[];indexed={(r['dataset'],r['role'],r['seed'],r['method']):r for r in cells}
    frame_index={(r['dataset'],r['seed'],r['key'],r['method']):r for r in frames}
    for name,before,after in contrasts:
        for c in [c for c in cells if c['method']==before]:
            d=indexed[c['dataset'],c['role'],c['seed'],after];metric='vertex_camera_mm' if c['dataset']=='native' else 'median_mm'
            rr=[r for r in frames if r['dataset']==c['dataset'] and r['role']==c['role'] and r['seed']==c['seed'] and r['method']==before]
            changes=[frame_index[r['dataset'],r['seed'],r['key'],after][metric]-r[metric] for r in rr]
            pairs.append(dict(contrast=name,before=before,after=after,dataset=c['dataset'],role=c['role'],seed=c['seed'],metric=metric,
                aggregate_delta_mm=d['metrics'][metric]['equal_mean']-c['metrics'][metric]['equal_mean'],improved_frames=sum(v<0 for v in changes),worsened_frames=sum(v>0 for v in changes),equal_frames=sum(v==0 for v in changes),frames=len(changes),
                p95_delta_mm=None if c['dataset']=='native' else d['metrics']['p95_mm']['equal_mean']-c['metrics']['p95_mm']['equal_mean']))
    transitions=[]
    for r in frames:
        if r['method'] in ['coarse','fine','official_hist6']:continue
        metric='vertex_camera_mm' if r['dataset']=='native' else 'median_mm';coarse=frame_index[r['dataset'],r['seed'],r['key'],'coarse'][metric];fine=frame_index[r['dataset'],r['seed'],r['key'],'fine'][metric]
        oldbad=fine>coarse;newbad=r[metric]>coarse
        transitions.append(dict(dataset=r['dataset'],role=r['role'],seed=r['seed'],method=r['method'],key=r['key'],identity=r['identity'],old_bad=oldbad,new_bad=newbad,rescued=oldbad and not newbad,newly_bad=not oldbad and newbad))
    out=W/'reports';out.mkdir(exist_ok=True)
    for name,v in [('RESULTS.json',cells),('PAIRED_CONTRASTS.json',pairs),('FRAME_RESULTS.json',frames),('REGION_RESULTS.json',fit_rows),('NEGATIVE_UPDATE_TRANSFERS.json',transitions)]:dump(out/name,v)
    for name,rr in [('ALL_FRAMES.csv',frames),('PAIRED_CONTRASTS.csv',pairs),('NEGATIVE_UPDATE_TRANSFERS.csv',transitions)]:
        fields=list(dict.fromkeys(k for r in rr for k in r))
        with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rr)
    # Retain exact original fallback membership and known identities.
    known=[]
    for r in frames:
        base=frame_index[r['dataset'],r['seed'],r['key'],'official_hist6']
        if r['dataset']=='real' and (base['fallback'] or r['identity'] in ['p001195','p001196']):known.append(r)
    dump(out/'KNOWN_FAILURES.json',known)
    print('SUMMARY_COMPLETE',len(cells),len(frames),flush=True)


if __name__=='__main__':main()
