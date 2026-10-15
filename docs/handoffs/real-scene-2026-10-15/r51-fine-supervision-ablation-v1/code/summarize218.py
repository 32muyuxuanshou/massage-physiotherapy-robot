"""Every selection, seed, identity and failure retained; no post-hoc winner rule."""
from collections import defaultdict
import csv,json
from pathlib import Path
import numpy as np
from core import WORK,OLD,G,CFG,sha


def hierarchical(rows,field):
    per={}
    for identity in sorted({r['identity'] for r in rows}):
        rr=[r for r in rows if r['identity']==identity];seq={}
        for sequence in sorted({r['sequence'] for r in rr}):seq[sequence]=float(np.mean([r[field] for r in rr if r['sequence']==sequence]))
        per[identity]=dict(mean=float(np.mean(list(seq.values()))),sequences=seq)
    return dict(equal_mean=float(np.mean([r['mean'] for r in per.values()])),per_identity=per)


def native_and_scan():
    result=[];base={s:json.loads((WORK/('BASELINE_s%d.json'%s)).read_text()) for s in CFG['seeds']}
    for seed in CFG['seeds']:
        result.append(dict(arm='Parent',seed=seed,selection='parent',epoch=0,domains={d:base[seed][d] for d in ['native','scan']}))
        for arm in CFG['arms']:
            root=WORK/'runs'/('%s_s%d'%(arm,seed));r=json.loads((root/'RESULTS.json').read_text())
            for selection,epoch in [('old_best',r['old_best_epoch']),('joint_best',r['joint_best_epoch']),('last',r['last_epoch'])]:
                values=base[seed] if epoch==0 else json.loads((root/('VAL_%02d.json'%epoch)).read_text())
                result.append(dict(arm=arm,seed=seed,selection=selection,epoch=epoch,domains={d:values[d] for d in ['native','scan']}))
    return result


def real_cells():
    index=json.loads((WORK/'REAL_EVALUATION_INDEX.json').read_text());job_results={}
    for job in index['jobs']:
        files=sorted((WORK/'real_evaluation'/job['name']/'metrics').glob('*.json'))
        assert len(files)==502
        records=[json.loads(p.read_text()) for p in files];groups=[]
        for dataset in ['real','behave']:
            for role in sorted({r['role'] for r in records if r['dataset']==dataset}):
                rr=[r for r in records if r['dataset']==dataset and r['role']==role]
                flat=[dict(r,**r['metrics']) for r in rr]
                values={k:hierarchical(flat,k) for k in ['median_mm','p95_mm','coverage_50mm']}
                if dataset=='behave':values['pve_mm']=hierarchical(flat,'pve_mm')
                groups.append(dict(dataset=dataset,role=role,frames=len(rr),metrics=values))
        job_results[job['name']]=dict(job=job,records=records,groups=groups)
    cells=[]
    for link in index['links']:cells.append(dict(link,**job_results[link['job']]))
    for seed in CFG['seeds']:
        name='parent_s%d_e00'%seed;cells.append(dict(arm='Parent',seed=seed,selection='parent',epoch=0,**job_results[name]))
    return cells,job_results


def transition(old,new,coarse):
    was=old>coarse;now=new>coarse
    return dict(old_worse=was,new_worse=now,rescued=was and not now,newly_worse=not was and now)


