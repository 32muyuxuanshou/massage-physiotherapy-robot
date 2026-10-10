"""Recompute delivery tables from saved per-seed results, without fitting."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):return json.loads(path.read_text())
def save(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf8')
def stats(values):return dict(mean=float(np.mean(values)),std=float(np.std(values,ddof=1)))


def main(root):
    out=root/'summary';out.mkdir(exist_ok=True)
    native=[]
    for stage,dirname in [('native','native_results'),('continuation','continuation_results')]:
        for path in sorted((root/dirname).glob('*/RESULTS.json')):
            d=read(path);assert d['status']=='COMPLETE'
            mode,seed=path.parent.name.rsplit('_s',1)
            native.append(dict(stage=stage,mode=mode,seed=int(seed),epochs=d['epochs_completed'],
                best=d['best']['identity_equal_mean'],best_checkpoint_camera_mm=d['best_camera_score_mm'],
                epoch_seconds=sum(r['seconds'] for r in read(path.parent/'CURVES.json'))))
    assert len(native)==15
    save(out/'NATIVE_PER_SEED.json',native)
    official=read(root/'real_evaluation/official.json')
    gate=read(root/'real_evaluation/OFFICIAL_REPRODUCTION_GATE.json');assert gate['status']=='PASS' and gate['frames']==232
    raw={p.stem:read(p) for p in (root/'real_evaluation').glob('repaired__*.json')}
    assert len(raw)==15 and all(len(d['records'])==232 and not d['TEST_read'] and not d['camera_B_fit'] for d in raw.values())
    baseline={r['key']:r for r in official['records']}
    cells=[];pairs=[];identities=[];failure=[]
    for cell,d in sorted(raw.items()):
        _,stage,name=cell.split('__');mode,seed=name.rsplit('_s',1)
        row=dict(cell=cell,stage=stage,mode=mode,seed=int(seed),fallback_232=d['fallback'],
            metrics={k:v['identity_equal_mean'] for k,v in d['aggregated'].items()})
        cells.append(row)
        for role in ['TRAIN','VAL']:
            for identity,x in d['aggregated'][role+'_after']['per_identity'].items():
                ref=official['aggregated'][role+'_after']['per_identity'][identity]['metrics']
                identities.append(dict(cell=cell,identity=identity,role=role,metrics=x['metrics'],
                    delta_vs_official_txyz={k:x['metrics'][k]-ref[k] for k in ref}))
        for r in d['records']:
            ref=baseline[r['key']]
            p=dict(cell=cell,key=r['key'],identity=r['identity'],role=r['role'],
                before=r['triangle_before'],after=r['triangle_after'],official_txyz=ref['triangle_after'],
                delta_vs_official_txyz={k:r['triangle_after'][k]-ref['triangle_after'][k] for k in ['median_mm','p95_mm','coverage_50mm']},
                fallback=r['fallback'],official_fallback=ref['fallback'],raw_translation_m=r['raw_translation_m'],
                applied_translation_m=r['applied_translation_m'],regions_before=r['regions_before'],regions_after=r['regions_after'])
            pairs.append(p)
            if ref['fallback']:failure.append(p)
    groups=[]
    for stage,mode in sorted({(r['stage'],r['mode']) for r in cells}):
        rr=[r for r in cells if r['stage']==stage and r['mode']==mode];assert len(rr)==3
        groups.append(dict(stage=stage,mode=mode,seeds=[r['seed'] for r in rr],
            metrics={key:{k:stats([r['metrics'][key][k] for r in rr]) for k in ['median_mm','p95_mm','coverage_50mm']} for key in ['TRAIN_before','TRAIN_after','VAL_before','VAL_after']},
            fallback_232=[r['fallback_232'] for r in rr]))
    save(out/'REAL_SUMMARY.json',dict(Official={k:v['identity_equal_mean'] for k,v in official['aggregated'].items()},
         Official_fallback_232=official['fallback'],cells=cells,groups=groups,
         aggregation='frame medians/P95/coverage -> sequence arithmetic means -> identity arithmetic means -> identity-equal arithmetic mean; std across 3 training seeds uses ddof=1'))
    save(out/'PAIRED_FRAMES.json',pairs);save(out/'PAIRED_IDENTITIES.json',identities)
    save(out/'OFFICIAL_FALLBACK_AUDIT.json',dict(unique_frames=sum(r['fallback'] for r in baseline.values()),records=failure))
    with (out/'REAL_PER_SEED.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.writer(f);writer.writerow(['cell','seed','role','stage','median_mm','p95_mm','coverage_50mm','fallback_total_232'])
        for row in cells:
            for role in ['TRAIN','VAL']:
                for s in ['before','after']:
                    m=row['metrics'][role+'_'+s];writer.writerow([row['cell'],row['seed'],role,s,m['median_mm'],m['p95_mm'],m['coverage_50mm'],row['fallback_232']])
    scans=[];ablations=[]
    for p in sorted((root/'diagnostics').glob('*_evaluate_scan.json')):
        d=read(p);assert len(d['records'])==768
        scans.append(dict(cell=p.stem.removesuffix('_evaluate_scan'),model=d['model']['identity_equal'],
                          Official=d['Official']['identity_equal'],per_identity=d['model']['per_identity']))
    for p in sorted((root/'diagnostics').glob('*_ablate_depth.json')):
        d=read(p)
        ablations.append(dict(cell=p.stem.removesuffix('_ablate_depth'),conditions={k:{x:y for x,y in v.items() if x!='records'} for k,v in d['conditions'].items()}))
    assert len(scans)==9 and len(ablations)==9
    save(out/'SCAN_SUMMARY.json',scans);save(out/'DEPTH_ABLATION_SUMMARY.json',ablations)
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    for ax,mode in zip(axes,['raw_bounded','metric_xyz','rgb_only_xyz']):
        for seed in [11,23,37]:
            curve=read(root/f'native_results/{mode}_s{seed}/CURVES.json')
            ax.plot([r['epoch'] for r in curve],[r['val']['camera_mean_mm'] for r in curve],label=f'seed {seed}')
        ax.set_title(mode);ax.set_xlabel('epoch');ax.set_ylabel('native VAL Camera L2 mm');ax.legend()
    fig.savefig(out/'NATIVE_TRAINING_CURVES.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for seed in [11,23,37]:
        for ax,mode in zip(axes,['native_only','mixed']):
            curve=read(root/f'continuation_results/{mode}_s{seed}/CURVES.json')
            ax.plot([r['epoch'] for r in curve],[r['val']['camera_mean_mm'] for r in curve],label=f'seed {seed}')
            ax.set_title(mode);ax.set_xlabel('additional epoch');ax.set_ylabel('native VAL Camera L2 mm');ax.legend()
    fig.savefig(out/'CONTINUATION_CURVES.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    selected=[r for r in groups if r['stage']=='continuation'];names=['Official+Txyz']+[r['mode']+'+Txyz' for r in selected]
    for ax,key in zip(axes,['median_mm','p95_mm']):
        values=[official['aggregated']['VAL_after']['identity_equal_mean'][key]]+[r['metrics']['VAL_after'][key]['mean'] for r in selected]
        deviations=[0]+[r['metrics']['VAL_after'][key]['std'] for r in selected]
        ax.bar(names,values,yerr=deviations,capsize=5,color=['#555555','#b47145','#247b9e']);ax.set_ylabel('mm');ax.set_title('Real VAL '+key+' | mean +/- seed sample SD')
    fig.savefig(out/'REAL_VAL_COMPARISON.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,8),layout='constrained')
    for ax,seed in zip(axes,[11,23,37]):
        rr=[r for r in identities if r['cell']==f'repaired__continuation__mixed_s{seed}']
        rr.sort(key=lambda r:r['identity'])
        values=[r['delta_vs_official_txyz']['p95_mm'] for r in rr]
        ax.barh([r['identity'] for r in rr],values,color=['#b33b31' if v>0 else '#247b9e' for v in values]);ax.axvline(0,color='black',lw=.7)
        ax.set_title(f'Mixed+Txyz seed{seed}');ax.set_xlabel('P95 delta vs Official+Txyz mm; right=worse')
    fig.savefig(out/'ALL_IDENTITY_P95.png',dpi=150);plt.close(fig)
    lines=['# 完整逐seed结果','', '真实指标为独立Camera B可见表面距离；下面的median/P95是既定层级等权汇总，不是所有点混在一起的分位数。','',
           '|组别|seed|native GT Camera mm|真实VAL raw median/P95 mm|真实VAL +Txyz median/P95 mm|fallback /232|','|---|---:|---:|---:|---:|---:|']
    for r in cells:
        n=next(v for v in native if (v['stage'],v['mode'],v['seed'])==(r['stage'],r['mode'],r['seed']))
        b=r['metrics']['VAL_before'];v=r['metrics']['VAL_after']
        lines.append(f"|{r['stage']}/{r['mode']}|{r['seed']}|{n['best']['camera_mm']:.3f}|{b['median_mm']:.3f}/{b['p95_mm']:.3f}|{v['median_mm']:.3f}/{v['p95_mm']:.3f}|{r['fallback_232']}|")
    lines += ['',f"Official +Txyz：VAL {official['aggregated']['VAL_after']['identity_equal_mean']}; fallback {official['fallback']}/232。确定性Official只计算一次，不把复制到3个seed表当3次独立推理。",'',
              '所有15个cell各232帧完整保留。逐帧配对见PAIRED_FRAMES.json；逐人见PAIRED_IDENTITIES.json；11个历史fallback逐模型见OFFICIAL_FALLBACK_AUDIT.json。']
    (out/'PER_SEED_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('SUMMARY_COMPLETE',len(cells),'cells',len(pairs),'paired frames',len(identities),'paired identities')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
