"""Verify actual MHR bindings; report stability rather than invented accuracy."""
import csv,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw
from run_interface import OUT,DATA,read,write,sha


def span(p):
    return np.max([np.linalg.norm(p[i]-p[j],axis=1) for i,j in [(0,1),(0,2),(1,2)]],axis=0)*1000


def main():
    cfg=read(OUT/'CONFIG.json');rows=read(OUT/'TARGET_MANIFEST.json');inputs=read(OUT/'INPUT_MANIFEST.json')
    caches={};meshes={};numeric=0;train_checked=0
    for r in inputs:
        assert sha(Path(r['path']))==r['sha256']
        with np.load(DATA/'inputs'/r['subject']/f'split_{r["split_seed"]}.npz') as s,np.load(r['path']) as z:
            assert np.isin(z['source_global_point_idx'],s['train_idx']).all()
            assert len(np.intersect1d(z['source_global_point_idx'],s['heldout_idx']))==0
            train_checked+=len(z['source_global_point_idx'])
    for r in rows:
        assert sha(Path(r['path']))==r['sha256'];z=dict(np.load(r['path']));caches[r['path']]=z
        if r['mesh_path'] not in meshes:
            assert sha(Path(r['mesh_path']))==r['mesh_sha256'];meshes[r['mesh_path']]=dict(np.load(r['mesh_path']))
        mesh=meshes[r['mesh_path']];v=mesh['vertices_m'];f=mesh['faces'];tri=v[f[z['face_id']]]
        xyz=np.sum(tri*z['barycentric'][:,:,None],1);n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.linalg.norm(n,axis=1,keepdims=True)
        assert np.allclose(xyz,z['xyz_m'],atol=1e-10);assert np.allclose(n,z['normals'],atol=1e-10)
        assert np.allclose(np.linalg.norm(z['query_m']-xyz,axis=1),z['projection_distance_m'],atol=1e-10)
        if r['method']!='TOPOLOGY':
            with np.load(r['input_path']) as p:assert np.isin(z['source_global_point_idx'],p['source_global_point_idx']).all()
        assert abs(np.median(z['projection_distance_m'])*1000-r['projection_median_mm'])<1e-8
        numeric+=5
    per=[];init=[];methods=['TOPOLOGY','BODY_NN','PAIR_GLOBAL','PAIR_LOCAL']
    for subject in cfg['cohort']:
        for mesh in cfg['meshes']:
            for method in methods:
                group=[r for r in rows if (r['subject'],r['mesh_method'],r['method'])==(subject,mesh,method)]
                stats=[]
                for seed in sorted({r['model_seed'] for r in group}):
                    triplet=sorted([r for r in group if r['model_seed']==seed],key=lambda r:r['split_seed'])
                    assert len(triplet)==3
                    stats.append(float(np.median(span([caches[r['path']]['xyz_m'] for r in triplet]))))
                per.append(dict(subject=subject,role=group[0]['role'],mesh_method=mesh,method=method,input_span_median_mm=float(np.mean(stats)),
                    projection_median_mm=float(np.mean([r['projection_median_mm'] for r in group])),offset_from_topology_median_mm=float(np.mean([r['offset_from_topology_median_mm'] for r in group]))))
                if method.startswith('PAIR'):
                    spreads=[]
                    for split in range(3):
                        t=sorted([r for r in group if r['split_seed']==split],key=lambda r:r['model_seed']);spreads.append(float(np.median(span([caches[r['path']]['xyz_m'] for r in t]))))
                    init.append(dict(subject=subject,mesh_method=mesh,method=method,initialization_span_median_mm=float(np.mean(spreads))))
    aggregate=[]
    for role in ['dev','consumed_test_role']:
        for mesh in cfg['meshes']:
            for method in methods:
                group=[r for r in per if (r['role'],r['mesh_method'],r['method'])==(role,mesh,method)]
                aggregate.append(dict(role=role,mesh_method=mesh,method=method,subjects=len(group),**{k:float(np.median([r[k] for r in group])) for k in ['input_span_median_mm','projection_median_mm','offset_from_topology_median_mm']}))
    write(OUT/'RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,per_subject=per,initialization=init,
        accuracy_ground_truth_available=False,default_method='TOPOLOGY',medical_label=False,robot_release=False,method_selection='experimental models NOT promoted'))
    with (OUT/'PER_SUBJECT_RESULTS.csv').open('w',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=per[0].keys());w.writeheader();w.writerows(per)
    for d in ['figures','private_rgb','mesh_reviews','exports']:(OUT/d).mkdir(exist_ok=True)
    visual=[];review=[]
    for subject in cfg['cohort']:
        fig,axes=plt.subplots(2,4,figsize=(16,8))
        with np.load(DATA/'inputs'/subject/'input.npz') as data:rgb=Image.fromarray(data['rgb']);K=data['K'].copy()
        canvas=Image.new('RGB',(rgb.width*4,rgb.height*2+100),'white');draw=ImageDraw.Draw(canvas)
        for row,mesh in enumerate(cfg['meshes']):
            mesh_rows=[r for r in rows if r['subject']==subject and r['mesh_method']==mesh]
            for split in range(3):
                r=next(r for r in mesh_rows if r['split_seed']==split);v=meshes[r['mesh_path']]['vertices_m'];f=meshes[r['mesh_path']]['faces']
                # Store only derived MHR posterior triangles needed to replay the targets.
                faceids=np.unique(np.concatenate([caches[x['path']]['face_id'] for x in mesh_rows if x['split_seed']==split]))
                p=OUT/'mesh_reviews'/f'{subject}_{split}_{mesh}.npz';np.savez_compressed(p,global_face_id=faceids,triangles_m=v[f[faceids]])
                review.append(dict(subject=subject,split_seed=split,mesh_method=mesh,path=str(p),sha256=sha(p),full_mesh_path=r['mesh_path'],full_mesh_sha256=r['mesh_sha256']))
            for col,method in enumerate(methods):
                ax=axes[row,col];canvas.paste(rgb,(col*rgb.width,row*rgb.height+100));group=[r for r in mesh_rows if r['method']==method]
                for r in group:
                    xyz=caches[r['path']]['xyz_m'];color=['orange','limegreen','magenta'][r['split_seed']];marker=['o','x','+'][max(0,r['model_seed'])]
                    ax.scatter(xyz[:,0]*1000,xyz[:,1]*1000,c=color,s=16,marker=marker,alpha=.7)
                    uv=xyz@K.T;uv=uv[:,:2]/uv[:,2,None]
                    for x,y in uv:
                        x+=col*rgb.width;y+=row*rgb.height+100;draw.ellipse((x-3,y-3,x+3,y+3),outline=color,width=2)
                ax.invert_yaxis();ax.set_aspect('equal');ax.set_title(mesh+' / '+method);ax.set_xlabel('Camera X / mm');ax.set_ylabel('Camera Y / mm')
                draw.text((col*rgb.width+5,row*rgb.height+105),mesh+' / '+method,fill='red')
        draw.text((5,5),subject+' / all input splits and model seeds',fill='black');draw.text((5,25),'8 ENGINEERING queries, NOT medical acupoints',fill='black');draw.text((5,45),'RGB projection uses historical reconstructed camera, NOT calibration validation',fill='black')
        fig.suptitle(subject+' / eight fixed template queries; XY orthographic diagnostic, NOT perspective\nColors=input splits; markers=model seed; default=TOPOLOGY');fig.tight_layout()
        gp=OUT/'figures'/f'{subject}.png';fig.savefig(gp,dpi=100);plt.close(fig);rp=OUT/'private_rgb'/f'{subject}.jpg';canvas.save(rp,quality=88)
        visual.append(dict(subject=subject,geometry_path=str(gp),geometry_sha256=sha(gp),private_rgb_path=str(rp),private_rgb_sha256=sha(rp)))
        for method,seed in [('TOPOLOGY',-1),('PAIR_GLOBAL',0)]:
            r=next(x for x in rows if (x['subject'],x['split_seed'],x['mesh_method'],x['method'],x['model_seed'])==(subject,0,'RigidD',method,seed));z=caches[r['path']]
            write(OUT/'exports'/f'{subject}_{method}.json',dict(schema='ENGINEERING_MHR_QUERY_V1',subject=subject,method=method,coordinate_frame='historical reconstructed camera_m',
                mesh_path=r['mesh_path'],mesh_sha256=r['mesh_sha256'],binding_sha256=r['sha256'],medical_label=False,robot_release=False,visibility_known=False,
                default=method=='TOPOLOGY',points=[dict(id=cfg['source_query_ids'][j],xyz_m=z['xyz_m'][j].tolist(),face_id=int(z['face_id'][j]),barycentric=z['barycentric'][j].tolist(),normal=z['normals'][j].tolist()) for j in range(len(z['xyz_m']))]))
    write(OUT/'MESH_REVIEW_MANIFEST.json',review);write(OUT/'VISUALIZATION_MANIFEST.json',visual)
    for r in read(OUT/'SOURCE_FREEZE.json'):assert sha(Path(r['path']))==r['sha256']
    write(OUT/'CACHE_REPLAY.json',dict(status='PASS',actual_target_caches=len(rows),actual_meshes=len(meshes),numeric_checks=numeric,
        train_only_points_checked=train_checked,heldout_intersection=0,source_unchanged=True,medical_accuracy=False))
    print('INTERFACE_ANALYSIS_COMPLETE',len(rows),numeric,flush=True)
    for r in aggregate:
        if r['role']=='consumed_test_role' and r['mesh_method']=='RigidD':print(r,flush=True)


if __name__=='__main__':main()