def main():
    assert json.loads((WORK/'REAL_EVALUATION_COMPLETE.json').read_text())['status']=='COMPLETE'
    synthetic=native_and_scan();real,jobs=real_cells()
    original=json.loads((OLD/'previous/reports/Q1_RECORDS.json').read_text())
    old={(r['dataset'],r['seed'],r['key']):r for r in original}
    transfers=[];paired=[]
    for cell in synthetic:
        for r in cell['domains']['native']['records']:
            ref=old['native',cell['seed'],r['key']]
            item=dict(arm=cell['arm'],selection=cell['selection'],seed=cell['seed'],epoch=cell['epoch'],dataset='native',role='VAL',key=r['key'],identity=r['identity'])
            item.update(transition(ref['stages']['final']['camera_mm'],r['camera_mm'],ref['stages']['coarse']['camera_mm']))
            item.update(metric='camera_mm',new=r['camera_mm'],old=ref['stages']['final']['camera_mm'],coarse=ref['stages']['coarse']['camera_mm'])
            transfers.append(item)
    for cell in real:
        for r in cell['records']:
            ref=old[r['dataset'],cell['seed'],r['key']]
            metrics=['median_mm'] if r['dataset']=='real' else ['pve_mm','surface_median_mm']
            for name in metrics:
                old_key='median_mm' if name=='median_mm' else name
                new=r['pve_mm'] if name=='pve_mm' else r['metrics']['median_mm']
                item={k:cell[k] for k in ['arm','selection','seed','epoch']}
                item.update({k:r[k] for k in ['dataset','key','identity','role']})
                item.update(metric=name,old=ref['stages']['final'][old_key],coarse=ref['stages']['coarse'][old_key],new=new)
                item.update(transition(item['old'],new,item['coarse']));transfers.append(item)
                paired.append(dict(item,versus_parent_mm=new-item['old'],P95=r['metrics']['p95_mm'],camera_m=r['camera_m'],fine_delta_m=r['fine_delta_m']))
    transfer_groups=[]
    keys=sorted({tuple(r[k] for k in ['arm','selection','seed','dataset','role','metric']) for r in transfers})
    for key in keys:
        rr=[r for r in transfers if tuple(r[k] for k in ['arm','selection','seed','dataset','role','metric'])==key]
        transfer_groups.append(dict(zip(['arm','selection','seed','dataset','role','metric'],key),frames=len(rr),**{k:sum(r[k] for r in rr) for k in ['old_worse','new_worse','rescued','newly_worse']}))
    gradients=[];training=[]
    for seed in CFG['seeds']:
        initial=[];orders=[]
        for arm in CFG['arms']:
            p=WORK/'runs'/('%s_s%d'%(arm,seed));r=json.loads((p/'RESULTS.json').read_text());curves=json.loads((p/'CURVES.json').read_text())
            training.append(dict(arm=arm,seed=seed,result=r,curves=curves));initial.append(r['initial_fine_sha256']);orders.append([c['data_order_sha256'] for c in curves])
            gradients.extend([dict(arm=arm,seed=seed,**g) for g in json.loads((p/'GRADIENT_LEDGER.json').read_text())])
        assert len(set(initial))==1 and all(v==orders[0] for v in orders)
    # Frozen strong baseline from identical historical cohorts, not a new fit.
    baselines=[]
    for dataset in ['real','behave']:
        for seed in CFG['seeds']:
            rr=[r for r in original if r['dataset']==dataset and r['seed']==seed]
            for role in sorted({r['role'] for r in rr}):
                group=[dict(r,**r['official_txyz']) for r in rr if r['role']==role]
                names=['median_mm','p95_mm','coverage_50mm'] if dataset=='real' else ['pve_mm','surface_median_mm','surface_p95_mm','surface_coverage_50mm']
                baselines.append(dict(dataset=dataset,seed=seed,role=role,metrics={k:hierarchical(group,k) for k in names}))
    out=WORK/'reports';out.mkdir(exist_ok=True)
    synthetic_compact=[dict(c,domains={d:dict(aggregate=v['aggregate']) for d,v in c['domains'].items()}) for c in synthetic]
    real_compact=[{k:v for k,v in c.items() if k!='records'} for c in real]
    for name,value in [('SYNTHETIC_RESULTS.json',synthetic_compact),('REAL_RESULTS.json',real_compact),('REAL_JOBS.json',jobs),('CLASSIFICATION_TRANSFERS.json',dict(groups=transfer_groups)),('GRADIENT_LEDGER_ALL.json',gradients),('TRAINING_ALL.json',training),('OFFICIAL_TXYZ_REFERENCE.json',baselines)]:
        (out/name).write_text(json.dumps(value,indent=2))
    def write_csv(name,records):
        fields=list(dict.fromkeys(k for r in records for k in r))
        with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            writer.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in records)
    write_csv('CLASSIFICATION_TRANSFERS.csv',transfers);write_csv('PAIRED_REAL_FRAMES.csv',paired)
    for domain in ['native','scan']:
        records=[dict(arm=c['arm'],seed=c['seed'],selection=c['selection'],epoch=c['epoch'],**r) for c in synthetic for r in c['domains'][domain]['records']]
        write_csv(domain.upper()+'_FRAME_RESULTS.csv',records)
    status=dict(status='COMPLETE',training_units=12,training_images_per_epoch=1280,epochs=6,unique_real_prediction_jobs=len(jobs),real_records=sum(len(j['records']) for j in jobs.values()),matching_initialization_and_orders=True,selection_freeze_sha256=sha(WORK/'SELECTION_FREEZE.json'),camera_B_fit=False,TEST_read=False,new_model_Txyz=False)
    (out/'SUMMARY_STATUS.json').write_text(json.dumps(status,indent=2));print(json.dumps(status),flush=True)


if __name__=='__main__':main()
