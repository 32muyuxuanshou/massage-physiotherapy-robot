"""Read final cache: surface vs known correspondence, all-case plots and integrity."""
import sys,csv,time
from pathlib import Path
import numpy as np,cv2
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT,BASE,PREV,METHODS,CASES,read,write,sha
sys.path[:0]=[str(BASE/'delivery/code'),str(PREV/'code')]
from geometry import local,project,probe
from surface_metrics import point_to_triangle_distances
from metrics_v2 import ray_depth_residual

def picture(V,F,K,height,width):
    # Display only: triangle union silhouette; does not stand in for the exact
    # first-layer raster or continuous ray evaluator used for geometry.
    uv=np.rint(project(V,K)).astype(np.int32);mask=np.zeros((height,width),np.uint8)
    for tri in uv[F]:cv2.fillConvexPoly(mask,tri,1)
    return mask.astype(bool)

def render_case(subject,case):
    path=ROOT/'runs'/subject/case;records=read(ROOT/'ATLAS.json')['records'];rows=read(path/'results.json')
    page=Image.new('RGB',(4*320,3*(480+75)),'white');draw=ImageDraw.Draw(page)
    meshes={m:np.load(path/(m+'.npz')) for m in METHODS};probes={m:np.load(path/(m+'_probes.npz')) for m in METHODS}
    for k in [0,1,2]:
        obs=np.load(ROOT/'reference'/subject/f'K{k}.npz');R=obs['R_world_to_camera'];C=obs['camera_center_world_m']
        K=obs['K'].copy();K[:2]/=2;truth_mask=obs['depth_m'][::2,::2]>0
        for col,m in enumerate(METHODS):
            z=meshes[m];V=local(z['vertices_m'],R,C);mask=picture(V,z['faces'],K,480,320)
            img=np.full((480,320,3),255,np.uint8);img[truth_mask]=(210,210,210)
            img[mask]=np.clip(.5*img[mask]+.5*np.array([235,110,185]),0,255).astype(np.uint8)
            contour,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(img,contour,-1,(30,160,60),1)
            pred=project(local(probes[m]['xyz_m'],R,C),K);gt=project(local(probes[m]['reference_xyz_m'],R,C),K)
            for a,b in zip(gt,pred):
                a=tuple(np.rint(a).astype(int));b=tuple(np.rint(b).astype(int))
                cv2.arrowedLine(img,a,b,(0,0,0),1,tipLength=.3);cv2.circle(img,a,3,(30,100,245),-1);cv2.circle(img,b,2,(245,65,40),-1)
            x=col*320;y=k*555;page.paste(Image.fromarray(img),(x,y+75));rr=next(r for r in rows if r['method']==m)
            draw.text((x+4,y+3),f'{subject} {case} K{k} / {m}',fill='black')
            draw.text((x+4,y+20),f"8-point error med {rr['known_probe_error']['median_mm']:.2f} mm",fill='black')
            if k:
                cr=next(c for c in rr['cameras'] if c['camera']==k)
                draw.text((x+4,y+37),f"Back surface med {cr['posterior']['median_mm']:.2f} mm",fill='black')
            else:draw.text((x+4,y+37),'K0 optimizer view; K1/K2 heldout',fill='black')
            draw.text((x+4,y+54),'Blue: known ENG / red: predicted ENG',fill='black')
    file=ROOT/'figures'/f'{subject}_{case}.jpg';file.parent.mkdir(exist_ok=True);page.save(file,quality=93)
    return dict(subject=subject,case=case,path=str(file),sha256=sha(file),
        input_meshes=[dict(method=m,sha256=sha(path/(m+'.npz'))) for m in METHODS],
        visual_geometry='half-resolution projected triangle union; no depth residual from image; exact geometry metrics separate')

