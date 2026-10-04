"""Frozen six line networks on the original train-only prone inputs and fixed meshes."""
import argparse,json,hashlib,sys,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree

PILOT=Path('/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004')
OLD=Path('/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004')
BASE=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
MASK=Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003/assets/candidate_posterior_mask.json')
PROJECTION=Path('/raid5/xuhd/datasets/back_reference_assisted_v1_20261004/code')
sys.path.insert(0,str(PILOT/'code'))
from line_net import LineNet
from data_line import features
sys.path.insert(0,str(PROJECTION))
from correspondence import surface_project


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main(root):
    start=time.monotonic();torch.set_num_threads(4)
    config=read(OLD/'CONFIG.json');queries={r['subject']:np.asarray(r['common_y_m']) for r in read(OLD/'QUERY_MANIFEST.json')}
    mask=np.asarray(read(MASK)['face_ids']);ledger=read(PILOT/'TRAINING_LEDGER.json')
    assert read(PILOT/'TRAINING_COMPLETE.json')['models']==6
    assets=[root/'PROTOCOL.md',*(root/'code').glob('*.py'),OLD/'CONFIG.json',OLD/'QUERY_MANIFEST.json',
            OLD/'CURVE_MANIFEST.json',OLD/'BINDING_MANIFEST.json',OLD/'STABILITY_RESULTS.csv',MASK,
            PILOT/'code/line_net.py',PILOT/'code/data_line.py',PILOT/'TRAINING_LEDGER.json',PROJECTION/'correspondence.py']
    for s in config['cohort']:
        assets.append(BASE/'inputs'/s/'input.npz')
        for split in range(3):
            assets.append(BASE/'inputs'/s/f'split_{split}.npz')
            assets.extend(BASE/'meshes'/s/f'seed_{split}'/(stem+'.npz') for stem in config['meshes'].values())
    assets.extend(Path(r['checkpoint_path']) for r in ledger)
    frozen=[dict(path=str(p),sha256=sha(p)) for p in assets];write(root/'SOURCE_FREEZE.json',frozen)
    models=[]
    for row in ledger:
        assert sha(row['checkpoint_path'])==row['checkpoint_sha256']
        model=LineNet().cuda();model.load_state_dict(torch.load(row['checkpoint_path'],weights_only=True)['state_dict']);model.eval()
        models.append((row,model))
    for folder in ['inputs','curves','bindings']:(root/folder).mkdir(exist_ok=True)
    curve_rows=[];binding_rows=[];input_rows=[]
    for subject in config['cohort']:
        role='dev' if subject in config['dev'] else 'consumed_test_role'
        with np.load(BASE/'inputs'/subject/'input.npz') as z:points=z['points_m'];posterior=z['posterior_point_mask']
        for split_seed in range(3):
            with np.load(BASE/'inputs'/subject/f'split_{split_seed}.npz') as z:train=z['train_idx'];held=z['heldout_idx']
            used=train[posterior[train]];assert len(np.intersect1d(used,held))==0
            observed=points[used];native=observed.copy();native[:,1]*=-1
            lo,hi=np.quantile(native[:,1],[.05,.95]);xs=np.linspace(native[:,0].min(),native[:,0].max(),128);ys=np.linspace(lo,hi,128)
            tensor,valid=features(native,xs,ys)
            inp=root/'inputs'/f'{subject}_{split_seed}.npz'
            np.savez_compressed(inp,extraction_point_idx=used,features=tensor,valid=valid,xs_m=xs,ys_feature_m=ys)
            input_rows.append(dict(subject=subject,split_seed=split_seed,path=str(inp),sha256=sha(inp),
                points=len(used),heldout_intersection=0,valid_grid_fraction=float(valid.mean())))
            meshes={}
            for mesh_method,stem in config['meshes'].items():
                path=BASE/'meshes'/subject/f'seed_{split_seed}'/(stem+'.npz')
                with np.load(path) as z:
                    assert np.isin(z['optimization_point_idx'],train).all()
                    meshes[mesh_method]=(path,z['vertices_m'].copy(),z['faces'].copy())
            for trained,model in models:
                with torch.no_grad():
                    pred=(model(torch.as_tensor(tensor[None],device='cuda:0')).softmax(-1)*
                          torch.as_tensor(xs,dtype=torch.float32,device='cuda:0')[None,None,:]).sum(-1)[0].cpu().numpy()
                xy=np.column_stack([pred,-ys])[::-1]
                distance,index=cKDTree(observed[:,:2]).query(xy);curve=observed[index]
                name=f"{subject}_input{split_seed}_{trained['strategy']}_model{trained['seed']}"
                path=root/'curves'/(name+'.npz')
                np.savez_compressed(path,query_xy_m=xy,query_y_m=xy[:,1],curve_m=curve,
                    source_global_point_idx=used[index],extraction_point_idx=used,xy_snap_distance_m=distance)
                row=dict(subject=subject,role=role,split_seed=split_seed,strategy=trained['strategy'],model_seed=trained['seed'],
                         path=str(path),sha256=sha(path),supported_fraction_3mm=float(np.mean(distance<=.003)),
                         snap_median_mm=float(np.median(distance)*1000),snap_max_mm=float(distance.max()*1000))
                curve_rows.append(row)
                query=np.column_stack([np.interp(queries[subject],xy[:,1],curve[:,j]) for j in range(3)])
                for mesh_method,(mesh_path,V,F) in meshes.items():
                    bound=surface_project(query,V,F,mask)
                    reconstructed=np.sum(V[F[bound['face_id']]]*bound['barycentric'][:,:,None],axis=1)
                    assert np.allclose(reconstructed,bound['xyz_m'],rtol=0,atol=1e-10)
                    bp=root/'bindings'/(name+'_'+mesh_method+'.npz')
                    np.savez_compressed(bp,**bound,query_m=query,common_y_m=queries[subject],mesh_path=np.asarray(str(mesh_path)))
                    binding_rows.append(dict(subject=subject,role=role,split_seed=split_seed,strategy=trained['strategy'],
                        model_seed=trained['seed'],mesh_method=mesh_method,path=str(bp),sha256=sha(bp),mesh_path=str(mesh_path),
                        mesh_sha256=sha(mesh_path),curve_sha256=row['sha256'],projection_median_mm=float(np.median(bound['projection_distance_m'])*1000)))
        print('SUBJECT_COMPLETE',subject,flush=True)
    assert len(curve_rows)==360 and len(binding_rows)==1080
    write(root/'INPUT_MANIFEST.json',input_rows);write(root/'CURVE_MANIFEST.json',curve_rows);write(root/'BINDING_MANIFEST.json',binding_rows)
    for r in frozen:assert sha(r['path'])==r['sha256']
    write(root/'EXECUTION_LEDGER.json',dict(status='COMPLETE',subjects=20,inputs=60,curve_predictions=360,
        binding_packages=1080,engineering_points=9720,sam_inferences=0,new_mesh_fits=0,new_training=0,
        inference_seconds=time.monotonic()-start,heldout_input_intersection=0,source_assets_unchanged=True,
        clinical_accuracy_validated=False,feature_row_axis='-camera Y; output restored to original camera XY'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
