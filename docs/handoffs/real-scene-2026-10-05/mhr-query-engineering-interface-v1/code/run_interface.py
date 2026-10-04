"""Fixed engineering queries on MHR; optional learned matching stays experimental."""
import argparse,sys,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
BASE=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
PAIR=BASE/'paired_query_v1'
sys.path.insert(0,str(PAIR/'code'));sys.path.insert(0,str(BASE/'code'))
from pair_model import PairedQuery
from experiment import read,write,sha,normals
sys.path.insert(0,'/raid5/xuhd/datasets/mesh_guided_back_chart_v1_20261005/code')
from run_chart import project,DATA,ASSETS
OUT=Path('/raid5/xuhd/datasets/mhr_query_engineering_interface_v1_20261005')


def normalize_mesh(v,f):
    tri=v[f];weights=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    center=np.average(tri.mean(1),axis=0,weights=weights);scale=np.sqrt(weights.sum())
    return (v-center)/scale,center,scale


def prepare():
    OUT.mkdir(exist_ok=True);cfg=read(Path('/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004/CONFIG.json'))
    atlas=read(OUT/'ENGINEERING_BACK_ATLAS_V2.json');assert atlas['native_unit']=='cm'
    v=np.load(ASSETS/'mhr_rest_vertices.npy').astype(np.float64)*.01;f=np.load(ASSETS/'mhr_faces.npy');mask=np.asarray(read(ASSETS/'candidate_posterior_mask.json')['face_ids'])
    ids=np.unique(f[mask]);sv,center,scale=normalize_mesh(v,f);feat=np.column_stack([sv[ids],normals(sv[ids])]).astype(np.float32)
    qface=np.asarray([r['face_id'] for r in atlas['records']]);bary=np.asarray([r['barycentric'] for r in atlas['records']]);corners=f[qface]
    q=np.sum(sv[corners]*bary[:,:,None],1);raw=np.sum(v[corners]*bary[:,:,None],1)
    assert np.allclose(raw*1000,np.asarray([r['canonical_xyz_mm'] for r in atlas['records']]),atol=1e-3,rtol=0)
    lookup=np.full(len(v),-1,int);lookup[ids]=np.arange(len(ids));assert np.all(lookup[corners]>=0)
    np.savez_compressed(OUT/'SOURCE_TEMPLATE.npz',features=feat,normalized_full_vertices=sv,posterior_vertex_ids=ids,
                        query_xyz_normalized=q,query_local_corner_idx=lookup[corners],query_barycentric=bary,query_face_id=qface,
                        center_m=center,scale_m=scale)
    cfg=dict(cohort=cfg['cohort'],dev=cfg['dev'],meshes={'Rigid':'Official_Rigid','RigidD':'Official_Rigid_D'},
             source_query_ids=[r['id'] for r in atlas['records']],voxel_m=.012,max_candidates=2048,default_method='TOPOLOGY',
             clinical_validated=False,robot_release=False,normalization='full mesh area-centroid / sqrt(area), then same-topology posterior Kabsch',
             normalization_differs_from_scan_vertex_centroid=True)
    write(OUT/'CONFIG.json',cfg)
    assets=[OUT/'PROTOCOL.md',OUT/'CONFIG.json',OUT/'ENGINEERING_BACK_ATLAS_V2.json',OUT/'SOURCE_TEMPLATE.npz',
            ASSETS/'mhr_rest_vertices.npy',ASSETS/'mhr_faces.npy',ASSETS/'candidate_posterior_mask.json',PAIR/'TRAINING_LEDGER.json',PAIR/'code/pair_model.py',
            Path('/raid5/xuhd/datasets/mesh_guided_back_chart_v1_20261005/code/run_chart.py'),*[p for p in (OUT/'code').glob('*.py')]]
    for r in read(PAIR/'TRAINING_LEDGER.json')['runs']:assets.append(Path(r['checkpoint_path']))
    for s in cfg['cohort']:
        assets.append(DATA/'inputs'/s/'input.npz')
        for seed in range(3):
            assets.append(DATA/'inputs'/s/f'split_{seed}.npz')
            assets.extend(DATA/'meshes'/s/f'seed_{seed}'/(stem+'.npz') for stem in cfg['meshes'].values())
    write(OUT/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in assets]);print('INTERFACE_PREPARED',len(ids),len(cfg['cohort']),len(assets),flush=True)


def match_queries(m,source,target,corner_idx,bary,q):
    hs=m.descriptors(source);ht=m.descriptors(target)
    hq=(hs[0,corner_idx]*bary[:,:,None]).sum(1)[None]
    dot=torch.nn.functional.normalize(hq,dim=-1)@torch.nn.functional.normalize(ht,dim=-1).transpose(1,2)
    n=ht.shape[1];k=hq.shape[1]
    joined=torch.cat([hq[:,:,None,:].expand(-1,-1,n,-1),ht[:,None,:,:].expand(-1,k,-1,-1),q[None,:,None,:]-target[:,None,:,:3]],dim=-1)
    return (dot*20+m.score(joined).squeeze(-1))[0].argmax(-1).cpu().numpy()


