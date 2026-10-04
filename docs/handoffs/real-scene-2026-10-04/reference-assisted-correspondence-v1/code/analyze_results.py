"""All-case analysis and images from cached point estimates, no refitting."""
import sys,csv,time
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageOps
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT,SOURCE,BASE,INPUT,QUERY,METHODS,CASES,read,write,sha
sys.path.insert(0,str(BASE/'delivery/code'))
from frozen_geometry import local,project,probe
from run_references import verify_freeze,evaluate

def csv_write(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def render_case(subject,case):
    z=np.load(SOURCE/'runs'/subject/case/'D_VECTOR.npz');V=z['vertices_m'];F=z['faces']
    truth=np.load(ROOT/'evaluation_truth'/subject/(case+'.npz'));inputs=np.load(ROOT/'inputs'/subject/(case+'.npz'))
    results=read(ROOT/'runs'/subject/case/'results.json');fixed=np.load(ROOT/'runs'/subject/case/'FIXED.npz')
    page=Image.new('RGB',(1200,1500),'white');draw=ImageDraw.Draw(page)
    for k in [0,1,2]:
        camera=np.load(SOURCE/'reference'/subject/f'K{k}.npz');R=camera['R_world_to_camera'];C=camera['camera_center_world_m'];K=camera['K']
        uv=project(local(V,R,C),K);mask=np.zeros((960,640),np.uint8)
        for t in np.rint(uv[F]).astype(np.int32):cv2.fillConvexPoly(mask,t,1)
        gt=project(local(truth['reference_xyz_m'],R,C),K);base=project(local(fixed['xyz_m'],R,C),K)
        bounds=np.vstack([gt,base]);lo=np.floor(bounds.min(0)-45).astype(int);hi=np.ceil(bounds.max(0)+45).astype(int)
        lo=np.maximum(lo,[0,0]);hi=np.minimum(hi,[640,960]);box=(int(lo[0]),int(lo[1]),int(hi[0]),int(hi[1]))
        for col,m in enumerate(METHODS):
            output=np.load(ROOT/'runs'/subject/case/(m+'.npz'));pred=project(local(output['xyz_m'],R,C),K)
            given=project(local(inputs['noisy_xyz_m' if m=='REF4_NOISY5' else 'exact_xyz_m'],R,C),K)
            img=np.full((960,640,3),255,np.uint8);img[mask.astype(bool)]=(215,195,210)
            for i in QUERY:
                a=tuple(np.rint(gt[i]).astype(int));b=tuple(np.rint(pred[i]).astype(int))
                cv2.arrowedLine(img,a,b,(0,0,0),1,tipLength=.25);cv2.circle(img,a,3,(30,100,245),-1);cv2.circle(img,b,2,(245,55,45),-1)
            for p in given:cv2.drawMarker(img,tuple(np.rint(p).astype(int)),(230,150,0),cv2.MARKER_TILTED_CROSS,8,1)
            cropped=ImageOps.contain(Image.fromarray(img).crop(box),(390,390));x=col*400;y=k*500
            page.paste(cropped,(x+(400-cropped.width)//2,y+100+(390-cropped.height)//2))
            rr=next(r for r in results if r['method']==m)
            draw.text((x+5,y+5),f'{subject} {case} K{k} / {m}',fill='black')
            draw.text((x+5,y+24),f"4 unprovided-point median {rr['query_median_mm']:.3f} mm",fill='black')
            draw.text((x+5,y+43),'Same frozen surface in all columns',fill='black')
            draw.text((x+5,y+62),'Blue query truth / red output / orange given refs',fill='black')
            draw.text((x+5,y+81),'FIXED does not use refs; shown for comparison',fill='black')
    p=ROOT/'figures'/f'{subject}_{case}.jpg';p.parent.mkdir(exist_ok=True);page.save(p,quality=93)
    return dict(subject=subject,case=case,path=str(p),sha256=sha(p),source_mesh_sha256=sha(SOURCE/'runs'/subject/case/'D_VECTOR.npz'),
        input_point_cache_hashes=[dict(method=m,sha256=sha(ROOT/'runs'/subject/case/(m+'.npz'))) for m in METHODS],
        crop='reference/fixed projected bindings +45px, common across methods; visualization only; aspect ratio preserved')

def main():
    started=time.time();cfg=read(ROOT/'CONTRACT.json');records=read(ROOT/'ATLAS.json')['records'];flat=[];points=[];all_rows=[];outputs=[];baseline=[]
    for item in read(ROOT/'CASE_MANIFEST.json'):
        subject=item['subject'];case=item['case'];d=ROOT/'runs'/subject/case;rows=read(d/'results.json');ledger=read(d/'ledger.json')
        assert ledger['status']=='COMPLETE' and sha(item['mesh_path'])==item['mesh_sha256']
        truth=np.load(item['truth_path']);inputs=np.load(item['input_path']);old=np.load(SOURCE/'runs'/subject/case/'D_VECTOR_probes.npz')
        for row in rows:
            method=row['method'];path=d/(method+'.npz');z=np.load(path);expected=next(r['sha256'] for r in ledger['outputs'] if r['method']==method)
            assert sha(path)==expected and not set(z['input_indices'])&set(z['query_indices'])
            metric=evaluate(z,truth,inputs['noisy_xyz_m' if method=='REF4_NOISY5' else 'exact_xyz_m'])
            for key,value in metric.items():np.testing.assert_allclose(value,row[key],rtol=0,atol=1e-10)
            if method=='FIXED':
                assert np.array_equal(z['xyz_m'],old['xyz_m']);baseline.append(dict(subject=subject,case=case,status='EXACT_OLD_BINDING'))
            all_rows.append(row);outputs.append(dict(subject=subject,case=case,method=method,path=str(path),sha256=sha(path)))
            flat.append(dict(subject=subject,role='dev' if subject in cfg['dev'] else 'validation_consumed',case=case,method=method,
                **{k:row[k] for k in ['query_median_mm','query_p95_mm','query_tangent_median_mm','query_normal_median_mm',
                    'query_normal_angle_median_deg','provided_reference_true_median_mm','provided_input_fit_median_mm','projection_distance_median_mm','changed_faces']}))
            for i,p in enumerate(records):
                points.append(dict(subject=subject,role=flat[-1]['role'],case=case,method=method,probe_id=p['id'],
                    provided_reference=i in INPUT,error_mm=row['per_probe_error_mm'][i],tangent_mm=row['per_probe_tangent_mm'][i],
                    normal_abs_mm=row['per_probe_normal_abs_mm'][i],normal_angle_deg=row['per_probe_normal_angle_deg'][i]))
    summaries=[];pairs=[]
    for role in ['dev','validation_consumed']:
        for case in CASES:
            for method in METHODS:
                rows=[r for r in flat if r['role']==role and r['case']==case and r['method']==method]
                summaries.append(dict(role=role,case=case,method=method,sources=len(rows),
                    **{k:float(np.median([r[k] for r in rows])) for k in flat[0] if k not in ['subject','role','case','method']}))
    for subject in cfg['subjects']:
        for case in CASES:
            rows={r['method']:r for r in flat if r['subject']==subject and r['case']==case}
            for method in METHODS[1:]:pairs.append(dict(subject=subject,role=rows[method]['role'],case=case,method=method,
                query_change_vs_fixed_mm=rows[method]['query_median_mm']-rows['FIXED']['query_median_mm']))
    assert len(flat)==180 and len(points)==1440 and sum(not p['provided_reference'] for p in points)==720
    write(ROOT/'ALL_RESULTS.json',all_rows);write(ROOT/'AGGREGATED_RESULTS.json',dict(summaries=summaries,paired_changes=pairs,
        input_indices=INPUT,query_indices=QUERY,medical_accuracy=False,surface_geometry_changed=False))
    csv_write(ROOT/'PER_CASE_RESULTS.csv',flat);csv_write(ROOT/'PER_PROBE_RESULTS.csv',points);csv_write(ROOT/'PAIRED_CHANGES.csv',pairs)
    write(ROOT/'FINAL_POINT_CACHE_MANIFEST.json',outputs)
    # Geometry metrics are inherited without touching any vertices/held-out points.
    surface=[]
    for item in read(ROOT/'CASE_MANIFEST.json'):
        old=next(r for r in read(SOURCE/'runs'/item['subject']/item['case']/'results.json') if r['method']=='D_VECTOR')
        surface.append(dict(subject=item['subject'],case=item['case'],source_surface_sha256=item['mesh_sha256'],
            common_to_all_new_methods=True,inherited_K1_K2=old['cameras'],new_evaluation=False))
    write(ROOT/'FIXED_SURFACE_METRICS.json',surface)
    from concurrent.futures import ProcessPoolExecutor,as_completed
    visuals=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(render_case,s,c) for s in cfg['subjects'] for c in CASES]):visuals.append(f.result())
    visuals.sort(key=lambda r:(r['subject'],r['case']));write(ROOT/'VISUALIZATION_MANIFEST.json',visuals)
    fig,axes=plt.subplots(1,3,figsize=(16,5))
    for col,case in enumerate(CASES):
        for m in METHODS:
            rs=[next(r for r in flat if r['subject']==s and r['case']==case and r['method']==m) for s in cfg['subjects']]
            axes[col].plot(np.arange(20),[r['query_median_mm'] for r in rs],'o-',ms=3,label=m)
        axes[col].set_title(case);axes[col].set_ylabel('4 unprovided engineering points median (mm)')
        axes[col].set_xticks(np.arange(20),cfg['subjects'],rotation=90,fontsize=7);axes[col].legend(fontsize=7)
    fig.suptitle('Same fixed surface / 4 oracle references / 4 disjoint queries / controlled geometry only');fig.tight_layout()
    fig.savefig(ROOT/'figures/ALL_CASE_COMPARISON.png',dpi=140);plt.close(fig)
    count=verify_freeze();write(ROOT/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',frozen_sources_verified=count,
        fixed_surfaces_verified=60,point_caches_verified=180,all_numeric_results_recomputed=180,
        baseline_exact_replay=baseline,input_query_intersection=[],query_truth_read_only_after_estimators=True,
        model_loads=0,new_mesh_fits=0))
    write(ROOT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',sources=20,cases=60,point_method_outputs=180,point_rows=1440,
        unprovided_query_rows=720,rbf_solves=120,new_sam_inferences=0,new_mesh_fits=0,training_runs=0,
        generated_pages=len(visuals),analysis_seconds=time.time()-started,oracle_reference_accuracy_only=True))
    print('ANALYSIS_COMPLETE',len(flat),len(visuals),flush=True)
    for r in summaries:
        if r['role']=='validation_consumed':print(r,flush=True)

if __name__=='__main__':main()
