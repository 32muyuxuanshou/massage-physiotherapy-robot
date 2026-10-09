"""Fixed native posed mesh; render consistent RGB/Depth at four camera distances."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse, hashlib, json, sys
from pathlib import Path
import cv2
import numpy as np
import torch
from r3_common import load_official, sha
from render_losses import MeshRenderer
from prepare_r3_cache import prepare


def build(root,out):
    import pyrender, trimesh
    out.mkdir(parents=True,exist_ok=False);official,_=load_official(root)
    data=root/'datasets/synthetic/native_scale_v2';m=json.loads((data/'MANIFEST.json').read_text())
    ids=[sorted({r['identity'] for r in m['samples'] if r['role']==role})[:2] for role in ['TRAIN','VAL']]
    source=[r for r in m['samples'] if r['identity'] in sum(ids,[]) and r['pose_id']==0 and r['camera_id']==2]
    gl=pyrender.OffscreenRenderer(640,480);renderer=MeshRenderer(official.head_pose.faces)
    faces=official.head_pose.faces.cpu().numpy();np.save(out/'faces.npy',faces);records=[];qa=[]
    sys.path.insert(0,str(root/'project_snapshot/docs/handoffs/real-scene-2026-09-09/public-rgbd-surface-finetuning-pilot-v1/code'))
    from surface_metrics import point_to_triangle_distances
    for row in source:
        assert row['role']!='TEST'
        z=np.load(data/row['file']);vertices=z['pred_vertices'];K=z['K'];original=z['pred_cam_t'].copy()
        fixed=hashlib.sha256(vertices.tobytes()).hexdigest()
        colours=np.c_[np.clip(np.array([.55,.48,.36])[None]+.1*np.sin(vertices[0,:,1:2]*15+vertices[0,:,0:1]*11),0,1),np.ones(vertices.shape[1])]
        for n,factor in enumerate([1.,1.15,1.3,1.45]):
            cam=original.copy();cam[:,2]*=factor;vc=vertices[0]+cam[0]
            scene=pyrender.Scene(bg_color=[.12,.15,.18,1],ambient_light=[.4]*3)
            scene.add(pyrender.Mesh.from_trimesh(trimesh.Trimesh(vc,faces,vertex_colors=(colours*255).astype(np.uint8),process=False),smooth=True))
            pose=np.diag([1.,-1.,-1.,1.]);scene.add(pyrender.IntrinsicsCamera(K[0,0],K[1,1],K[0,2]+.5,K[1,2]+.5,znear=.05,zfar=20),pose=pose)
            scene.add(pyrender.DirectionalLight(color=[1,1,1],intensity=2),pose=pose);rgb,_=gl.render(scene)
            with torch.no_grad():depth,_=renderer(torch.from_numpy(vc[None]).float().cuda(),torch.from_numpy(K[None]).float().cuda())
            depth=depth[0].cpu().numpy();mask=depth>0;yy,xx=np.nonzero(mask)
            assert len(xx)>1000 and xx.min()>1 and xx.max()<639 and yy.min()>1 and yy.max()<479
            pick=np.linspace(0,len(xx)-1,64).astype(int);u,v=xx[pick],yy[pick];zz=depth[v,u]
            points=np.c_[(u-K[0,2])*zz/K[0,0],(v-K[1,2])*zz/K[1,1],zz]
            distance=point_to_triangle_distances(points,vc,faces)*1000
            assert np.median(distance)<.01 and np.quantile(distance,.95)<.1
            name=f"{row['identity']}_distance{n}.npz"
            targets={key:z[key] for key in ['global_rot','body_pose','shape','scale','hand','pred_vertices','pred_keypoints_3d','pred_joint_coords']}
            np.savez_compressed(out/name,rgb=rgb,depth_m=depth,depth_clean_m=depth,mask=mask,K=K,
                bbox=np.array([xx.min(),yy.min(),xx.max()+1,yy.max()+1],np.float32),pred_cam_t=cam,**targets)
            cv2.imwrite(str(out/(name.removesuffix('.npz')+'.jpg')),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
            records.append(dict(file=name,identity=row['identity'],role=row['role'],pose_id=0,camera_id=n,
                physical_camera_factor=factor,source_file=row['file'],fixed_vertices_sha256=fixed,truth_camera_xyz_m=cam[0].tolist(),sha256=sha(out/name)))
            qa.append(dict(file=name,exact_surface_median_mm=float(np.median(distance)),exact_surface_p95_mm=float(np.quantile(distance,.95))))
    gl.delete();(out/'MANIFEST.json').write_text(json.dumps(dict(samples=records,factors=[1.,1.15,1.3,1.45],test_used=False,
        contract='same posed vertices/texture/light/K; physically change camera Z, jointly rerender RGB and Depth; bbox changes from sensor mask'),indent=2))
    (out/'GEOMETRY_QA.json').write_text(json.dumps(dict(status='PASS',records=qa,mesh_constant_each_identity=True),indent=2))
    del official,renderer;torch.cuda.empty_cache()
    prepare(root,out,out.parent/'physical_camera_cache')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();torch.set_num_threads(2);build(a.root,a.out)
