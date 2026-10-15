"""Show actual Camera A depth/query inputs, not inferred occlusion labels."""
import json
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from replay_queries218 import cache_path

WORK=Path('/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1')


def main():
    old=json.loads((WORK/'previous/reports/Q1_RECORDS.json').read_text())
    tasks=json.loads((WORK/'previous/geometry/MANIFEST.json').read_text())['tasks']
    cases=[]
    for dataset,metric in [('native','camera_mm'),('real','median_mm'),('behave','pve_mm')]:
        rr=[r for r in old if r['dataset']==dataset and r['seed']==11]
        cases.append(max(rr,key=lambda r:r['stages']['final'][metric]-r['stages']['coarse'][metric]))
    cases.insert(2,next(r for r in old if r['dataset']=='real' and r['seed']==11 and r['identity']=='p001195'))
    fig,axes=plt.subplots(4,3,figsize=(13,15),layout='constrained');index=[]
    for i,r in enumerate(cases):
        t=next(t for t in tasks if t['dataset']==r['dataset'] and t['seed']==11 and t['key']==r['key'])
        rec=torch.load(cache_path(t),map_location='cpu',weights_only=False)
        with np.load(WORK/'query_replay_frozen_coarse/s11'/(r['dataset']+'_'+r['key']+'.npz')) as z:
            geo=z['geometry'];obs=z['observed'];wins=z['max_pool_wins']
        depth=rec['depth'][0,0].numpy();valid=rec['valid'][0,0].numpy();h,w=depth.shape
        background=np.where(valid,depth,np.nan);axes[i,0].imshow(background,cmap='gray')
        xy=(geo[:,15:17]+1)*np.array([w-1,h-1])/2
        axes[i,0].scatter(xy[~obs,0],xy[~obs,1],s=7,color='gray',marker='x')
        color=axes[i,0].scatter(xy[obs,0],xy[obs,1],s=10,c=geo[obs,14]*1000,cmap='coolwarm',vmin=-100,vmax=100)
        top=np.argsort(wins)[-5:];axes[i,0].scatter(xy[top,0],xy[top,1],s=50,facecolors='none',edgecolors='black',lw=.8)
        axes[i,0].set(xlim=(0,w-1),ylim=(h-1,0),xlabel='A depth crop u / px',ylabel='A depth crop v / px')
        axes[i,0].set_title(r['dataset']+' s11 '+r['key'],fontsize=8)
        axes[i,1].hist(geo[obs,14]*1000,bins=30,color='#157f98')
        axes[i,1].set(xlabel='Observed Z - query Z / mm (all visible queries)',ylabel='Query count')
        axes[i,1].set_title('Visible queries: %d / 256; ring: top-5 max-pool owners'%obs.sum(),fontsize=9)
        metric='camera_mm' if r['dataset']=='native' else 'median_mm' if r['dataset']=='real' else 'pve_mm'
        axes[i,2].bar(['Tx','Ty','Tz'],r['fine_delta_mm'],color=['#687da9','#37a596','#c0809e'])
        axes[i,2].axhline(0,color='gray',lw=.7);axes[i,2].set_ylabel('Historical Fine update / mm')
        axes[i,2].set_title(metric+': %.2f -> %.2f'%(r['stages']['coarse'][metric],r['stages']['final'][metric]),fontsize=10)
        index.append(dict(dataset=r['dataset'],seed=11,key=r['key'],metric=metric,
            selection='Largest historical worsening in dataset for seed11' if i!=2 else 'First pre-existing p001195 known large-drift frame',
            observed_queries=int(obs.sum()),color_saturation_mm=[-100,100],
            actual_signed_residual_minmax_mm=[float(geo[obs,14].min()*1000),float(geo[obs,14].max()*1000)]))
    fig.colorbar(color,ax=axes[:,0].tolist(),label='Signed residual / mm (colour capped; histograms use all values)',shrink=.65)
    fig.suptitle('Frozen Full Last query replay: Camera A inputs only; historical errors retained',fontsize=13)
    fig.savefig(WORK/'reports/query_examples.png',dpi=150);plt.close(fig)
    (WORK/'reports/QUERY_FIGURE_INDEX.json').write_text(json.dumps(index,indent=2))


if __name__=='__main__':main()
