"""Frozen surface + separate provided references and unprovided point tests."""
import sys,time,argparse,platform,datetime,inspect
import numpy as np,scipy,trimesh
from common import ROOT,SOURCE,BASE,INPUT,QUERY,METHODS,CASES,read,write,sha
sys.path.insert(0,str(BASE/'delivery/code'))
from correspondence import binding,estimate
from frozen_geometry import probe
from metrics_v2 import ray_depth_residual

PARENT_COMMIT='08128e14f881805a316e642c1f120810c22c7772'
PARENT_MANIFEST_SHA='829abe21340d48fe9815d4b885f575689907e238f81d3400e7079533f82dfe84'

def prepare():
    assert sha(SOURCE/'reviewed_delivery/FILES_MANIFEST.json')==PARENT_MANIFEST_SHA
    assert read(SOURCE/'GIT_DELIVERY_RECEIPT.json')['commit']==PARENT_COMMIT
    assert read(SOURCE/'POST_EXECUTION_INTEGRITY.json')['status']=='PASS'
    old=read(SOURCE/'CONTRACT.json');records=read(SOURCE/'ATLAS.json')['records'];sources=list(read(SOURCE/'SOURCE_FREEZE.json'));cases=[];qa=[]
    write(ROOT/'CONTRACT.json',dict(id='REFERENCE_ASSISTED_CORRESPONDENCE_V1',frozen_before_results=True,
        parent_commit=PARENT_COMMIT,parent_manifest_sha256=PARENT_MANIFEST_SHA,subjects=old['subjects'],dev=old['dev'],
        input_indices=INPUT,query_indices=QUERY,methods=METHODS,cases=CASES,surface_source_method='D_VECTOR',
        noise_magnitude_m=.005,noise_seed_formula='20261004 + int(subject[1:]); same vectors in all error cases',
        algorithm='predicted graph-distance Gaussian RBF + constant, median input pair distance bandwidth, ridge 1e-6, full posterior closest triangle projection',
        ridge=1e-6,projection_face_count=2152,geometric_reference_is_oracle=True,
        new_sam_inferences=0,new_mesh_fits=0,training_runs=0,
        primary='4 unprovided query errors median per case -> source median within each error class; dev/consumed validation separate'))
    write(ROOT/'ATLAS.json',read(SOURCE/'ATLAS.json'));write(ROOT/'POSTERIOR_FACE_IDS.json',read(SOURCE/'POSTERIOR_FACE_IDS.json'))
    for subject in old['subjects']:
        ref=np.load(SOURCE/'reference'/subject/'reference.npz');P,_=probe(ref['vertices_m'],ref['faces'],records)
        z=np.load(SOURCE/'reference'/subject/'K0.npz');local=(P[INPUT]-z['camera_center_world_m'])@z['R_world_to_camera'].T
        ray,hit=ray_depth_residual(local,(ref['vertices_m']-z['camera_center_world_m'])@z['R_world_to_camera'].T,ref['faces'])
        visible=hit&(np.abs(ray)<1e-6)
        qa.append(dict(subject=subject,input_indices=INPUT,ray_hit=hit.tolist(),visible_first_surface=visible.tolist(),
            ray_residual_mm=[float(a*1000) if np.isfinite(a) else None for a in ray],oracle_inputs=True))
        rng=np.random.default_rng(20261004+int(subject[1:]));noise=rng.normal(size=(4,3));noise*=.005/np.linalg.norm(noise,axis=1,keepdims=True)
        for case in CASES:
            d=SOURCE/'runs'/subject/case;mesh=d/'D_VECTOR.npz';probes=d/'D_VECTOR_probes.npz';result=d/'results.json'
            expected=next(r['sha256'] for r in read(d/'ledger.json')['output_meshes'] if r['method']=='D_VECTOR');assert sha(mesh)==expected
            b=np.load(probes);assert np.allclose(b['reference_xyz_m'],P,atol=1e-12,rtol=0)
            inp=ROOT/'inputs'/subject/(case+'.npz');truth=ROOT/'evaluation_truth'/subject/(case+'.npz')
            inp.parent.mkdir(parents=True,exist_ok=True);truth.parent.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(inp,input_indices=np.asarray(INPUT),exact_xyz_m=P[INPUT],noise_m=noise,noisy_xyz_m=P[INPUT]+noise)
            np.savez_compressed(truth,reference_xyz_m=b['reference_xyz_m'],reference_normals=b['reference_normals'],query_indices=np.asarray(QUERY))
            cases.append(dict(subject=subject,case=case,mesh_path=str(mesh),mesh_sha256=sha(mesh),input_path=str(inp),truth_path=str(truth)))
            sources.extend(dict(path=str(p),sha256=sha(p)) for p in [mesh,probes,result,inp,truth])
        sources.extend(dict(path=str(p),sha256=sha(p)) for p in [SOURCE/'reference'/subject/'reference.npz',SOURCE/'reference'/subject/'K0.npz'])
    write(ROOT/'CASE_MANIFEST.json',cases)
    write(ROOT/'K0_REFERENCE_VISIBILITY_QA.json',dict(status='COMPLETE',rows=qa,visible=sum(sum(r['visible_first_surface']) for r in qa),
        total=80,case_selection_changed=False,all_inputs_oracle=True,not_sensor_annotation=True))
    write(ROOT/'EXECUTION_ENVIRONMENT.json',dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),python=sys.version,
        executable=sys.executable,platform=platform.platform(),numpy=np.__version__,scipy=scipy.__version__,trimesh=trimesh.__version__,
        device='CPU',workers=4,model_loads=0,new_mesh_fits=0,training_runs=0))
    for p in (ROOT/'code').glob('*.py'):sources.append(dict(path=str(p),sha256=sha(p)))
    for p in (BASE/'delivery/code').glob('*.py'):sources.append(dict(path=str(p),sha256=sha(p)))
    for p in [ROOT/'PROTOCOL.md',ROOT/'CONTRACT.json',ROOT/'ATLAS.json',ROOT/'POSTERIOR_FACE_IDS.json',ROOT/'CASE_MANIFEST.json',
        SOURCE/'SOURCE_FREEZE.json',SOURCE/'reviewed_delivery/FILES_MANIFEST.json',inspect.getfile(trimesh.triangles)]:
        sources.append(dict(path=str(p),sha256=sha(p)))
    unique={r['path']:r for r in sources};write(ROOT/'SOURCE_FREEZE.json',list(unique.values()))
    print('PREPARED',len(cases),'frozen',len(unique),'K0-visible',sum(sum(q['visible_first_surface']) for q in qa),'/80',flush=True)

