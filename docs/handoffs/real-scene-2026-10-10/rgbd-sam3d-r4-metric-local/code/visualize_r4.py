"""Prespecified real failure panels from cached native meshes, no refitting."""
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


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--cells',type=Path,required=True)
    p.add_argument('--names',nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();torch.set_num_threads(2)
    a.out.mkdir(parents=True,exist_ok=True);R=a.root;old=R/'runs/r3_multiseed_v1';r31=R/'runs/r31_diagnosis_pilot_v1'
    sys.path.insert(0,str(R/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code'))
    from surface_metrics import point_to_triangle_distances
    selected=json.loads((r31/'pilot_visuals/VISUALIZATION_MANIFEST.json').read_text())['records']
    rows=json.loads((R/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    lookup={(r['sequence'],r['frame']):r for r in rows};faces=np.load(old/'real/official/faces.npy')
    renderer=MeshRenderer(torch.as_tensor(faces,device='cuda'),1080,1920)
    methods={'Official':old/'real/official','Official + Txyz':r31/'txyz/txyz/official',
        'R3 RGB seed11':old/'formal/cells/rgb_only_seed11/real'}
    methods.update({n:a.cells/n/'real' for n in a.names});records=[]
    for entry in selected:
        r=lookup[entry['sequence'],entry['frame']];key=f"{r['sequence']}_{r['frame']:06d}"
        aa=np.load(R/'datasets/registered_v1'/r['views']['kinect_000']['file']);bb=np.load(R/'datasets/registered_v1'/r['views']['kinect_001']['file'])
        points=np.load(R/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
        K=bb['K'];uv=points[:,:2]/points[:,2,None]*np.array([K[0,0],K[1,1]])+K[:2,2]
        cols=len(methods)+1;fig,axes=plt.subplots(2,cols,figsize=(3.6*cols,10),layout='constrained')
        axes[0,0].imshow(aa['rgb']);axes[0,0].set_title('Camera A RGB input')
        axes[1,0].imshow(bb['rgb']);axes[1,0].set_title('Camera B: evaluation only')
        record=dict(identity=r['identity'],role=r['role'],sequence=r['sequence'],frame=r['frame'],figure=key+'.jpg',methods={})
        for i,(label,directory) in enumerate(methods.items(),1):
            z=np.load(directory/(key+'.npz'));dist=point_to_triangle_distances(points,z['vertices_camera_B'],faces)*1000
            with torch.no_grad():rd,_=renderer(torch.tensor(z['vertices_camera_A'][None],device='cuda',dtype=torch.float32),torch.tensor(aa['K'][None],device='cuda'))
            hit=rd[0].cpu().numpy()>0;rgb=aa['rgb'].copy();rgb[hit]=(.45*rgb[hit]+.55*np.array([190,70,220])).astype(np.uint8)
            median=float(np.median(dist));p95=float(np.quantile(dist,.95))
            axes[0,i].imshow(rgb);axes[0,i].contour(hit,levels=[.5],colors=['lime'],linewidths=.6)
            axes[0,i].set_title(f'{label}\nB med {median:.1f} / P95 {p95:.1f} mm')
            axes[1,i].imshow(bb['rgb'],alpha=.55);im=axes[1,i].scatter(uv[:,0],uv[:,1],s=4,c=dist,cmap='inferno',vmin=0,vmax=150)
            axes[1,i].set_title('Held-out point -> exact triangle')
            record['methods'][label]=dict(median_mm=median,p95_mm=p95,camera_xyz_m=z['pred_cam_t'].reshape(-1,3)[0].tolist())
        for level in range(2):
            x0,y0,x1,y1=(aa if level==0 else bb)['bbox'];pad=.12*max(x1-x0,y1-y0)
            for ax in axes[level]:ax.set_xlim(max(0,x0-pad),min(1920,x1+pad));ax.set_ylim(min(1080,y1+pad),max(0,y0-pad));ax.axis('off')
        fig.colorbar(im,ax=axes[1,1:].tolist(),shrink=.6,label='Independent Camera B residual (mm)')
        fig.suptitle(key+' | original R3.1 prespecified 16 frames | predicted magenta mesh / green silhouette',fontsize=14)
        fig.savefig(a.out/record['figure'],dpi=125);plt.close(fig);records.append(record)
        (a.out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(records=records,source='cached final meshes; no inference/refitting; fixed 0-150mm colour scale',selection='same14 historical failures+2 otherVAL identities as R3.1',test_read=False),indent=2))
        print('VISUAL',len(records),'/',len(selected),flush=True)
