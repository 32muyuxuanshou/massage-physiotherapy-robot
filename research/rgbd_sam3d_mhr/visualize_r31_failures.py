"""Saved-mesh real failure audit, exact B residuals and A-only counterfactual swaps."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json,sys
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from r3_common import load_official
from render_losses import MeshRenderer
from humman_geometry import transform_camera


def native_regenerate(head,p):
    t=lambda k:torch.as_tensor(p[k],device='cuda',dtype=torch.float32).reshape(1,-1)
    v,j,jc=head.mhr_forward(global_trans=torch.zeros((1,3),device='cuda'),global_rot=t('global_rot'),
        body_pose_params=t('body_pose'),hand_pose_params=torch.zeros((1,108),device='cuda') if 'hand' not in p else t('hand'),
        scale_params=t('scale'),shape_params=t('shape'),return_keypoints=True,return_joint_coords=True)
    return v*torch.tensor([1.,-1.,-1.],device='cuda')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);root=a.root;base=root/'runs/r3_multiseed_v1'
    sys.path.insert(0,str(root/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code'))
    from surface_metrics import point_to_triangle_distances
    official_report=json.loads((base/'real/official/HUMMAN_RESULTS.json').read_text())
    cross_report=json.loads((base/'formal/cells/cross_attention_seed11/real/HUMMAN_RESULTS.json').read_text())
    ref={(r['sequence'],r['frame']):r for role in ['TRAIN','VAL'] for r in official_report['results'][role]['records']}
    train=cross_report['results']['TRAIN']['records']
    worst=sorted(train,key=lambda r:r['triangle']['p95_mm']-ref[r['sequence'],r['frame']]['triangle']['p95_mm'],reverse=True)[:6]
    selected=[r for r in cross_report['results']['VAL']['records'] if r['identity']=='p001196']+worst
    rows=json.loads((root/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    rowmap={(r['sequence'],r['frame']):r for r in rows}
    faces=np.load(base/'real/official/faces.npy');model,_=load_official(root);renderer=MeshRenderer(model.head_pose.faces,1080,1920)
    dirs={'Official':base/'real/official','RGB-only':base/'formal/cells/rgb_only_seed11/real',
          'Cross-attention':base/'formal/cells/cross_attention_seed11/real'}
    records=[]
    for idx,row in enumerate(selected):
        raw=rowmap[row['sequence'],row['frame']];name=f"{row['sequence']}_{row['frame']:06d}"
        aa=np.load(root/'datasets/registered_v1'/raw['views']['kinect_000']['file'])
        bb=np.load(root/'datasets/registered_v1'/raw['views']['kinect_001']['file'])
        points=np.load(root/'datasets/heldout/humman_r3_k1_v1'/(name+'.npz'))['points_camera_B']
        data={k:np.load(d/(name+'.npz')) for k,d in dirs.items()}
        distances={k:point_to_triangle_distances(points,z['vertices_camera_B'],faces)*1000 for k,z in data.items()}
        fig=plt.figure(figsize=(20,12),layout='constrained');axes=[]
        for i in range(10):axes.append(fig.add_subplot(2,5,i+1))
        axes[0].imshow(aa['rgb']);axes[0].set_title('Camera A RGB input')
        depth=aa['depth_rgb_z_m'];masked=np.where(aa['valid'],depth,np.nan)
        axes[1].imshow(aa['rgb'],alpha=.25);im=axes[1].imshow(masked,cmap='turbo',vmin=np.nanpercentile(masked,2),vmax=np.nanpercentile(masked,98))
        axes[1].set_title('Camera A registered measured Z (m)');fig.colorbar(im,ax=axes[1],shrink=.6)
        for i,(label,z) in enumerate(data.items(),2):
            with torch.no_grad():rd,_=renderer(torch.tensor(z['vertices_camera_A'][None],device='cuda',dtype=torch.float32),torch.tensor(aa['K'][None],device='cuda'))
            hit=rd[0].cpu().numpy()>0;rgb=aa['rgb'].copy();colour=np.array([190,70,220]);rgb[hit]=(.4*rgb[hit]+.6*colour).astype(np.uint8)
            axes[i].imshow(rgb);axes[i].contour(hit,levels=[.5],colors=['lime'],linewidths=.4)
            axes[i].set_title(f'{label} | B med {np.median(distances[label]):.1f}, P95 {np.quantile(distances[label],.95):.1f} mm')
        axes[5].imshow(bb['rgb']);axes[5].set_title('Independent Camera B RGB')
        K=bb['K'];uv=points[:,:2]/points[:,2,None]*np.array([K[0,0],K[1,1]])+K[:2,2]
        for i,(label,dist) in enumerate(distances.items(),6):
            axes[i].imshow(bb['rgb'],alpha=.5);im=axes[i].scatter(uv[:,0],uv[:,1],s=3,c=dist,cmap='inferno',vmin=0,vmax=150)
            axes[i].set_xlim(0,1920);axes[i].set_ylim(1080,0);axes[i].set_title(f'{label}: B point -> exact triangle (mm)')
        fig.colorbar(im,ax=axes[6:9],shrink=.6)
        ax=axes[9];ax.scatter(points[:,0],points[:,2],s=2,c='black',alpha=.25,label='measured Camera B')
        for label,z in data.items():v=z['vertices_camera_B'][::20];ax.scatter(v[:,0],v[:,2],s=1,alpha=.35,label=label)
        ax.set_xlabel('Camera B X (m)');ax.set_ylabel('Camera B Z (m)');ax.set_aspect('equal');ax.invert_yaxis();ax.legend(fontsize=7);ax.set_title('3D top slice / pointcloud; no refitting')
        for ax in axes[:9]:ax.axis('off')
        fig.suptitle(name+' | seed11 | green = predicted silhouette; magenta = predicted mesh; B heatmap = actual held-out residual',fontsize=13)
        path=a.out/(name+'.jpg');fig.savefig(path,dpi=120);plt.close(fig)
        off=data['Official'];cross=data['Cross-attention'];delta=cross['vertices_camera_A']-off['vertices_camera_A']
        camdelta=(cross['pred_cam_t']-off['pred_cam_t']).reshape(-1,3)[0]
        centered=(delta-delta.mean(0)).__array__()
        # This is deformation of the predicted meshes, not a true-body attribution.
        reg=dict(camera_delta_mm=(camdelta*1000).tolist(),mesh_center_delta_mm=(delta.mean(0)*1000).tolist(),
            corresponding_centered_mesh_change_median_mm=float(np.median(np.linalg.norm(centered,axis=1))*1000),
            pose_parameter_periodic_change_deg=float(np.mean(np.abs(np.arctan2(np.sin(cross['body_pose']-off['body_pose']),np.cos(cross['body_pose']-off['body_pose']))))*180/np.pi),
            shape_change_rmse=float(np.sqrt(np.mean((cross['shape']-off['shape'])**2))),
            scale_change_rmse=float(np.sqrt(np.mean((cross['scale']-off['scale'])**2))))
        # Camera-only and rigid-only remove localization hypotheses without B fitting.
        cf={}
        camA=off['vertices_camera_A']+camdelta
        ca={k:aa[k] for k in ['R','T']};cb={k:bb[k] for k in ['R','T']}
        dd=point_to_triangle_distances(points,transform_camera(camA,ca,cb),faces)*1000
        cf['official_mesh_cross_camera_only']=dict(median_mm=float(np.median(dd)),p95_mm=float(np.quantile(dd,.95)))
        # Kabsch aligns Cross to Official corresponding vertices, not observed B points.
        src=cross['vertices_camera_A'];dst=off['vertices_camera_A'];s=src-src.mean(0);t=dst-dst.mean(0)
        U,_,Vt=np.linalg.svd(s.T@t);Q=U@np.diag([1,1,np.linalg.det(U@Vt)])@Vt
        vc=s@Q+dst.mean(0);dd=point_to_triangle_distances(points,transform_camera(vc,ca,cb),faces)*1000
        cf['cross_rigid_aligned_to_official_mesh']=dict(median_mm=float(np.median(dd)),p95_mm=float(np.quantile(dd,.95)))
        records.append(dict(identity=row['identity'],role=row['role'],sequence=row['sequence'],frame=row['frame'],figure=path.name,
            metrics={k:dict(median_mm=float(np.median(d)),p95_mm=float(np.quantile(d,.95))) for k,d in distances.items()},
            changes=reg,counterfactual=cf,interpretation='Diagnostic swaps and predicted-mesh Kabsch only; no fitted GT, anatomical causality or B optimization'))
        np.savez_compressed(a.out/(name+'_B_residuals.npz'),points_camera_B=points,**{k.replace('-','_'):d for k,d in distances.items()})
        (a.out/'FAILURE_AUDIT.json').write_text(json.dumps(dict(records=records,selection='all p001196 + top6 TRAIN P95 degradations; same seed11',
            residual='exact measured Camera B point to predicted triangle',test_used=False),indent=2));print('FAILURE_VIS',idx+1,'/',len(selected),flush=True)


if __name__=='__main__':main()
