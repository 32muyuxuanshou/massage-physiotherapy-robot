"""Actual cached meshes and fixed B points, no RGB or post-hoc alignment."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':140})


def main(root):
    previous=Path('output/r5_focused_diagnostics_v1/geometry')
    tasks=json.loads((previous/'MANIFEST.json').read_text())['tasks'];faces=np.load(previous/'assets/faces.npy')
    selection=json.loads((root/'FIGURE_SELECTION.json').read_text(encoding='utf-8'));index=[]
    for num,item in enumerate(selection['cases'],1):
        task=next(t for t in tasks if t['dataset']=='real' and t['seed']==11 and t['key']==item['key'])
        with np.load(previous/task['input']) as z:K=z['B_K'];ca={k:z['A_'+k] for k in ['R','T']};cb={k:z['B_'+k] for k in ['R','T']}
        with np.load(previous/task['heldout']) as z:points=z['points_camera_B']
        assert len(points)==2048
        project=lambda p:(p@K.T)[:,:2]/p[:,2:]
        meshes=[];errors=[]
        names=['Parent','E0','E1_half','E1_zero','E2_l2'];titles=['原Full Last','E0 原监督','Camera权重0.5','Camera权重0','仅L2正则']
        for arm in names:
            with np.load(root/'visual_inputs'/(arm+'_'+item['key']+'_mesh.npz')) as z:va=z['vertices_camera_A'].astype(np.float64)
            world=(va-ca['T'])@ca['R'];v=world@cb['R'].T+cb['T'];meshes.append(v)
            with np.load(root/'visual_inputs'/(arm+'_'+item['key']+'_distances.npz')) as z:errors.append(z['B_mm'])
        allpoints=np.concatenate(meshes+[points]);uv=project(allpoints);lo=uv.min(0)-20;hi=uv.max(0)+20
        fig,axes=plt.subplots(2,5,figsize=(19,8),layout='constrained');puv=project(points)
        for col,(v,d,title) in enumerate(zip(meshes,errors,titles)):
            tri=v[faces];order=np.argsort(tri[:,:,2].mean(1))[::-1]
            polygons=project(tri.reshape(-1,3)).reshape(-1,3,2)[order]
            axes[0,col].add_collection(PolyCollection(polygons,facecolor='#c5ced9',edgecolor='none'))
            color=axes[0,col].scatter(puv[:,0],puv[:,1],c=d,s=3,cmap='turbo',vmin=0,vmax=100)
            axes[0,col].set(xlim=(lo[0],hi[0]),ylim=(hi[1],lo[1]),xlabel='B u / px',ylabel='B v / px',title=title+f'\nmedian {np.median(d):.2f} / P95 {np.quantile(d,.95):.2f} mm')
            axes[0,col].set_aspect('equal',adjustable='box')
            axes[1,col].scatter(v[::8,0],v[::8,2],s=1,color='#aebdcc',alpha=.45)
            axes[1,col].scatter(points[:,0],points[:,2],c=d,s=4,cmap='turbo',vmin=0,vmax=100)
            axes[1,col].set(xlim=(allpoints[:,0].min()-.03,allpoints[:,0].max()+.03),ylim=(allpoints[:,2].min()-.03,allpoints[:,2].max()+.03),xlabel='B X / m',ylabel='B Z / m',title='XZ正交侧视，同一坐标范围')
            axes[1,col].set_aspect('equal',adjustable='box')
        fig.colorbar(color,ax=axes.ravel().tolist(),shrink=.75,label='彩色：固定B实测点→预测三角面距离 mm；灰色：预测Mesh')
        fig.suptitle(item['key']+' | '+item['reason']+'\nseed11／末轮；上方是B内参的透视投影，无RGB背景；颜色上限100mm，全部点和数值不截断',fontsize=13)
        target=root/'reports'/('failure_case_%02d.png'%num);fig.savefig(target);plt.close(fig)
        index.append(dict(item,seed=11,selection='last',points=2048,colour_cap_mm=100,actual_max_mm=[float(d.max()) for d in errors],body_pose_unchanged=True,file=target.name))
    (root/'reports/FIGURE_INDEX.json').write_text(json.dumps(index,indent=2,ensure_ascii=False),encoding='utf-8');print('FAILURE_PLOTS_COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
