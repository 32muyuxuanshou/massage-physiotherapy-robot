"""Review cached bodies/translations and fixed B points, with no refitting."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':140})


def load(p):
    with np.load(p) as z:return {k:z[k] for k in z.files}


def main(root,geometry):
    out=root/'reports';frames=json.loads((out/'FRAME_RESULTS.json').read_text(encoding='utf-8'))
    rr=[r for r in frames if r['dataset']=='real' and r['seed']==11];index={(r['key'],r['method']):r for r in rr}
    keys=[]
    for identity in ['p001195','p001196']:keys.append(next(r['key'] for r in rr if r['identity']==identity))
    val=[r for r in rr if r['role']=='VAL' and r['method']=='hist_med6'];worst=max(val,key=lambda r:r['p95_mm']-index[r['key'],'fine']['p95_mm'])['key'];keys.append(worst)
    methods=['coarse','fine','hist_med6','official_hist6','proj_lattice_vis_med1','lattice_nn_vis_med1']
    labels=['内部Coarse','原Fine','Coarse＋历史6步','Official＋历史6步','投影像素对应一步','同Depth格点NN一步']
    manifest=json.loads((geometry/'MANIFEST.json').read_text(encoding='utf-8'));faces=np.load(geometry/'assets/faces.npy')
    tasks={(t['key'],t['seed']):t for t in manifest['tasks'] if t['dataset']=='real'}
    for i,key in enumerate(keys,1):
        t=tasks[key,11];z=load(root/'review_inputs'/('real_s11_'+key+'.npz'));a=load(geometry/t['input']);held=load(geometry/t['heldout']);points=held['points_camera_B'];metrics=load(root/'review_inputs'/('real_s11_'+key+'_distances.npz'))
        gold=load(geometry/t['prediction']);vlist=[]
        for method in methods:
            j=list(z['method_names']).index(method)
            start=z['original_camera_m'] if method=='official_hist6' else z['coarse_camera_m']
            v=gold['vertices_camera_A'].astype(np.float64) if method=='fine' else (z['body_m']+start).astype(np.float64)+z['applied_deltas_m'][j]
            world=(v-a['A_T'])@a['A_R'];vlist.append(world@a['B_R'].T+a['B_T'])
        pmin=np.minimum(points.min(0),np.min([v.min(0) for v in vlist],axis=0));pmax=np.maximum(points.max(0),np.max([v.max(0) for v in vlist],axis=0))
        K=a['B_K'];uv=points@K.T;uv=uv[:,:2]/uv[:,2:]
        allpoints=np.concatenate(vlist+[points]);alluv=allpoints@K.T;alluv=alluv[:,:2]/alluv[:,2:];lo=alluv.min(0)-20;hi=alluv.max(0)+20
        fig,axes=plt.subplots(2,len(methods),figsize=(20,8),layout='constrained')
        for col,(method,label,v) in enumerate(zip(methods,labels,vlist)):
            row=index[key,method];ax=axes[0,col];mp=v@K.T;mp=mp[:,:2]/mp[:,2:]
            ax.add_collection(PolyCollection(mp[faces],facecolors='#bbc7d0',edgecolors='none',alpha=.22,rasterized=True))
            ax.scatter(uv[:,0],uv[:,1],c=metrics[method+'_B_mm'],s=3,cmap='turbo',vmin=0,vmax=100)
            ax.set(title=label+'\nmedian %.2f /P95 %.2f mm'%(row['median_mm'],row['p95_mm']),xlabel='B u /px',ylabel='B v /px',xlim=(lo[0],hi[0]),ylim=(hi[1],lo[1]));ax.set_aspect('equal')
            ax=axes[1,col];ax.scatter(v[:,0],v[:,2],s=.25,color='#b6c2cd',alpha=.3);m=ax.scatter(points[:,0],points[:,2],c=metrics[method+'_B_mm'],s=4,cmap='turbo',vmin=0,vmax=100)
            ax.set(xlim=(pmin[0]-.02,pmax[0]+.02),ylim=(pmin[2]-.02,pmax[2]+.02),xlabel='B X /m',ylabel='B Z /m',title='XZ侧视，同一物理范围');ax.set_aspect('equal')
        fig.colorbar(m,ax=axes[:,-1],label='固定B点→预测三角面距离mm，颜色上限100；点与统计不截断',shrink=.7)
        fig.suptitle(key+' | seed11；前两例为已知失败身份首帧，第三例为密集6步相对Fine的VAL P95最坏帧',fontsize=13)
        fig.savefig(out/('failure_%02d.png'%i));plt.close(fig)
    (out/'FIGURE_SELECTION.json').write_text(json.dumps(dict(seed=11,keys=keys,methods=methods,no_B_fit=True,selection='Known identity first frames plus worst heldout P95 degradation, no frame removed'),indent=2),encoding='utf-8')
    print('FIGURES_COMPLETE',keys)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--geometry',type=Path,default=Path('output/r5_focused_diagnostics_v1/geometry'));a=p.parse_args();main(a.root,a.geometry)
