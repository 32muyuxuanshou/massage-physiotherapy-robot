"""Summarize completed R31 evidence without altering any evaluation or selection."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);figdir=a.out/'figures';figdir.mkdir(exist_ok=True)
    modes=['rgb_only','cross_attention','geometry_attention','mhr_refinement'];names=['RGB-only','Cross-Attention','Geometry A','MHR B']
    result=dict(pilots={},historical_txyz={},depth_source={},test_used=False,training_budget='100 TRAIN IDs / 800 views; 50 VAL IDs / 400 views; seed11; eight epochs')
    fig,ax=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for mode,name in zip(modes,names):
        syn=json.loads((a.run/'pilots'/mode/'run/RESULTS.json').read_text())
        real=json.loads((a.run/'pilots'/mode/'real/HUMMAN_RESULTS.json').read_text())
        abl=json.loads((a.run/'ablations_fast'/mode/'CANDIDATE_ABLATIONS.json').read_text())
        result['pilots'][mode]=dict(synthetic_best=syn['best']['identity_equal_mean'],synthetic_last=syn['last']['identity_equal_mean'],
            best_epoch=syn['best_epoch'],seconds=syn['seconds'],trainable_parameters=syn['trainable_parameters'],
            peak_memory_bytes=syn['peak_memory_bytes'],real={r:d['identity_equal_mean'] for r,d in real['results'].items()},
            ablations={domain:{cond:dict(responses=value['responses'],synthetic=value['synthetic']['identity_equal_mean'] if value['synthetic'] else None)
                for cond,value in values.items()} for domain,values in abl['conditions'].items()})
        ax[0].plot([c['epoch'] for c in syn['curves']],[c['val']['vertex_camera_mm'] for c in syn['curves']],label=name,marker='o')
        ax[1].plot([c['epoch'] for c in syn['curves']],[c['train_loss'] for c in syn['curves']],label=name,marker='o')
    ax[0].set_ylabel('Synthetic VAL corresponding vertex error (mm)');ax[1].set_ylabel('Training loss')
    for panel in ax:panel.set_xlabel('Epoch');panel.grid(alpha=.25);panel.legend(fontsize=8)
    fig.savefig(figdir/'TRAINING_CURVES.png',dpi=160);plt.close(fig)
    cheap=json.loads((a.run/'txyz/CHEAP_TXYZ_COMPARISON.json').read_text())
    for method,value in cheap['methods'].items():
        result['historical_txyz'][method]=dict(before={r:d['identity_equal_mean'] for r,d in value['before'].items()},
            after={r:d['identity_equal_mean'] for r,d in value['after'].items()},fallback_count=value['fallback_count'])
    depth=json.loads((a.run/'depth/DEPTH_SOURCE_DIAGNOSTIC.json').read_text())
    for domain,value in depth.items():
        result['depth_source'][domain]={cond:dict(responses=v['responses'],synthetic=v['synthetic']['identity_equal_mean'] if v['synthetic'] else None)
            for cond,v in value['conditions'].items()}
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    labels=['Official','Official + Txyz']+names
    for ax,role in zip(axes,['TRAIN','VAL']):
        med=[result['historical_txyz']['official']['before'][role]['median_mm'],result['historical_txyz']['official']['after'][role]['median_mm']]
        tail=[result['historical_txyz']['official']['before'][role]['p95_mm'],result['historical_txyz']['official']['after'][role]['p95_mm']]
        med.extend(result['pilots'][m]['real'][role]['median_mm'] for m in modes)
        tail.extend(result['pilots'][m]['real'][role]['p95_mm'] for m in modes)
        x=np.arange(len(labels));ax.bar(x-.18,med,.36,label='mean of frame medians');ax.bar(x+.18,tail,.36,label='mean of frame P95')
        ax.set_xticks(x,labels,rotation=25,ha='right');ax.set_ylabel('Independent Camera B surface distance (mm)');ax.set_title('HuMMan '+role);ax.legend(fontsize=8)
        for xx,v in zip(x-.18,med):ax.text(xx,v+1,f'{v:.1f}',ha='center',fontsize=7)
    fig.savefig(figdir/'REAL_CAMERA_B_COMPARISON.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    conditions=['correct','mask_rays_only','absolute_only','relative_only','flat_center','offset_0.2']
    values=result['depth_source']['synthetic_VAL_seed11']
    axes[0].bar(np.arange(len(conditions)),[values[c]['synthetic']['vertex_camera_mm'] for c in conditions])
    axes[0].set_xticks(np.arange(len(conditions)),conditions,rotation=30,ha='right');axes[0].set_ylabel('Corresponding vertex error (mm)');axes[0].set_title('R3 Cross seed11, fixed Mask/rays')
    for seed in [11,23,37]:
        values=result['depth_source']['real_TRAIN_VAL_seed'+str(seed)]
        cs=['mask_rays_only','absolute_only','relative_only','offset_0.2']
        axes[1].plot(cs,[values[c]['responses']['VAL']['vertex_camera_change_mm'] for c in cs],marker='o',label='seed '+str(seed))
    axes[1].tick_params(axis='x',rotation=25);axes[1].set_ylabel('Mesh change versus correct Depth (mm)');axes[1].set_title('Real VAL parameter response, fixed RGB/Mask/rays');axes[1].legend()
    fig.savefig(figdir/'DEPTH_SOURCE_DIAGNOSTIC.png',dpi=160);plt.close(fig)
    (a.out/'R31_SUMMARY.json').write_text(json.dumps(result,indent=2));print('R31_SUMMARY_COMPLETE',flush=True)


if __name__=='__main__':main()