def run():
    start=time.monotonic();torch.set_num_threads(4);cfg=read(OUT/'CONFIG.json')
    for r in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    with np.load(OUT/'SOURCE_TEMPLATE.npz') as z:source=z['features'];sv=z['normalized_full_vertices'];ids=z['posterior_vertex_ids'];q=z['query_xyz_normalized'];corners=z['query_local_corner_idx'];bary=z['query_barycentric'];qface=z['query_face_id']
    mask=np.asarray(read(ASSETS/'candidate_posterior_mask.json')['face_ids']);models=[]
    for r in read(PAIR/'TRAINING_LEDGER.json')['runs']:
        assert sha(Path(r['checkpoint_path']))==r['checkpoint_sha256'];m=PairedQuery(r['mode']).cuda();m.load_state_dict(torch.load(r['checkpoint_path'],weights_only=True)['state_dict']);m.eval();models.append((r,m))
    source_tensor=torch.tensor(source[None],device='cuda');corner_tensor=torch.tensor(corners,device='cuda');bary_tensor=torch.tensor(bary,dtype=torch.float32,device='cuda');q_tensor=torch.tensor(q,dtype=torch.float32,device='cuda')
    for d in ['inputs','targets']:(OUT/d).mkdir(exist_ok=True)
    rows=[];inputs=[]
    for subject in cfg['cohort']:
        role='dev' if subject in cfg['dev'] else 'consumed_test_role'
        with np.load(DATA/'inputs'/subject/'input.npz') as z:points=z['points_m'];posterior=z['posterior_point_mask']
        for split in range(3):
            with np.load(DATA/'inputs'/subject/f'split_{split}.npz') as z:train=z['train_idx'];held=z['heldout_idx']
            used=train[posterior[train]];_,index=np.unique(np.floor(points[used]/cfg['voxel_m']).astype(int),axis=0,return_index=True)
            selected=used[index]
            if len(selected)>cfg['max_candidates']:selected=selected[np.linspace(0,len(selected)-1,cfg['max_candidates']).astype(int)]
            assert len(np.intersect1d(selected,held))==0
            for mesh,stem in cfg['meshes'].items():
                mp=DATA/'meshes'/subject/f'seed_{split}'/(stem+'.npz')
                with np.load(mp) as z:v=z['vertices_m'];f=z['faces'];assert np.isin(z['optimization_point_idx'],train).all()
                pv,center,scale=normalize_mesh(v,f);U,_,VT=np.linalg.svd(sv[ids].T@pv[ids]);R=U@VT
                if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@VT
                assert np.allclose(R@R.T,np.eye(3),atol=1e-9)
                target=((points[selected]-center)/scale)@R.T
                feat=np.column_stack([target,normals(target)]).astype(np.float32);ip=OUT/'inputs'/f'{subject}_{split}_{mesh}.npz'
                np.savez_compressed(ip,features=feat,source_global_point_idx=selected,center_m=center,scale_m=scale,canonical_to_patient_R=R)
                inputs.append(dict(subject=subject,split_seed=split,mesh_method=mesh,path=str(ip),sha256=sha(ip),candidates=len(selected),heldout_intersection=0))
                top_xyz=np.sum(v[f[qface]]*bary[:,:,None],1);normal=np.cross(v[f[qface,1]]-v[f[qface,0]],v[f[qface,2]]-v[f[qface,0]]);normal/=np.linalg.norm(normal,axis=1,keepdims=True)
                options=[('TOPOLOGY',-1,dict(xyz_m=top_xyz,face_id=qface,barycentric=bary,normals=normal,query_m=top_xyz,projection_distance_m=np.zeros(len(q))),np.full(len(q),-1,int),None)]
                nn=cKDTree(target).query(q)[1];options.append(('BODY_NN',-1,project(points[selected[nn]],v,f,mask),selected[nn],None))
                for trained,m in models:
                    with torch.no_grad():chosen=match_queries(m,source_tensor,torch.tensor(feat[None],device='cuda'),corner_tensor,bary_tensor,q_tensor)
                    query=points[selected[chosen]];options.append((trained['mode'],trained['seed'],project(query,v,f,mask),selected[chosen],trained['checkpoint_sha256']))
                for mode,model_seed,bound,point_idx,ckpt in options:
                    path=OUT/'targets'/f'{subject}_{split}_{mesh}_{mode}_{model_seed}.npz'
                    np.savez_compressed(path,**bound,source_global_point_idx=point_idx,topology_xyz_m=top_xyz)
                    rows.append(dict(subject=subject,role=role,split_seed=split,mesh_method=mesh,method=mode,model_seed=model_seed,path=str(path),sha256=sha(path),
                        mesh_path=str(mp),mesh_sha256=sha(mp),input_path=str(ip),input_sha256=sha(ip),checkpoint_sha256=ckpt,
                        projection_median_mm=float(np.median(bound['projection_distance_m'])*1000),offset_from_topology_median_mm=float(np.median(np.linalg.norm(bound['xyz_m']-top_xyz,axis=1))*1000),
                        medical_label=False,robot_release=False,visibility_known=False))
        print('INTERFACE_SOURCE',subject,len(rows),flush=True)
    write(OUT/'INPUT_MANIFEST.json',inputs);write(OUT/'TARGET_MANIFEST.json',rows)
    for r in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(OUT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',seconds=time.monotonic()-start,subjects=len(cfg['cohort']),records=len(rows),engineering_points=len(rows)*len(q),
        input_caches=len(inputs),new_training=0,new_sam=0,new_mesh_fit=0,heldout_input_intersection=0,source_unchanged=True,medical_validated=False,robot_release=False))
    print('INTERFACE_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','run'],required=True);a=p.parse_args();{'prepare':prepare,'run':run}[a.phase]()