def verify_freeze():
    rows=read(ROOT/'SOURCE_FREEZE.json')
    for r in rows:assert sha(r['path'])==r['sha256'],r['path']
    return len(rows)

def evaluate(result,truth,input_xyz):
    delta=result['xyz_m']-truth['reference_xyz_m'];normal=truth['reference_normals'];signed=np.sum(delta*normal,axis=1)
    euclidean=np.linalg.norm(delta,axis=1)*1000;tangent=np.linalg.norm(delta-signed[:,None]*normal,axis=1)*1000
    query=euclidean[QUERY];angle=np.degrees(np.arccos(np.clip(np.sum(result['normals']*normal,axis=1),-1,1)))
    return dict(query_median_mm=float(np.median(query)),query_p95_mm=float(np.percentile(query,95)),
        query_tangent_median_mm=float(np.median(tangent[QUERY])),query_normal_median_mm=float(np.median(np.abs(signed[QUERY])*1000)),
        query_normal_angle_median_deg=float(np.median(angle[QUERY])),per_probe_error_mm=euclidean.tolist(),
        per_probe_tangent_mm=tangent.tolist(),per_probe_normal_abs_mm=(np.abs(signed)*1000).tolist(),per_probe_normal_angle_deg=angle.tolist(),
        provided_reference_true_median_mm=float(np.median(euclidean[INPUT])),
        provided_input_fit_median_mm=float(np.median(np.linalg.norm(result['xyz_m'][INPUT]-input_xyz,axis=1)*1000)),
        projection_distance_median_mm=float(np.median(result['projection_distance_m'])*1000))

