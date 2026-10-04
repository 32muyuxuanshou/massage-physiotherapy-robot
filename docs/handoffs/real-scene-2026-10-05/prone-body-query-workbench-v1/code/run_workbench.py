"""Frozen learned body queries on the existing train-only MHR interface."""
import sys,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
BASE=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005');LEARN=BASE/'body_intrinsic_query_v1'
OLD=Path('/raid5/xuhd/datasets/mhr_query_engineering_interface_v1_20261005');OUT=Path('/raid5/xuhd/datasets/prone_body_query_workbench_v1_20261005')
sys.path[:0]=[str(LEARN/'code'),str(OLD/'code')]
from run_learning import body_features
from query_model import BodyIntrinsicQuery
from run_interface import read,write,sha,DATA,ASSETS,project


def main():
    start=time.monotonic();torch.set_num_threads(2);OUT.mkdir(exist_ok=True)
    cfg=read(OLD/'CONFIG.json');cfg=dict(cfg,default_method='TOPOLOGY',experimental_model='BODY_QUERY',method_status='NOT_PROMOTED',medical_label=False)
    write(OUT/'CONFIG.json',cfg)
    with np.load(OLD/'SOURCE_TEMPLATE.npz') as z:source=z['features'];corners=z['query_local_corner_idx'];bary=z['query_barycentric'];qface=z['query_face_id']
    body=torch.tensor(body_features(source),device='cuda');qbody=(body[corners]*torch.tensor(bary[:,:,None],dtype=torch.float32,device='cuda')).sum(1)
    models=[];weights=[]
    for seed in range(3):
        ck=next(r for r in read(LEARN/f'TRAINING_LEDGER_{seed}.json')['runs'] if r['mode']=='BODY_QUERY');assert sha(Path(ck['checkpoint_path']))==ck['checkpoint_sha256']
        m=BodyIntrinsicQuery('BODY_QUERY').cuda();m.load_state_dict(torch.load(ck['checkpoint_path'],weights_only=True)['state_dict']);m.eval()
        with torch.no_grad():sd=m.descriptors(None,body);qd=(sd[corners]*torch.tensor(bary[:,:,None],dtype=torch.float32,device='cuda')).sum(1)
        models.append((seed,m,qd,ck));weights.append(Path(ck['checkpoint_path']))
    inputs=read(OLD/'INPUT_MANIFEST.json');oldtargets=read(OLD/'TARGET_MANIFEST.json')
    frozen=[OUT/'PROTOCOL.md',OUT/'CONFIG.json',Path(__file__),LEARN/'code/query_model.py',LEARN/'code/run_learning.py',OLD/'code/run_interface.py',OLD/'SOURCE_TEMPLATE.npz',ASSETS/'candidate_posterior_mask.json',*weights,
        *[Path(r['path']) for r in inputs],*[Path(r['mesh_path']) for r in oldtargets if r['method']=='TOPOLOGY'],
        *[DATA/'inputs'/s/'input.npz' for s in cfg['cohort']],*[DATA/'inputs'/s/f'split_{seed}.npz' for s in cfg['cohort'] for seed in range(3)]]
    freeze=[dict(path=str(p),sha256=sha(p)) for p in frozen];write(OUT/'SOURCE_FREEZE.json',freeze);write(OUT/'INPUT_MANIFEST.json',inputs)
    (OUT/'targets').mkdir(exist_ok=True);mask=np.asarray(read(ASSETS/'candidate_posterior_mask.json')['face_ids']);rows=[]
    for inp in inputs:
        with np.load(inp['path']) as z:features=z['features'];pointids=z['source_global_point_idx']
        target=torch.tensor(body_features(features),device='cuda');top=next(r for r in oldtargets if (r['subject'],r['split_seed'],r['mesh_method'],r['method'])==(inp['subject'],inp['split_seed'],inp['mesh_method'],'TOPOLOGY'))
        with np.load(top['mesh_path']) as z:v=z['vertices_m'];f=z['faces']
        with np.load(top['path']) as z:topology=dict(z)
        with np.load(DATA/'inputs'/inp['subject']/'input.npz') as z:points=z['points_m']
        options=[('TOPOLOGY',-1,topology,np.full(len(bary),-1,int),None)]
        nn=cKDTree(target.cpu().numpy()[:,:3]).query(qbody.cpu().numpy()[:,:3])[1]
        options.append(('BODY_CHART_NN',-1,project(points[pointids[nn]],v,f,mask),pointids[nn],None))
        for seed,m,qd,ck in models:
            with torch.no_grad():
                td=m.descriptors(None,target);dot=torch.nn.functional.normalize(qd,dim=-1)@torch.nn.functional.normalize(td,dim=-1).T
                k=len(qd);n=len(td);joined=torch.cat([qd[:,None,:].expand(-1,n,-1),td[None,:,:].expand(k,-1,-1),qbody[:,None,:3]-target[None,:,:3]],-1)
                chosen=(dot*20+m.score(joined).squeeze(-1)).argmax(-1).cpu().numpy()
            options.append(('BODY_QUERY',seed,project(points[pointids[chosen]],v,f,mask),pointids[chosen],ck['checkpoint_sha256']))
        for method,seed,bound,idx,ck in options:
            p=OUT/'targets'/f'{inp["subject"]}_{inp["split_seed"]}_{inp["mesh_method"]}_{method}_{seed}.npz'
            keys=['xyz_m','face_id','barycentric','normals','query_m','projection_distance_m']
            np.savez_compressed(p,**{key:bound[key] for key in keys},source_global_point_idx=idx,topology_xyz_m=topology['xyz_m'])
            rows.append(dict(subject=inp['subject'],role=top['role'],split_seed=inp['split_seed'],mesh_method=inp['mesh_method'],method=method,model_seed=seed,path=str(p),sha256=sha(p),mesh_path=top['mesh_path'],mesh_sha256=top['mesh_sha256'],input_path=inp['path'],input_sha256=inp['sha256'],checkpoint_sha256=ck,
                projection_median_mm=float(np.median(bound['projection_distance_m'])*1000),offset_from_topology_median_mm=float(np.median(np.linalg.norm(bound['xyz_m']-topology['xyz_m'],axis=1))*1000),medical_label=False,robot_release=False,visibility_known=False))
        if inp['split_seed']==2 and inp['mesh_method']=='RigidD':print('WORKBENCH_SUBJECT',inp['subject'],len(rows),flush=True)
    write(OUT/'TARGET_MANIFEST.json',rows)
    for a in freeze:assert sha(Path(a['path']))==a['sha256']
    write(OUT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,records=len(rows),engineering_points=len(rows)*8,default_method='TOPOLOGY',source_unchanged=True,new_training=0,new_sam=0,new_mesh_fit=0))
    print('WORKBENCH_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':main()
