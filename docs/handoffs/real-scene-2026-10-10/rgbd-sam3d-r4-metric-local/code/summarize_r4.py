"""Actual completed-cell tables and curves; retain per-seed/per-ID results."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def summarize(run,out):
    out.mkdir(parents=True,exist_ok=True);report=dict(pilots={},formal={},test_used=False);lines=[]
    for stage in ['pilots','formal']:
        for cell in sorted((run/stage).glob('*')):
            p=cell/'run/RESULTS.json'
            if not p.exists():continue
            x=json.loads(p.read_text());r=dict(mode=x['mode'],seed=x['seed'],epochs=x['epochs'],best_epoch=x['best_epoch'],
                best=x['best']['identity_equal_mean'],last=x['last']['identity_equal_mean'],trainable_parameters=x['trainable_parameters'],seconds=x['seconds'],peak_memory_bytes=x['peak_memory_bytes'])
            for key,path in [('real',cell/'real/HUMMAN_RESULTS.json'),('physical',cell/'physical.json')]:
                if path.exists():
                    z=json.loads(path.read_text());r[key]=({role:z['results'][role]['identity_equal_mean'] for role in ['TRAIN','VAL']} if key=='real' else z['identity_equal_mean'])
            report[stage][cell.name]=r
    stats={}
    for mode in sorted({x['mode'] for x in report['formal'].values()}):
        rr=[x for x in report['formal'].values() if x['mode']==mode];stats[mode]=dict(seeds=[x['seed'] for x in rr],synthetic={
            k:dict(mean=float(np.mean([x['best'][k] for x in rr])),sample_std=float(np.std([x['best'][k] for x in rr],ddof=1)) if len(rr)>1 else None) for k in rr[0]['best']})
        if all('real' in x for x in rr):stats[mode]['real']={role:{k:dict(mean=float(np.mean([x['real'][role][k] for x in rr])),sample_std=float(np.std([x['real'][role][k] for x in rr],ddof=1)) if len(rr)>1 else None) for k in rr[0]['real'][role]} for role in ['TRAIN','VAL']}
    report['multiseed']=stats;(out/'R4_SUMMARY.json').write_text(json.dumps(report,indent=2))
    for stage in ['pilots','formal']:
        lines+=['',f'## {stage}','', '| Cell | best epoch | camera-frame PVE | centered PVE | camera mm | real TRAIN med/P95 | real VAL med/P95 |','|---|---:|---:|---:|---:|---:|---:|']
        for name,x in report[stage].items():
            real=x.get('real',{});fmt=lambda role:('/'.join(f'{real[role][k]:.2f}' for k in ['median_mm','p95_mm']) if role in real else 'pending')
            lines.append(f"|{name}|{x['best_epoch']}|{x['best']['vertex_camera_mm']:.2f}|{x['best']['vertex_translation_removed_mm']:.2f}|{x['best']['camera_mm']:.2f}|{fmt('TRAIN')}|{fmt('VAL')}|")
    (out/'RESULT_TABLES.md').write_text('# R4 actual result tables\n'+'\n'.join(lines))
    for stage in ['pilots','formal']:
        fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
        for cell in sorted((run/stage).glob('*')):
            p=cell/'run/CURVES.json'
            if not p.exists():continue
            curves=json.loads(p.read_text());ep=[x['epoch'] for x in curves]
            axes[0].plot(ep,[x['train_loss'] for x in curves],label=cell.name)
            axes[1].plot(ep,[x['val']['vertex_camera_mm'] for x in curves],label=cell.name)
            axes[2].plot(ep,[x['val']['camera_mm'] for x in curves],label=cell.name)
        for ax,title in zip(axes,['Training loss','Synthetic VAL corresponding vertices (mm)','Synthetic VAL camera (mm)']):ax.set_title(title);ax.set_xlabel('Epoch');ax.grid(alpha=.2)
        handles,labels=axes[0].get_legend_handles_labels()
        if handles:fig.legend(handles,labels,loc='outside lower center',ncols=4,fontsize=8)
        fig.savefig(out/(stage.upper()+'_CURVES.png'),dpi=150);plt.close(fig)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();summarize(a.run,a.out)
