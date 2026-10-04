"""Read-only chart comparison, all-subject diagnostics and engineering target export."""
import argparse
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from run_chart import read, write, sha, DATA


def span(points):
    return np.max([np.linalg.norm(points[i]-points[j],axis=1) for i,j in [(0,1),(0,2),(1,2)]],axis=0)*1000


def main(root):
    cfg=read(root/'CONFIG.json')
    bindings=sum([read(root/f'BINDING_MANIFEST_{p}.json') for p in ['dev','test']],[])
    curves=sum([read(root/f'CURVE_MANIFEST_{p}.json') for p in ['dev','test']],[])
    topology=sum([read(root/f'TOPOLOGY_MANIFEST_{p}.json') for p in ['dev','test']],[])
    for r in bindings+curves+topology:assert sha(r['path'])==r['sha256']
    caches={r['path']:dict(np.load(r['path'])) for r in bindings+topology}
    models=[];individual=[];initialization=[];topology_stats=[]
    for subject in cfg['cohort']:
        role='dev' if subject in cfg['dev'] else 'consumed_test_role'
        for chart in cfg['chart_methods']:
            for strategy in ['NO_BLOCK_AUG','BLOCK_AUG']:
                for mesh in cfg['meshes']:
                    group=[r for r in bindings if r['subject']==subject and r['chart']==chart and r['strategy']==strategy and r['mesh_method']==mesh]
                    for seed in range(3):
                        chosen=sorted([r for r in group if r['model_seed']==seed],key=lambda r:r['split_seed'])
                        data=[caches[r['path']] for r in chosen]
                        b=span([r['xyz_m'] for r in data]);q=span([r['query_m'] for r in data])
                        models.append(dict(subject=subject,role=role,chart=chart,strategy=strategy,mesh_method=mesh,model_seed=seed,
                            bound_span_median_mm=float(np.median(b)),bound_center_span_median_mm=float(np.median(b[1::3])),
                            query_span_median_mm=float(np.median(q)),query_center_span_median_mm=float(np.median(q[1::3])),
                            bound_span_max_mm=float(b.max()),projection_median_mm=float(np.mean([r['projection_median_mm'] for r in chosen])),
                            clamped_fraction=float(np.mean([r['clamped_fraction'] for r in chosen]))))
                    selected=[r for r in models if all(r[k]==v for k,v in [('subject',subject),('chart',chart),('strategy',strategy),('mesh_method',mesh)])]
                    metrics=[k for k in selected[0] if k.endswith('_mm') or k=='clamped_fraction']
                    individual.append(dict(subject=subject,role=role,chart=chart,strategy=strategy,mesh_method=mesh,
                        **{k:float(np.mean([r[k] for r in selected])) for k in metrics}))
                    for split in range(3):
                        chosen=sorted([r for r in group if r['split_seed']==split],key=lambda r:r['model_seed'])
                        b=span([caches[r['path']]['xyz_m'] for r in chosen])
                        initialization.append(dict(subject=subject,role=role,chart=chart,strategy=strategy,mesh_method=mesh,split_seed=split,
                            initialization_bound_span_median_mm=float(np.median(b)),initialization_center_span_median_mm=float(np.median(b[1::3]))))
        for mesh in cfg['meshes']:
            chosen=sorted([r for r in topology if r['subject']==subject and r['mesh_method']==mesh],key=lambda r:r['split_seed'])
            b=span([caches[r['path']]['xyz_m'] for r in chosen])
            topology_stats.append(dict(subject=subject,role=role,mesh_method=mesh,bound_span_median_mm=float(np.median(b)),
                bound_center_span_median_mm=float(np.median(b[1::3])),medical_accuracy=False))
    aggregate=[]
    for role in ['dev','consumed_test_role']:
        for chart in cfg['chart_methods']:
            for strategy in ['NO_BLOCK_AUG','BLOCK_AUG']:
                for mesh in cfg['meshes']:
                    selected=[r for r in individual if all(r[k]==v for k,v in [('role',role),('chart',chart),('strategy',strategy),('mesh_method',mesh)])]
                    aggregate.append(dict(role=role,chart=chart,strategy=strategy,mesh_method=mesh,subjects=len(selected),
                        **{k:float(np.median([r[k] for r in selected])) for k in metrics}))
    init_agg=[]
    for r in aggregate:
        subjects=[];centers=[]
        for s in cfg['cohort']:
            selected=[x for x in initialization if x['subject']==s and all(x[k]==r[k] for k in ['role','chart','strategy','mesh_method'])]
            if selected:
                subjects.append(np.mean([x['initialization_bound_span_median_mm'] for x in selected]))
                centers.append(np.mean([x['initialization_center_span_median_mm'] for x in selected]))
        init_agg.append(dict(role=r['role'],chart=r['chart'],strategy=r['strategy'],mesh_method=r['mesh_method'],
            subjects=len(subjects),initialization_span_median_mm=float(np.median(subjects)),initialization_center_span_median_mm=float(np.median(centers))))
    write(root/'RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,per_subject=individual,per_model=models,
        initialization=initialization,initialization_aggregate=init_agg,topology=topology_stats,clinical_accuracy_validated=False,
        target_definition='27 body-local grid probes, NOT identical to previous 9 camera-Y probes',all_curves=len(curves),all_bindings=len(bindings),topology_bindings=len(topology)))
    with (root/'PER_SUBJECT_RESULTS.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=individual[0].keys());w.writeheader();w.writerows(individual)
    for directory in ['figures','private_rgb','targets']:(root/directory).mkdir(exist_ok=True)
    visual=[];exports=[]
    for subject in cfg['cohort']:
        with np.load(DATA/'inputs'/subject/'input.npz') as z:rgb=Image.fromarray(z['rgb']);K=z['K'].copy()
        canvas=Image.new('RGB',(rgb.width*3,rgb.height+70),'white');draw=ImageDraw.Draw(canvas)
        fig,axes=plt.subplots(2,3,figsize=(15,10))
        with np.load(DATA/'inputs'/subject/'input.npz') as z:p=z['points_m'][z['posterior_point_mask']]
        p=p[::max(1,len(p)//5000)]
        for row,strategy in enumerate(['NO_BLOCK_AUG','BLOCK_AUG']):
            for col,chart in enumerate(cfg['chart_methods']):
                ax=axes[row,col];ax.scatter(p[:,0]*1000,p[:,1]*1000,s=.4,color='lightgray')
                selected=[r for r in bindings if r['subject']==subject and r['strategy']==strategy and r['chart']==chart and r['mesh_method']=='RigidD']
                for r in selected:
                    z=caches[r['path']];center=z['xyz_m'][1::3];color=['orange','limegreen','magenta'][r['split_seed']]
                    ax.plot(center[:,0]*1000,center[:,1]*1000,color=color,ls=['-','--',':'][r['model_seed']],lw=1)
                    ax.scatter(z['xyz_m'][:,0]*1000,z['xyz_m'][:,1]*1000,c=color,s=6,alpha=.45)
                    if strategy=='BLOCK_AUG':
                        uv=center@K.T;uv=uv[:,:2]/uv[:,2,None]
                        pixels=[(float(x)+col*rgb.width,float(y)+70) for x,y in uv]
                        draw.line(pixels,fill=color,width=2)
                ax.invert_yaxis();ax.set_aspect('equal');ax.set_title(chart+' / '+strategy)
                ax.set_xlabel('Camera X / mm');ax.set_ylabel('Camera Y / mm')
                if row==1:
                    canvas.paste(rgb,(col*rgb.width,70))
                    # Paste precedes drawing below: redraw curves in RGB, not a blank canvas.
                    for r in selected:
                        center=caches[r['path']]['xyz_m'][1::3];uv=center@K.T;uv=uv[:,:2]/uv[:,2,None]
                        color=['orange','limegreen','magenta'][r['split_seed']]
                        draw.line([(float(x)+col*rgb.width,float(y)+70) for x,y in uv],fill=color,width=2)
                    draw.text((col*rgb.width+5,5),subject+' / '+chart,fill='black')
                    draw.text((col*rgb.width+5,25),'All augmented model and input seeds',fill='black')
                    draw.text((col*rgb.width+5,45),'Engineering reference, NOT acupoints',fill='black')
        fig.suptitle(subject+' / camera XY orthographic diagnostic, NOT perspective overlay\nColors=input split; styles=model seed; dots=27 engineering targets on unchanged RigidD')
        fig.tight_layout();gp=root/'figures'/f'{subject}.png';fig.savefig(gp,dpi=100);plt.close(fig)
        rp=root/'private_rgb'/f'{subject}.jpg';canvas.save(rp,quality=90)
        visual.append(dict(subject=subject,public_geometry_path=str(gp),sha256=sha(gp),private_rgb_path=str(rp),private_rgb_sha256=sha(rp)))
        selected=next(r for r in bindings if r['subject']==subject and r['chart']=='BODY_PRIOR_FIXED' and r['strategy']=='BLOCK_AUG' and r['model_seed']==0 and r['split_seed']==0 and r['mesh_method']=='RigidD')
        z=caches[selected['path']];points=[]
        for j in range(27):
            points.append(dict(id=f'ENG_U{j//3+1:02d}_V{j%3}',u=float(z['u'][j]),lateral_offset_m=float(z['v_offset_m'][j]),
                xyz_m=z['xyz_m'][j].tolist(),face_id=int(z['face_id'][j]),barycentric=z['barycentric'][j].tolist(),normal=z['normals'][j].tolist(),
                clamped=bool(z['clamped'][j])))
        path=root/'targets'/f'{subject}.json'
        write(path,dict(schema='ENGINEERING_SURFACE_TARGET_V1',subject=subject,coordinate_frame='camera_m',method='BODY_PRIOR_FIXED / BLOCK_AUG / model0 / input0 / RigidD',
            example_selection='first initialization and split; NOT selected by target results',source_binding_sha256=selected['sha256'],mesh_path=selected['mesh_path'],mesh_sha256=selected['mesh_sha256'],
            medical_label=False,robot_release=False,points=points))
        exports.append(dict(subject=subject,path=str(path),sha256=sha(path),points=27))
    write(root/'VISUALIZATION_MANIFEST.json',visual);write(root/'TARGET_EXPORT_MANIFEST.json',exports)
    for r in read(root/'SOURCE_FREEZE.json'):assert sha(r['path'])==r['sha256'],r['path']
    write(root/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',source_assets=len(read(root/'SOURCE_FREEZE.json')),source_unchanged=True,
        curves=len(curves),bindings=len(bindings),topology_bindings=len(topology),exported_targets=540,clinical_validation=False))
    print('ANALYSIS_COMPLETE',len(bindings),len(topology),flush=True)
    for r in aggregate:
        if r['role']=='consumed_test_role' and r['mesh_method']=='RigidD':print(r,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