def csv_write(path,rows):
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def integrity():
    sources=read(ROOT/'SOURCE_FREEZE.json')
    for r in sources:assert sha(r['path'])==r['sha256'],r['path']
    cfg=read(ROOT/'CONTRACT.json');refs=read(ROOT/'REFERENCE_MANIFEST.json');rows=[];recomputed=[]
    for record in refs:
        subject=record['subject'];ref_dir=ROOT/'reference'/subject
        assert sha(ref_dir/'reference.npz')==record['reference_sha256']
        for view in record['views']:assert sha(ref_dir/f"K{view['camera']}.npz")==view['sha256']
        for case in CASES:
            d=ROOT/'runs'/subject/case;ledger=read(d/'ledger.json');assert ledger['status']=='COMPLETE'
            obs0=np.load(ref_dir/'K0.npz')
            for entry in ledger['output_meshes']:
                path=d/(entry['method']+'.npz');assert sha(path)==entry['sha256']
                z=np.load(path);assert np.array_equal(z['actual_K0_optimization_point_idx'],obs0['optimization_idx'])
                assert np.isfinite(z['vertices_m']).all();rows.append(dict(subject=subject,case=case,method=entry['method'],path=str(path),sha256=sha(path)))
            if subject in cfg['dev'] and case=='TANGENTIAL_SHIFT':
                z=np.load(d/'D_NORMAL.npz');ob=np.load(ref_dir/'K1.npz');ev=ob['posterior_eval_idx']
                ids=np.asarray(read(ROOT/'POSTERIOR_FACE_IDS.json')['face_ids'],int)
                saved=np.load(d/'D_NORMAL_K1_metrics.npz')
                dist=point_to_triangle_distances(ob['points_world_m'][ev],z['vertices_m'],z['faces'][ids])
                ray,hit=ray_depth_residual(ob['points_m'][ev],local(z['vertices_m'],ob['R_world_to_camera'],ob['camera_center_world_m']),z['faces'])
                assert np.array_equal(dist,saved['point_to_surface_m']) and np.array_equal(ray,saved['ray_z_residual_m'],equal_nan=True)
                assert np.array_equal(hit,saved['ray_hit'])
                recomputed.append(dict(subject=subject,case=case,method='D_NORMAL',camera='K1',status='EXACT_RECOMPUTATION'))
    assert len(rows)==240 and len(recomputed)==4
    write(ROOT/'FINAL_MESH_MANIFEST.json',rows)
    write(ROOT/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',sources_checked=len(sources),reference_meshes_checked=20,
        observation_files_checked=60,final_meshes_checked=240,independent_cache_recomputations=recomputed,
        K0_only_optimization=True,new_inferences=0,training_runs=0))

