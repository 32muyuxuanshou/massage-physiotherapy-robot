"""All cases and post-estimation response audit; no estimator reruns."""
import argparse,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_bounded import PARENT,read,write,sha,csv_write


def main(root):
    rows=read(root/'PER_CASE_RESULTS.json');cfg=read(root/'CONTRACT.json');manifest=read(root/'CACHE_MANIFEST.json')
    cases=read(PARENT/'CASE_MANIFEST.json');query=cfg['query_indices'];(root/'figures').mkdir(exist_ok=True)
    ids=read(PARENT/'POSTERIOR_FACE_IDS.json')['face_ids'];paired=[];noise=[];visuals=[]
    for case in cases:
        s,c=case['subject'],case['case'];subset=[r for r in rows if r['subject']==s and r['case']==c]
        cache={r['method']:np.load(r['path']) for r in manifest if r['subject']==s and r['case']==c}
        truth=np.load(case['truth_path'])['reference_xyz_m'];mesh=np.load(case['mesh_path']);V,F=mesh['vertices_m'],mesh['faces']
        support=V[np.unique(F[ids].ravel())]
        response={}
        for prefix in ['RBF','CONVEX4']:
            exact,noisy=cache[prefix+'_EXACT'],cache[prefix+'_NOISY5']
            pre=np.linalg.norm(noisy['preprojection_xyz_m']-exact['preprojection_xyz_m'],axis=1)*1000
            post=np.linalg.norm(noisy['xyz_m']-exact['xyz_m'],axis=1)*1000
            response[prefix]=dict(query_pre_max_mm=float(pre[query].max()),query_post_max_mm=float(post[query].max()))
        noise.append(dict(subject=s,case=c,**response))
        by={r['method']:r for r in subset}
        paired.append(dict(subject=s,role=by['FIXED']['role'],case=c,
            convex_exact_minus_fixed_mm=by['CONVEX4_EXACT']['query_median_mm']-by['FIXED']['query_median_mm'],
            convex_noisy_minus_fixed_mm=by['CONVEX4_NOISY5']['query_median_mm']-by['FIXED']['query_median_mm'],
            convex_exact_minus_rbf_exact_mm=by['CONVEX4_EXACT']['query_median_mm']-by['RBF_EXACT']['query_median_mm'],
            convex_noisy_minus_rbf_noisy_mm=by['CONVEX4_NOISY5']['query_median_mm']-by['RBF_NOISY5']['query_median_mm']))
        fig,axes=plt.subplots(1,3,figsize=(16,6))
        for ax,(x,y) in zip(axes[:2],[(0,1),(0,2)]):
            ax.scatter(support[:,x]*1000,support[:,y]*1000,color='gray',alpha=.15,s=1)
            ax.scatter(truth[query,x]*1000,truth[query,y]*1000,color='black',marker='*',s=90,label='Unprovided synthetic reference')
            for method,color in zip(cfg['methods'],['red','deepskyblue','blue','limegreen','magenta']):
                xyz=cache[method]['xyz_m'][query]
                ax.scatter(xyz[:,x]*1000,xyz[:,y]*1000,color=color,s=20,label=method)
            ax.set_xlabel(['X','Y','Z'][x]+' mm');ax.set_ylabel(['X','Y','Z'][y]+' mm');ax.set_aspect('equal',adjustable='datalim')
        axes[0].invert_yaxis();axes[0].legend(fontsize=7)
        positions=np.arange(4);width=.14
        for k,method in enumerate(cfg['methods']):
            errors=np.asarray(by[method]['per_probe_error_mm'])[query]
            axes[2].bar(positions+(k-2)*width,errors,width,label=method)
        axes[2].set_xticks(positions,[str(i) for i in query]);axes[2].set_ylabel('Unprovided probe error mm');axes[2].set_xlabel('Fixed query identity');axes[2].legend(fontsize=7)
        fig.suptitle(s+' / '+c+' / same fixed D_VECTOR surface\nProgram-generated reference, not patient/acupoint ground truth; all five methods retained')
        fig.tight_layout();path=root/'figures'/(s+'_'+c+'.png');fig.savefig(path,dpi=120);plt.close(fig)
        visuals.append(dict(subject=s,case=c,path=str(path),sha256=sha(path)))
    csv_write(root/'PAIRED_CHANGES.csv',paired);write(root/'QUERY_NOISE_RESPONSE.json',noise);write(root/'VISUALIZATION_MANIFEST.json',visuals)
    summary={}
    for c in cfg['cases']:
        subset=[r for r in paired if r['case']==c and r['role']=='consumed_validation']
        summary[c]={}
        for key in ['convex_exact_minus_fixed_mm','convex_noisy_minus_fixed_mm','convex_exact_minus_rbf_exact_mm','convex_noisy_minus_rbf_noisy_mm']:
            values=np.asarray([r[key] for r in subset]);summary[c][key]=dict(improved=int((values<0).sum()),degraded=int((values>0).sum()),paired_median_mm=float(np.median(values)))
    summary['query_noise_max_all60']={m:dict(pre_mm=max(r[m]['query_pre_max_mm'] for r in noise),post_mm=max(r[m]['query_post_max_mm'] for r in noise)) for m in ['RBF','CONVEX4']}
    write(root/'PAIRED_SUMMARY.json',summary)
    print('ALL60_VISUALIZED',summary,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
