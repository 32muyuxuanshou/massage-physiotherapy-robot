"""Actual frozen Camera B points and cached bodies; no fitting or new inference."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import analyze_cached as diagnostic

plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':140})


def main(a):
    root=a.root;g=root/'geometry';out=root/'reports'
    manifest=json.loads((g/'MANIFEST.json').read_text())
    results=json.loads((out/'Q1_RECORDS.json').read_text())
    rr=[r for r in results if r['dataset']=='real' and r['seed']==11]
    examples=[next(r for r in rr if r['identity']=='p001195'),
        max(rr,key=lambda r:r['stages']['final']['median_mm']-r['stages']['coarse']['median_mm'])]
    diagnostic.initialize(g)
    receipts=[]
    for i,row in enumerate(examples):
        t=next(t for t in manifest['tasks'] if t['dataset']=='real' and t['seed']==11 and t['key']==row['key'])
        z=diagnostic.load(t['prediction']);inp=diagnostic.load(t['input']);held=diagnostic.load(t['heldout'])
        ca={k:inp['A_'+k] for k in ['R','T']};cb={k:inp['B_'+k] for k in ['R','T']};K=inp['B_K']
        vf=z['vertices_camera_A'].astype(float);vc=vf+z['coarse_camera'].reshape(3)-z['camera_m'].reshape(3)
        with np.load(a.official/(row['key']+'.npz')) as oz:
            vt=oz['vertices_camera_A']+np.array(t['baseline']['applied_translation_m'])
        points=held['points_camera_B'];faces=diagnostic.FACES
        vertices=[diagnostic.FUNCTIONS['transform_camera'](v,ca,cb) for v in [vc,vf,vt]]
        errors=[diagnostic.FUNCTIONS['distance'](points,v,faces)*1000 for v in vertices]
        projection=lambda p:(p@K.T)[:,:2]/p[:,2:]
        uv=projection(points);alluv=np.concatenate([uv]+[projection(v) for v in vertices]);lo=alluv.min(0);hi=alluv.max(0)
        fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
        for j,(v,d,name) in enumerate(zip(vertices,errors,['Full 内部 Coarse','Full 最终 Fine','Official+历史 Txyz'])):
            tri=v[faces];order=np.argsort(tri[:,:,2].mean(1))[::-1]
            polys=projection(tri.reshape(-1,3)).reshape(-1,3,2)[order]
            axes[0,j].add_collection(PolyCollection(polys,facecolor='#ccd4dd',edgecolor='none'))
            color=axes[0,j].scatter(uv[:,0],uv[:,1],c=d,s=3,cmap='turbo',vmin=0,vmax=100)
            axes[0,j].set(xlim=(lo[0]-25,hi[0]+25),ylim=(hi[1]+25,lo[1]-25),xlabel='B 相机 u / px',ylabel='B 相机 v / px')
            axes[0,j].set_aspect('equal',adjustable='box')
            axes[0,j].set_title(name+f'\nmedian {np.median(d):.2f} / P95 {np.quantile(d,.95):.2f} mm')
            axes[1,j].scatter(v[::8,0],v[::8,2],s=1,color='#b7c1ce',alpha=.45)
            axes[1,j].scatter(points[:,0],points[:,2],c=d,s=4,cmap='turbo',vmin=0,vmax=100)
            axes[1,j].set(xlabel='B 相机 X / m',ylabel='B 相机 Z / m',title='XZ 侧视：灰色 Mesh、彩色实测点')
            axes[1,j].set_aspect('equal',adjustable='box')
        vv=np.concatenate(vertices+[points]);xlim=(vv[:,0].min()-.03,vv[:,0].max()+.03);zlim=(vv[:,2].min()-.03,vv[:,2].max()+.03)
        for ax in axes[1]:ax.set_xlim(xlim);ax.set_ylim(zlim)
        fig.colorbar(color,ax=axes.ravel().tolist(),label='B 实测点→预测三角面距离 mm（颜色上限100；数值不截断）',shrink=.7)
        label='已知大漂移样本' if i==0 else 'seed 11 中 Fine median 负收益最大帧'
        fig.suptitle(row['key']+' | '+label+'\n上：真实内参透视投影，无 RGB 背景；下：同一 B 坐标的 XZ 侧视',fontsize=13)
        target=out/f'geometry_case_{i+1}.png';fig.savefig(target);plt.close(fig)
        receipts.append(dict(key=row['key'],seed=11,selection=label,point_count=len(points),
            color_limit_mm=100,actual_max_mm=[float(d.max()) for d in errors],
            note='B points evaluation only; projected mesh is not a raw RGB overlay; orthographic XZ explicitly labeled'))
    (out/'GEOMETRY_FIGURE_INDEX.json').write_text(json.dumps(receipts,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--official',type=Path,required=True)
    main(p.parse_args())
