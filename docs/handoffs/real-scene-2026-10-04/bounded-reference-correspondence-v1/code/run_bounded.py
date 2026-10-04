"""Two new corresponding-point variants, original surfaces and tests unchanged."""
import argparse,csv,hashlib,json,shutil,sys,time
from pathlib import Path
import numpy as np
from convex_correspondence import PARENT,estimate
sys.path.insert(0,str(PARENT/'code'))
from run_references import evaluate,INPUT,QUERY
from correspondence import binding

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def csv_write(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(root):
    start=time.time();parent=read(PARENT/'CONTRACT.json');records=read(PARENT/'ATLAS.json')['records'];ids=read(PARENT/'POSTERIOR_FACE_IDS.json')['face_ids']
    cases=read(PARENT/'CASE_MANIFEST.json');files=[PARENT/'CONTRACT.json',PARENT/'ATLAS.json',PARENT/'POSTERIOR_FACE_IDS.json',PARENT/'CASE_MANIFEST.json',root/'PROTOCOL.md',*(root/'code').glob('*.py')]
    for r in cases:
        files.extend([Path(r['mesh_path']),Path(r['input_path']),Path(r['truth_path'])])
        source=PARENT/'runs'/r['subject']/r['case'];files.extend([source/'results.json',source/'FIXED.npz',source/'REF4_EXACT.npz',source/'REF4_NOISY5.npz'])
    files.extend([PARENT/'code/correspondence.py',PARENT/'code/run_references.py'])
    freeze=[dict(path=str(p),sha256=sha(p)) for p in files];write(root/'SOURCE_FREEZE.json',freeze)
    write(root/'CONTRACT.json',dict(id='BOUNDED_REFERENCE_CORRESPONDENCE_V1',subjects=parent['subjects'],dev=parent['dev'],
        cases=parent['cases'],input_indices=INPUT,query_indices=QUERY,distance_floor_m=.001,inverse_distance_power=2,
        noise_magnitude_m=.005,methods=['FIXED','RBF_EXACT','RBF_NOISY5','CONVEX4_EXACT','CONVEX4_NOISY5'],
        surface_changed=False,targets_are_program_generated=True))
    output=[];manifest=[];noise_audit=[]
    for r in cases:
        subject,case=r['subject'],r['case'];dest=root/'runs'/subject/case;dest.mkdir(parents=True,exist_ok=True)
        mesh=np.load(r['mesh_path']);V,F=mesh['vertices_m'],mesh['faces'];assert sha(r['mesh_path'])==r['mesh_sha256']
        source=PARENT/'runs'/subject/case;original=read(source/'results.json')
        for old,new in [('FIXED','FIXED'),('REF4_EXACT','RBF_EXACT'),('REF4_NOISY5','RBF_NOISY5')]:
            shutil.copyfile(source/(old+'.npz'),dest/(new+'.npz'))
            oldrow=next(x for x in original if x['method']==old);output.append(dict(**{k:v for k,v in oldrow.items() if k!='method'},method=new,role='dev' if subject in parent['dev'] else 'consumed_validation',inherited=True))
        inputs=np.load(r['input_path']);assert np.array_equal(inputs['input_indices'],INPUT)
        # Both estimates precede opening any unprovided evaluation truth.
        exact=estimate(V,F,records,INPUT,inputs['exact_xyz_m'],ids)
        noisy=estimate(V,F,records,INPUT,inputs['noisy_xyz_m'],ids)
        truth=np.load(r['truth_path']);assert np.array_equal(truth['query_indices'],QUERY)
        for name,result,inputkey in [('CONVEX4_EXACT',exact,'exact_xyz_m'),('CONVEX4_NOISY5',noisy,'noisy_xyz_m')]:
            np.savez_compressed(dest/(name+'.npz'),**result,input_indices=np.asarray(INPUT),query_indices=np.asarray(QUERY))
            metric=evaluate(result,truth,inputs[inputkey])
            output.append(dict(subject=subject,case=case,method=name,**metric,solver={'type':'convex_inverse_graph_distance','distance_floor_m':.001},
                source_surface_sha256=r['mesh_sha256'],surface_changed=False,changed_faces=int(np.sum(result['face_id']!=np.load(dest/'FIXED.npz')['face_id'])),
                role='dev' if subject in parent['dev'] else 'consumed_validation',inherited=False))
        weight=exact['reference_weights'];response=noisy['preprojection_xyz_m']-exact['preprojection_xyz_m'];expected=weight@inputs['noise_m']
        assert np.allclose(response,expected,rtol=0,atol=1e-12)
        assert (weight>=0).all();assert np.allclose(weight.sum(axis=1),1,atol=1e-12)
        assert np.linalg.norm(response,axis=1).max()<=.005+1e-12
        noise_audit.append(dict(subject=subject,case=case,min_weight=float(weight.min()),max_weight=float(weight.max()),
            weight_l1_max=float(np.abs(weight).sum(axis=1).max()),preprojection_noise_max_mm=float(np.linalg.norm(response,axis=1).max()*1000),
            postprojection_noise_max_mm=float(np.linalg.norm(noisy['xyz_m']-exact['xyz_m'],axis=1).max()*1000)))
        write(dest/'results.json',[x for x in output if x['subject']==subject and x['case']==case])
        for name in read(root/'CONTRACT.json')['methods']:
            manifest.append(dict(subject=subject,case=case,method=name,path=str(dest/(name+'.npz')),sha256=sha(dest/(name+'.npz')),
                source_surface_path=r['mesh_path'],source_surface_sha256=r['mesh_sha256'],inherited=name.startswith('RBF') or name=='FIXED'))
        print('CASE_COMPLETE',subject,case,[round(x['query_median_mm'],3) for x in output if x['subject']==subject and x['case']==case],flush=True)
    write(root/'PER_CASE_RESULTS.json',output);write(root/'CACHE_MANIFEST.json',manifest);write(root/'NOISE_RESPONSE.json',noise_audit)
    rows=[];points=[]
    for r in output:
        rows.append({k:r[k] for k in ['subject','role','case','method','inherited','query_median_mm','query_p95_mm','query_tangent_median_mm','query_normal_median_mm']})
        for i in range(8):points.append(dict(subject=r['subject'],role=r['role'],case=r['case'],method=r['method'],probe=i,
            provided=i in INPUT,euclidean_mm=r['per_probe_error_mm'][i],tangent_mm=r['per_probe_tangent_mm'][i],normal_mm=r['per_probe_normal_abs_mm'][i]))
    csv_write(root/'PER_CASE_RESULTS.csv',rows);csv_write(root/'PER_PROBE_RESULTS.csv',points)
    summary={}
    for role in ['dev','consumed_validation']:
        summary[role]={}
        for case in parent['cases']:
            summary[role][case]={}
            for method in read(root/'CONTRACT.json')['methods']:
                subset=[r for r in output if r['role']==role and r['case']==case and r['method']==method]
                summary[role][case][method]=dict(sources=len(subset),median_mm=float(np.median([r['query_median_mm'] for r in subset])),
                    p95_mm=float(np.median([r['query_p95_mm'] for r in subset])))
    write(root/'RESULTS.json',summary)
    for r in freeze:assert sha(r['path'])==r['sha256']
    write(root/'EXECUTION_LEDGER.json',dict(status='COMPLETE',cases=60,method_records=len(output),point_records=len(points),
        inherited_point_caches=180,new_point_caches=120,new_mesh_fits=0,new_sam_inferences=0,training=0,
        source_files=len(freeze),source_unchanged=True,seconds=time.time()-start))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
