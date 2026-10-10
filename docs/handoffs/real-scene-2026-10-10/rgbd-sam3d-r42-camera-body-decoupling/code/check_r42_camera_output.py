"""CPU Torch integration QA with native caches and unmodified official projection.

The official model's projection methods are loaded verbatim via AST to avoid
loading 2GB+ weights on a no-GPU instance. This is projection/output QA, not a
fresh end-to-end Official inference or model-load result.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace, MethodType
import numpy as np
import torch
from camera_only_r42 import camera_only_output, predict


def function(path,name,space,method=False):
    tree=ast.parse(path.read_text())
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
    if method and name=='perspective_projection':nodes=[n for n in nodes if n.args.args[0].arg=='self']
    assert len(nodes)==1
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),space)
    return space[name]


def main(a):
    torch.set_num_threads(1)
    src=a.official/'sam_3d_body/models'
    space=dict(torch=torch,Dict=dict)
    geometry_projection=function(src/'modules/geometry_utils.py','perspective_projection',space)
    projection=function(src/'heads/camera_head.py','perspective_projection',space,True)
    space['perspective_projection']=geometry_projection
    camera_project=function(src/'meta_arch/sam3d_body.py','camera_project',space)
    crop=function(src/'meta_arch/sam3d_body.py','_full_to_crop',space)
    head=SimpleNamespace(default_scale_factor=1.)
    head.perspective_projection=MethodType(projection,head)
    official=SimpleNamespace(body_batch_idx=torch.tensor([0]),head_camera=head,
        cfg=SimpleNamespace(MODEL=SimpleNamespace(DECODER={'USE_INTRIN_CENTER':True})),
        _flatten_person=lambda x:x.flatten(0,1))
    official.camera_project=MethodType(camera_project,official);official._full_to_crop=MethodType(crop,official)
    state=dict(np.load(a.fixtures/'camera_only_best.npz'));anchor=np.load(a.fixtures/'FROZEN_ANCHORS.npz')
    faces=np.load(a.fixtures/'faces.npy');rows=[]
    for path in sorted(a.fixtures.glob('*_official.npz')):
        key=path.name.removesuffix('_official.npz');z=np.load(path);data=np.load(a.fixtures/(key+'_input.npz'))
        cache=torch.load(a.cache/(key+'.pt'),map_location='cpu',weights_only=False);batch=cache['batch']
        output={k:torch.from_numpy(z[k]) for k in ['pred_cam_t','global_rot','body_pose','shape','scale']}
        output['pred_vertices']=torch.from_numpy(z['vertices_camera_A'])[None]-output['pred_cam_t'][:,None]
        output['pred_keypoints_3d']=output['pred_vertices'][:,:70].clone()  # projection fixture, not anatomical GT
        result=camera_only_output(official,output,batch,data['points_camera_A'],state,anchor['face_index'],anchor['barycentric'],faces)
        body=output['pred_vertices'][0].double().numpy();anchors=(body[faces[anchor['face_index']]]*anchor['barycentric'][:,:,None]).sum(1)
        expected=predict(data['points_camera_A'],anchors,z['pred_cam_t'],state)
        camera_error=float(np.max(np.abs(result['pred_cam_t'][0].numpy()-expected)))
        va=result['vertices_camera_A'][0].numpy();K=data['A_K']
        uv=va[:,:2]/va[:,2,None]*[K[0,0],K[1,1]]+K[:2,2]
        uv_error=float(np.max(np.abs(uv-result['pred_keypoints_2d_verts'][0].numpy())))
        assert camera_error<2e-6 and uv_error<.002
        unchanged=all(torch.equal(output[k],result[k]) for k in ['pred_vertices','pred_keypoints_3d','global_rot','body_pose','shape','scale'])
        assert unchanged
        missing=camera_only_output(official,output,batch,data['points_camera_A'][:0],state,anchor['face_index'],anchor['barycentric'],faces)
        assert all(torch.equal(missing[k],output[k]) for k in output)
        rows.append(dict(key=key,status='PASS',camera_max_error_m=camera_error,projection_vertex_max_error_px=uv_error,
                         body_arrays_exact=True,missing_depth_output_exact=True,fixture_keypoints='70 native vertices; projection only'))
    assert len(rows)==4
    report=dict(status='PASS',scope='cached native output + exact official projection AST; no full SAM model load or fresh network inference',
        records=rows,torch_version=torch.__version__,cuda_used=False,
        official_projection_source_sha256={str(p.relative_to(a.official)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [src/'heads/camera_head.py',src/'meta_arch/sam3d_body.py',src/'modules/geometry_utils.py']},
        head_sha256=hashlib.sha256((Path(__file__).parent/'camera_only_r42.py').read_bytes()).hexdigest())
    a.out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
