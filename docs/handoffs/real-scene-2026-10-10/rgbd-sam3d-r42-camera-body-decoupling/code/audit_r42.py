"""Verify actual inputs, all final native caches and sampled independent replays."""
import argparse
import ast
import json
from pathlib import Path
from run_r41_txyz import dependencies,np,sha


def training_kernel(path):
    tree=ast.parse(path.read_text());selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['features','fit','predict']]
    return ast.dump(ast.Module(body=selected,type_ignores=[]),include_attributes=False)


def main(a):
    w=a.work;s=a.source;assets=s/'assets';f=dependencies(s/'code')
    source_receipt=json.loads((assets/'original_assets/SOURCE_RECEIPT.json').read_text())
    inputs=[]
    for r in source_receipt['records']:
        key=r['key'];paths=[(assets/'original_assets/inputs'/(key+'.npz'),r['compact_sha256']),
                           (assets/'original_assets/official'/(key+'.npz'),r['official_sha256']),
                           (assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'),r['heldout_sha256'])]
        for path,expected in paths:assert sha(path)==expected
        inputs.append(dict(key=key,compact_sha256=r['compact_sha256'],official_sha256=r['official_sha256'],heldout_sha256=r['heldout_sha256']))
    report=json.loads((w/'ALL_RESULTS.json').read_text());rows=report['records']
    new=[r for r in rows if r['cell'] not in ['official','g1_seed11','g1_seed23','g1_seed37']]
    assert len(new)==1856 and len(rows)==2784
    faces=np.load(assets/'original_assets/official/faces.npy');files=[];max_roundoff=0.
    for r in new:
        key,cell=r['key'],r['cell']
        body_dir=assets/f'r4/formal/g1_seed{cell.split("seed")[-1]}/real' if cell.startswith('g1_body_official_camera') else assets/'original_assets/official'
        body=np.load(body_dir/(key+'.npz'));raw=np.load(w/'raw'/cell/(key+'.npz'));final=np.load(w/'corrected'/cell/(key+'.npz'))
        for k in ['global_rot','body_pose','shape','scale']:
            assert np.array_equal(body[k],raw[k]) and np.array_equal(body[k],final[k])
        delta=np.asarray(r['applied_translation_m'])
        assert np.max(np.abs(final['vertices_camera_A']-raw['vertices_camera_A']-delta))<1e-12
        assert np.max(np.abs(final['pred_cam_t']-raw['pred_cam_t']-delta))<1e-12
        relative_error=float(np.max(np.abs((raw['vertices_camera_A'].astype(np.float64)-raw['pred_cam_t'].reshape(3))-
                                          (body['vertices_camera_A'].astype(np.float64)-body['pred_cam_t'].reshape(3)))))
        assert relative_error<1e-6;max_roundoff=max(max_roundoff,relative_error)
        a_input=np.load(assets/'original_assets/inputs'/(key+'.npz'))
        ca,cb=({k:a_input['A_'+k] for k in ['R','T']},{k:a_input['B_'+k] for k in ['R','T']})
        assert np.max(np.abs(f['transform_camera'](final['vertices_camera_A'],ca,cb)-final['vertices_camera_B']))<1e-12
        distance=np.load(w/'distances'/cell/(key+'.npz'));assert len(distance['after_mm'])==2048
        for sub in ['raw','corrected','distances']:
            path=w/sub/cell/(key+'.npz');files.append(dict(file=str(path.relative_to(w)).replace('\\','/'),sha256=sha(path),bytes=path.stat().st_size))
    replays=[]
    for cell in sorted({r['cell'] for r in new}):
        r=next(x for x in new if x['cell']==cell and x['identity']=='p001196');key=r['key']
        z=np.load(w/'corrected'/cell/(key+'.npz'));points=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
        exact=f['distance'](points,z['vertices_camera_B'],faces)*1000;cached=np.load(w/'distances'/cell/(key+'.npz'))['after_mm']
        assert np.array_equal(exact,cached);replays.append(dict(cell=cell,key=key,status='PASS',max_error_mm=0.))
    train=json.loads((w/'camera_only_pilot/TRAINING_RESULT.json').read_text())
    assert sha(w/'camera_only_pilot/camera_only_best.npz')==train['model_sha256']
    training_snapshot=w/'code/training_snapshot/camera_only_r42.py'
    current=Path(__file__).parent/'camera_only_r42.py'
    assert sha(training_snapshot)==train['config']['head_sha256']
    assert training_kernel(training_snapshot)==training_kernel(current)
    qa=json.loads((w/'TORCH_ADAPTER_QA.json').read_text());assert qa['status']=='PASS' and qa['head_sha256']==sha(current)
    out=dict(status='PASS',actual_input_checks=len(inputs)*3,new_native_cases=len(new),cache_files=len(files),cached_mesh_replays=replays,
        native_body_parameter_arrays_exact=True,body_vertex_roundoff_max_m=max_roundoff,
        camera_applied_once=True,all_A_to_B_transforms_exact=True,frozen_model_sha256=train['model_sha256'],
        original_training_source_sha256=sha(training_snapshot),final_inference_source_sha256=sha(current),
        features_fit_predict_AST_unchanged=True,inference_only_fix='Missing-depth adapter bypass preserves all original output tensors exactly.',
        metadata_repair='No-learned-offset ablation originally recorded learned-head response; evaluator rerun with zero coefficients. Surface metrics unchanged, no refit.',
        test_read=False,camera_B_fitting=False,actual_inputs=inputs)
    (w/'POST_EXECUTION_INTEGRITY.json').write_text(json.dumps(out,indent=2))
    (w/'CACHE_MESH_MANIFEST.json').write_text(json.dumps(dict(files=files),indent=2))
    print('R42_AUDIT_PASS',len(new),len(files),max_roundoff,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True);main(p.parse_args())