def run_subject(subject):
    records=read(ROOT/'ATLAS.json')['records'];ids=read(ROOT/'POSTERIOR_FACE_IDS.json')['face_ids'];cases=read(ROOT/'CASE_MANIFEST.json');ledgers=[]
    for row in [r for r in cases if r['subject']==subject]:
        start=time.time();case=row['case'];dest=ROOT/'runs'/subject/case;dest.mkdir(parents=True,exist_ok=False)
        z=np.load(row['mesh_path']);V=z['vertices_m'];F=z['faces'];assert sha(row['mesh_path'])==row['mesh_sha256']
        inputs=np.load(row['input_path']);assert np.array_equal(inputs['input_indices'],INPUT)
        P,N=probe(V,F,records)
        variants={'FIXED':(dict(xyz_m=P,face_id=np.asarray([r['face_id'] for r in records]),barycentric=np.asarray([r['barycentric'] for r in records]),
            normals=N,preprojection_xyz_m=P,projection_distance_m=np.zeros(8),interpolated_offset_m=np.zeros((8,3))),{})}
        # No evaluation truth is opened before all point estimators return.
        for m,key in [('REF4_EXACT','exact_xyz_m'),('REF4_NOISY5','noisy_xyz_m')]:
            variants[m]=estimate(V,F,records,INPUT,inputs[key],ids)
        truth=np.load(row['truth_path']);assert np.array_equal(truth['query_indices'],QUERY);results=[]
        for m,(result,info) in variants.items():
            assert np.isfinite(result['xyz_m']).all() and np.isin(result['face_id'],ids).all()
            reconstructed=np.sum(V[F[result['face_id']]]*result['barycentric'][:,:,None],axis=1)
            assert np.max(np.linalg.norm(reconstructed-result['xyz_m'],axis=1))<1e-9
            np.savez_compressed(dest/(m+'.npz'),**result,input_indices=np.asarray(INPUT),query_indices=np.asarray(QUERY))
            input_xyz=inputs['noisy_xyz_m' if m=='REF4_NOISY5' else 'exact_xyz_m']
            metric=evaluate(result,truth,input_xyz);results.append(dict(subject=subject,case=case,method=m,**metric,solver=info,
                source_surface_sha256=row['mesh_sha256'],surface_changed=False,
                changed_faces=int(np.sum(result['face_id']!=variants['FIXED'][0]['face_id']))))
        assert sha(row['mesh_path'])==row['mesh_sha256']
        write(dest/'results.json',results)
        ledger=dict(status='COMPLETE',subject=subject,case=case,seconds=time.time()-start,rbf_solves=2,new_mesh_fits=0,
            input_positions_used=4,unprovided_queries=4,query_identity_intersection=[],evaluation_truth_read_after_estimators=True,
            source_surface_sha256=row['mesh_sha256'],outputs=[dict(method=m,sha256=sha(dest/(m+'.npz'))) for m in METHODS])
        write(dest/'ledger.json',ledger);ledgers.append(ledger)
        print('CASE_COMPLETE',subject,case,'query medians',[round(r['query_median_mm'],3) for r in results],flush=True)
    write(ROOT/'ledger'/(subject+'.json'),ledgers)

def execute(phase,workers):
    from concurrent.futures import ProcessPoolExecutor,as_completed
    cfg=read(ROOT/'CONTRACT.json');verify_freeze();assert read(ROOT/'ANALYTIC_CHECK.json')['status']=='PASS'
    subjects=cfg['dev'] if phase=='dev' else [s for s in cfg['subjects'] if s not in cfg['dev']]
    if phase=='validation':assert read(ROOT/'DEV_GATE.json')['status']=='PASS'
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(run_subject,s) for s in subjects]):f.result()
    if phase=='dev':write(ROOT/'DEV_GATE.json',dict(status='PASS',cases=12,parameters_changed=0,gate='finite cached points, disjoint identities, normal execution path; no performance cutoff'))
    print('PHASE_COMPLETE',phase,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','dev','validation'],required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    prepare() if a.phase=='prepare' else execute(a.phase,a.workers)
