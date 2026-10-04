"""Frozen MHR-guided input charts and 27 engineering surface queries; no Mesh fitting."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.spatial import cKDTree
from trimesh.triangles import closest_point

DATA = Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
OLD = Path('/raid5/xuhd/datasets/prone_learned_reference_transfer_v1_20261005')
PILOT = Path('/raid5/xuhd/datasets/surface_line_completion_pilot_v1_20261004')
ASSETS = Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003/assets')
sys.path.insert(0, str(PILOT / 'code'))
from data_line import features
from line_net import LineNet


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def project(query, vertices, faces, mask):
    ids = np.asarray(mask, int)
    tri = vertices[faces[ids]]
    n, m = len(query), len(tri)
    projected = closest_point(np.tile(tri, (n, 1, 1)), np.repeat(query, m, axis=0)).reshape(n, m, 3)
    k = np.argmin(np.sum((projected - query[:, None]) ** 2, axis=2), axis=1)
    xyz = projected[np.arange(n), k]
    chosen = tri[k]
    a, b, d = chosen[:, 1] - chosen[:, 0], chosen[:, 2] - chosen[:, 0], xyz - chosen[:, 0]
    aa, ab, bb = np.sum(a*a, 1), np.sum(a*b, 1), np.sum(b*b, 1)
    ad, bd = np.sum(a*d, 1), np.sum(b*d, 1)
    det = aa*bb-ab*ab
    u, v = (bb*ad-ab*bd)/det, (aa*bd-ab*ad)/det
    bary = np.column_stack([1-u-v, u, v])
    xyz = np.sum(chosen * bary[:, :, None], axis=1)
    normal = np.cross(a, b)
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    return dict(xyz_m=xyz, face_id=ids[k], barycentric=bary, normals=normal,
                query_m=query, projection_distance_m=np.linalg.norm(xyz-query, axis=1))


def body_frame(canonical, patient, face_ids, faces):
    ids = np.unique(faces[face_ids])
    c, p = canonical[ids], patient[ids]
    ymin, ymax = np.quantile(c[:, 1], [.2, .8])
    y = p[c[:, 1] >= ymax].mean(0) - p[c[:, 1] <= ymin].mean(0)
    y /= np.linalg.norm(y)
    xmin, xmax = np.quantile(c[:, 0], [.2, .8])
    x = p[c[:, 0] >= xmax].mean(0) - p[c[:, 0] <= xmin].mean(0)
    x -= np.dot(x, y)*y
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    z *= 1 if z[2] >= 0 else -1  # Feature-depth axis faces camera +Z, not anatomical laterality.
    axes = np.stack([x, y, z])
    assert np.max(np.abs(axes @ axes.T-np.eye(3))) < 1e-10
    origin = p.mean(0)
    local = (p-origin) @ axes.T
    return dict(origin_m=origin.tolist(), axes=axes.tolist(), prior_vertex_ids=ids.tolist(),
                local_extent_m=[local.min(0).tolist(), local.max(0).tolist()])


def extent(points):
    xlo, xhi = points[:, 0].min(), points[:, 0].max()
    ylo, yhi = np.quantile(points[:, 1], [.05, .95])
    dx, dy = .05*(xhi-xlo), .05*(yhi-ylo)
    return np.array([xlo-dx, xhi+dx]), np.array([ylo-dy, yhi+dy])


def query_grid(curve, frame, ytargets):
    axes, origin = np.asarray(frame['axes']), np.asarray(frame['origin_m'])
    local = (curve-origin) @ axes.T
    unique = np.unique(local[:, 1])
    mean = np.array([local[local[:, 1] == y].mean(0) for y in unique])
    centers = np.column_stack([np.interp(ytargets, unique, mean[:, j]) for j in range(3)])
    queries = np.repeat(centers, 3, axis=0)
    queries[:, 0] += np.tile([-.02, 0, .02], len(centers))
    clamped = (ytargets < unique.min()) | (ytargets > unique.max())
    return queries @ axes + origin, np.repeat(clamped, 3)


def prepare(root):
    config = read('/raid5/xuhd/datasets/prone_reference_mesh_interface_v1_20261004/CONFIG.json')
    mask = np.asarray(read(ASSETS/'candidate_posterior_mask.json')['face_ids'])
    canonical = np.load(ASSETS/'mhr_rest_vertices.npy') * .01
    faces = np.load(ASSETS/'mhr_faces.npy')
    source = [root/'PROTOCOL.md', *sorted((root/'code').glob('*.py')),
              ASSETS/'candidate_posterior_mask.json', ASSETS/'mhr_rest_vertices.npy', ASSETS/'mhr_faces.npy',
              OLD/'CURVE_MANIFEST.json', PILOT/'TRAINING_LEDGER.json', PILOT/'code/line_net.py', PILOT/'code/data_line.py']
    for row in read(PILOT/'TRAINING_LEDGER.json'):
        assert sha(row['checkpoint_path']) == row['checkpoint_sha256']
        source.append(Path(row['checkpoint_path']))
    for subject in config['cohort']:
        with np.load(DATA/'meshes'/subject/'seed_0/Official.npz') as z:
            assert len(z['optimization_point_idx']) == 0
            prior = z['vertices_m'].copy()
            assert np.array_equal(z['faces'], faces)
        f = body_frame(canonical, prior, mask, faces)
        ids = np.unique(faces[mask]);p = prior[ids]
        origin = np.asarray(f['origin_m']);axes = np.asarray(f['axes'])
        cam = np.diag([1., -1., 1.])
        f['bounds'] = {name: [x.tolist(), y.tolist()] for name, matrix in
                       [('CAM_PRIOR_FIXED', cam), ('BODY_PRIOR_FIXED', axes)]
                       for x, y in [extent((p-origin) @ matrix.T)]}
        local = (p-origin) @ axes.T
        ymin, ymax = np.quantile(local[:, 1], [.05, .95])
        f['u'] = np.linspace(.1, .9, 9).tolist()
        f['target_y_body_m'] = (ymax-np.asarray(f['u'])*(ymax-ymin)).tolist()
        f['lateral_offsets_m'] = [-.02, 0, .02]
        topology = np.zeros((27, 3))
        topology[:, 0] = np.tile([-.02, 0, .02], 9)
        topology[:, 1] = np.repeat(f['target_y_body_m'], 3)
        topology[:, 2] = np.median(local[:, 2])
        target = project(topology @ axes+origin, prior, faces, mask)
        np.savez_compressed(root/'frames'/f'{subject}_topology.npz', **target)
        f['prior_mesh_sha256'] = sha(DATA/'meshes'/subject/'seed_0/Official.npz')
        f['topology_target_sha256'] = sha(root/'frames'/f'{subject}_topology.npz')
        write(root/'frames'/f'{subject}.json', f)
        source.extend([DATA/'inputs'/subject/'input.npz',root/'frames'/f'{subject}.json',root/'frames'/f'{subject}_topology.npz'])
        for seed in range(3):
            source.append(DATA/'inputs'/subject/f'split_{seed}.npz')
            source.extend(DATA/'meshes'/subject/f'seed_{seed}'/(stem+'.npz') for stem in config['meshes'].values())
    source.extend(Path(r['path']) for r in read(OLD/'CURVE_MANIFEST.json'))
    write(root/'CONFIG.json', dict(**config, chart_methods=['CAM_DYN','CAM_PRIOR_FIXED','BODY_PRIOR_FIXED'],
                                  points_per_binding=27, bounds_margin_fraction=.05, reference_labels=False))
    source.append(root/'CONFIG.json')
    write(root/'SOURCE_FREEZE.json',[dict(path=str(p),sha256=sha(p)) for p in source])
    print('PREPARED',len(config['cohort']),len(source),flush=True)


def run(root, phase):
    start=time.monotonic();torch.set_num_threads(4)
    cfg=read(root/'CONFIG.json');mask=np.asarray(read(ASSETS/'candidate_posterior_mask.json')['face_ids'])
    for row in read(root/'SOURCE_FREEZE.json'):assert sha(row['path'])==row['sha256'],row['path']
    subjects=cfg['dev'] if phase=='dev' else [s for s in cfg['cohort'] if s not in cfg['dev']]
    if phase=='test':assert read(root/'DEV_GATE.json')['status']=='PASS'
    models=[]
    for trained in read(PILOT/'TRAINING_LEDGER.json'):
        model=LineNet().cuda();model.load_state_dict(torch.load(trained['checkpoint_path'],weights_only=True)['state_dict']);model.eval()
        models.append((trained,model))
    old=read(OLD/'CURVE_MANIFEST.json');curves=[];bindings=[];inputs=[];topology=[]
    for subject in subjects:
        role='dev' if subject in cfg['dev'] else 'consumed_test_role'
        frame=read(root/'frames'/f'{subject}.json');origin=np.asarray(frame['origin_m']);axes=np.asarray(frame['axes'])
        ytargets=np.asarray(frame['target_y_body_m'])
        with np.load(DATA/'inputs'/subject/'input.npz') as z:points=z['points_m'];posterior=z['posterior_point_mask']
        for split in range(3):
            with np.load(DATA/'inputs'/subject/f'split_{split}.npz') as z:train=z['train_idx'];held=z['heldout_idx']
            used=train[posterior[train]];assert len(np.intersect1d(used,held))==0
            observed=points[used];meshes={}
            for method,stem in cfg['meshes'].items():
                path=DATA/'meshes'/subject/f'seed_{split}'/(stem+'.npz')
                with np.load(path) as z:
                    assert np.isin(z['optimization_point_idx'],train).all()
                    meshes[method]=(z['vertices_m'].copy(),z['faces'].copy(),path)
            with np.load(root/'frames'/f'{subject}_topology.npz') as z:face=z['face_id'];bary=z['barycentric']
            for method,(v,f,mp) in meshes.items():
                tri=v[f[face]];normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal/=np.linalg.norm(normal,axis=1,keepdims=True)
                path=root/'topology'/f'{subject}_input{split}_{method}.npz'
                np.savez_compressed(path,xyz_m=np.sum(tri*bary[:,:,None],axis=1),face_id=face,barycentric=bary,normals=normal)
                topology.append(dict(subject=subject,role=role,split_seed=split,mesh_method=method,path=str(path),sha256=sha(path)))
            for chart in cfg['chart_methods']:
                if chart!='CAM_DYN':
                    matrix=np.diag([1.,-1.,1.]) if chart=='CAM_PRIOR_FIXED' else axes
                    native=(observed-origin)@matrix.T
                    xb,yb=frame['bounds'][chart];xs=np.linspace(*xb,128);ys=np.linspace(*yb,128)
                    tensor,valid=features(native,xs,ys)
                    ip=root/'inputs'/f'{subject}_input{split}_{chart}.npz'
                    np.savez_compressed(ip,features=tensor,valid=valid,xs_m=xs,ys_m=ys,extraction_point_idx=used,axes=matrix,origin_m=origin)
                    inputs.append(dict(subject=subject,split_seed=split,chart=chart,path=str(ip),sha256=sha(ip),valid_grid_fraction=float(valid.mean()),heldout_intersection=0))
                for trained,model in models:
                    if chart=='CAM_DYN':
                        row=next(r for r in old if r['subject']==subject and r['split_seed']==split and r['strategy']==trained['strategy'] and r['model_seed']==trained['seed'])
                        with np.load(row['path']) as z:curve=z['curve_m'].copy();indices=z['source_global_point_idx'].copy()
                        cr=dict(row,chart=chart,source_reused=True)
                    else:
                        with torch.no_grad():pred=(model(torch.as_tensor(tensor[None],device='cuda:0')).softmax(-1)*torch.as_tensor(xs,dtype=torch.float32,device='cuda:0')[None,None,:]).sum(-1)[0].cpu().numpy()
                        xy=np.column_stack([pred,ys]);distance,index=cKDTree(native[:,:2]).query(xy);indices=used[index];curve=points[indices]
                        cp=root/'curves'/f"{subject}_input{split}_{chart}_{trained['strategy']}_model{trained['seed']}.npz"
                        np.savez_compressed(cp,curve_m=curve,source_global_point_idx=indices,extraction_point_idx=used,query_xy_native_m=xy,xy_snap_distance_m=distance)
                        cr=dict(subject=subject,role=role,split_seed=split,chart=chart,strategy=trained['strategy'],model_seed=trained['seed'],path=str(cp),sha256=sha(cp),source_reused=False,supported_fraction_3mm=float(np.mean(distance<=.003)))
                    assert np.isin(indices,used).all()
                    curves.append(cr);query,clamped=query_grid(curve,frame,ytargets)
                    for method,(v,f,mp) in meshes.items():
                        bound=project(query,v,f,mask)
                        assert np.max(np.abs(bound['barycentric'].sum(1)-1))<1e-9
                        assert np.min(bound['barycentric'])>-1e-8
                        path=root/'bindings'/f"{subject}_input{split}_{chart}_{trained['strategy']}_model{trained['seed']}_{method}.npz"
                        np.savez_compressed(path,**bound,u=np.repeat(frame['u'],3),v_offset_m=np.tile([-.02,0,.02],9),clamped=clamped)
                        bindings.append(dict(subject=subject,role=role,split_seed=split,chart=chart,strategy=trained['strategy'],model_seed=trained['seed'],mesh_method=method,
                            path=str(path),sha256=sha(path),mesh_path=str(mp),mesh_sha256=sha(mp),clamped_fraction=float(clamped.mean()),projection_median_mm=float(np.median(bound['projection_distance_m'])*1000)))
        print('SUBJECT_COMPLETE',subject,len(curves),len(bindings),flush=True)
    for name,data in [('INPUT',inputs),('CURVE',curves),('BINDING',bindings),('TOPOLOGY',topology)]:write(root/f'{name}_MANIFEST_{phase}.json',data)
    write(root/f'EXECUTION_{phase}.json',dict(status='COMPLETE',seconds=time.monotonic()-start,subjects=len(subjects),curves=len(curves),bindings=len(bindings),
        topology_bindings=len(topology),new_training=0,new_sam=0,new_mesh_fits=0,heldout_input_intersection=0))
    if phase=='dev':write(root/'DEV_GATE.json',dict(status='PASS',gate='normal-path finite predictions, source membership and barycentric reconstruction; no performance cutoff',hyperparameters_changed=0))
    print('PHASE_COMPLETE',phase,round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--phase',choices=['prepare','dev','test'],required=True);a=parser.parse_args()
    for directory in ['frames','inputs','curves','bindings','topology']:(a.root/directory).mkdir(parents=True,exist_ok=True)
    prepare(a.root) if a.phase=='prepare' else run(a.root,a.phase)
