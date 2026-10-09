"""Matched-pilot failure comparisons from saved meshes; no inference/refitting."""
import os
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json,sys
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from render_losses import MeshRenderer


def main():
    torch.set_num_threads(2)
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(a.root/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code'))
    from surface_metrics import point_to_triangle_distances
    old=a.root/'runs/r3_multiseed_v1';faces=np.load(old/'real/official/faces.npy')
    renderer=MeshRenderer(torch.as_tensor(faces,device='cuda'),1080,1920)
    selected=json.loads((a.run/'failure/FAILURE_AUDIT.json').read_text())['records']
    rows=json.loads((a.root/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    seen={r['identity'] for r in selected};normal=[]
    for row in rows:
        if row['role']=='VAL' and row['identity'] not in seen:
            normal.append(row);seen.add(row['identity'])
        if len(normal)==2:break
    selected=selected+normal;rowmap={(r['sequence'],r['frame']):r for r in rows}
    dirs={'Official':old/'real/official','Official + Txyz':a.run/'txyz/txyz/official'}
    dirs.update({name:a.run/'pilots'/mode/'real' for mode,name in [('rgb_only','RGB-only pilot'),
        ('cross_attention','Cross pilot'),('geometry_attention','Geometry A'),('mhr_refinement','MHR B')]})
    manifest=[]
    for item in selected:
        row=rowmap[item['sequence'],item['frame']];key=f"{row['sequence']}_{row['frame']:06d}"
        aa=np.load(a.root/'datasets/registered_v1'/row['views']['kinect_000']['file'])
        bb=np.load(a.root/'datasets/registered_v1'/row['views']['kinect_001']['file'])
        points=np.load(a.root/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
        fig,axes=plt.subplots(2,7,figsize=(25,10),layout='constrained')
        axes[0,0].imshow(aa['rgb']);axes[0,0].set_title('Camera A RGB input')
        axes[1,0].imshow(bb['rgb']);axes[1,0].set_title('Camera B RGB; evaluation only')
        K=bb['K'];uv=points[:,:2]/points[:,2,None]*np.array([K[0,0],K[1,1]])+K[:2,2]
        record=dict(identity=row['identity'],role=row['role'],sequence=row['sequence'],frame=row['frame'],
            figure=key+'.jpg',selection='R3 prespecified failure' if item not in normal else 'first other VAL identity',methods={})
        for i,(label,path) in enumerate(dirs.items(),1):
            z=np.load(path/(key+'.npz'));dist=point_to_triangle_distances(points,z['vertices_camera_B'],faces)*1000
            with torch.no_grad():rd,_=renderer(torch.tensor(z['vertices_camera_A'][None],device='cuda',dtype=torch.float32),
                torch.tensor(aa['K'][None],device='cuda'))
            hit=rd[0].cpu().numpy()>0;rgb=aa['rgb'].copy();rgb[hit]=(.45*rgb[hit]+.55*np.array([190,70,220])).astype(np.uint8)
            axes[0,i].imshow(rgb);axes[0,i].contour(hit,levels=[.5],colors=['lime'],linewidths=.6)
            med=float(np.median(dist));p95=float(np.quantile(dist,.95));axes[0,i].set_title(f'{label}\nB median {med:.1f} / P95 {p95:.1f} mm')
            axes[1,i].imshow(bb['rgb'],alpha=.55);im=axes[1,i].scatter(uv[:,0],uv[:,1],s=4,c=dist,cmap='inferno',vmin=0,vmax=150)
            axes[1,i].set_title('Exact held-out surface residual')
            record['methods'][label]=dict(median_mm=med,p95_mm=p95)
        for rowid in range(2):
            x0,y0,x1,y1=(aa if rowid==0 else bb)['bbox'];pad=.12*max(x1-x0,y1-y0)
            for ax in axes[rowid]:ax.set_xlim(max(0,x0-pad),min(1920,x1+pad));ax.set_ylim(min(1080,y1+pad),max(0,y0-pad));ax.axis('off')
        fig.colorbar(im,ax=axes[1,1:].tolist(),shrink=.6,label='Camera B measured point -> predicted triangle (mm)')
        fig.suptitle(key+' | 100 TRAIN identities, 8 epochs, seed11; green silhouette / magenta predicted mesh',fontsize=14)
        fig.savefig(a.out/record['figure'],dpi=125);plt.close(fig);manifest.append(record)
        (a.out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(records=manifest,source='saved final native meshes; no refitting',test_used=False),indent=2))
        print('PILOT_VIS',len(manifest),'/',len(selected),flush=True)


if __name__=='__main__':main()