def main():
    start=time.time();write(ROOT/'ANALYSIS_CODE_IDENTITY.json',dict(status='RECORDED_BEFORE_ANALYSIS',path=str(Path(__file__)),sha256=sha(Path(__file__))))
    cfg=read(ROOT/'CONTRACT.json');all_rows=[];flat=[];oracle=[];ids=np.asarray(read(ROOT/'POSTERIOR_FACE_IDS.json')['face_ids'],int)
    for subject in cfg['subjects']:
        ref=np.load(ROOT/'reference'/subject/'reference.npz')
        for k in [1,2]:
            ob=np.load(ROOT/'reference'/subject/f'K{k}.npz');ev=ob['posterior_eval_idx']
            d=point_to_triangle_distances(ob['points_world_m'][ev],ref['vertices_m'],ref['faces'][ids]);assert d.max()<1e-9
            oracle.append(dict(subject=subject,camera=k,max_surface_error_mm=float(d.max()*1000),points=len(d)))
        for case in CASES:
            rows=read(ROOT/'runs'/subject/case/'results.json');all_rows.extend(rows)
            for r in rows:
                flat.append(dict(subject=subject,role='dev' if subject in cfg['dev'] else 'validation_consumed',case=case,method=r['method'],
                    surface_median_mm=float(np.median([c['posterior']['median_mm'] for c in r['cameras']])),
                    surface_p95_mm=float(np.median([c['posterior']['p95_mm'] for c in r['cameras']])),
                    ray_hit_fraction=float(np.median([c['hit_fraction'] for c in r['cameras']])),
                    common_ray_median_mm=float(np.median([c['common_ray']['median_mm'] for c in r['cameras']])),
                    known_probe_median_mm=r['known_probe_error']['median_mm'],known_probe_p95_mm=r['known_probe_error']['p95_mm'],
                    known_probe_tangent_median_mm=r['probe_tangent_error']['median_mm'],known_probe_normal_median_mm=r['probe_normal_error']['median_mm'],
                    edge_strain_p99=r['mesh_quality_against_reference']['edge_strain_p99'],
                    face_normal_reversal_fraction=r['mesh_quality_against_reference']['face_flip_frac']))
    summaries=[];pairs=[]
    excluded=['subject','role','case','method'];fields=[k for k in flat[0] if k not in excluded]
    for role in ['dev','validation_consumed']:
        for case in CASES:
            for method in METHODS:
                subset=[r for r in flat if r['role']==role and r['case']==case and r['method']==method]
                summaries.append(dict(role=role,case=case,method=method,sources=len(subset),**{k:float(np.median([r[k] for r in subset])) for k in fields}))
    for subject in cfg['subjects']:
        for case in CASES:
            rs={r['method']:r for r in flat if r['subject']==subject and r['case']==case}
            for method in ['D_VECTOR','D_NORMAL']:
                pairs.append(dict(subject=subject,role=rs[method]['role'],case=case,method=method,
                    surface_change_vs_rigid_mm=rs[method]['surface_median_mm']-rs['RIGID']['surface_median_mm'],
                    known_probe_change_vs_rigid_mm=rs[method]['known_probe_median_mm']-rs['RIGID']['known_probe_median_mm']))
    assert len(all_rows)==240 and len(flat)==240
    write(ROOT/'ALL_RESULTS.json',all_rows);write(ROOT/'AGGREGATED_RESULTS.json',dict(status='COMPLETE',role_case_method_summary=summaries,
        per_source_case=flat,paired_changes=pairs,real_world_accuracy=False,known_correspondence_is_engineering_not_medical=True))
    write(ROOT/'REFERENCE_SURFACE_ORACLE_QA.json',dict(status='PASS',rows=oracle));csv_write(ROOT/'PER_SOURCE_CASE_RESULTS.csv',flat);csv_write(ROOT/'PAIRED_CHANGES.csv',pairs)
    from concurrent.futures import ProcessPoolExecutor,as_completed
    visuals=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(render_case,s,c) for s in cfg['subjects'] for c in CASES]):visuals.append(f.result())
    visuals.sort(key=lambda r:(r['subject'],r['case']));write(ROOT/'VISUALIZATION_MANIFEST.json',visuals)
    fig,axes=plt.subplots(2,3,figsize=(16,9))
    for col,case in enumerate(CASES):
        for m in METHODS[1:]:
            rs=[next(r for r in flat if r['subject']==s and r['case']==case and r['method']==m) for s in cfg['subjects']]
            axes[0,col].plot(np.arange(20),[r['surface_median_mm'] for r in rs],'o-',ms=3,label=m)
            axes[1,col].plot(np.arange(20),[r['known_probe_median_mm'] for r in rs],'o-',ms=3,label=m)
        axes[0,col].set_title(case);axes[0,col].set_ylabel('K1/K2 posterior surface distance (mm)')
        axes[1,col].set_ylabel('Known ENG correspondence error (mm)')
        for ax in axes[:,col]:ax.set_xticks(np.arange(20),cfg['subjects'],rotation=90,fontsize=7);ax.legend(fontsize=7)
    fig.suptitle('Controlled geometry only / exact virtual cameras / not real sensor or acupoint accuracy');fig.tight_layout();fig.savefig(ROOT/'figures/ALL_CASE_COMPARISON.png',dpi=130);plt.close(fig)
    plane=np.load(ROOT/'planar_witness.npz');target=plane['target_probe_m'];face=plane['probe_face'];b=plane['probe_barycentric']
    shifted=(plane['initial_vertices_m'][face]*b[:,None]).sum(0)
    fig,ax=plt.subplots(figsize=(7,5));ax.scatter(plane['observed_points_m'][::12,0]*1000,plane['observed_points_m'][::12,1]*1000,s=3,c='gray',label='observed planar patch: same Z')
    ax.scatter(target[0]*1000,target[1]*1000,c='blue',label='known binding');ax.scatter(shifted[0]*1000,shifted[1]*1000,c='red',label='shifted same binding')
    ax.annotate('',xy=shifted[:2]*1000,xytext=target[:2]*1000,arrowprops=dict(arrowstyle='->',color='black'))
    ax.set_aspect('equal');ax.set_xlabel('X (mm)');ax.set_ylabel('Y (mm)');ax.set_title('Surface/depth error ~0; topology-bound point error 20 mm');ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures/PLANAR_BINDING_WITNESS.png',dpi=150);plt.close(fig)
    integrity();write(ROOT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',source_geometries=20,controlled_cases=60,final_meshes=240,
        rigid_fits=60,vector_fits=60,normal_fits=60,new_sam_inferences=0,training_runs=0,synthetic_observation_views=60,
        analysis_seconds=time.time()-start,generated_comparison_pages=len(visuals),posterior_face_count=len(ids),
        source_pre_post=read(ROOT/'POST_EXECUTION_INTEGRITY.json'),runtime_root=str(ROOT),independent_real_patient_accuracy=False))
    print('ANALYSIS_COMPLETE',len(flat),len(visuals),flush=True)
    for r in summaries:
        if r['role']=='validation_consumed':print(r,flush=True)

if __name__=='__main__':main()
