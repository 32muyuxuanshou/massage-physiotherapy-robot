"""Finite A-only reprojected paths, preserving the frozen Official body."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,json,time
from functools import lru_cache
import numpy as np
import torch
from common import W,R52,OLD,G,CFG,load,sha,tasks,key,dump
from projection import Projector,nested_ids
from solvers import update,finish,analytic_qa


@lru_cache(maxsize=1)
def prior_records():
    inputs={r['tag']:r for r in json.loads((R52/'INPUT_FREEZE.json').read_text())['records']}
    outputs={r['tag']:r for r in json.loads((R52/'POST_INTEGRITY.json').read_text())['output_records']}
    return inputs,outputs


def one(t,projector):
    started=time.monotonic();tag=key(t)
    oldfit=R52/'fits'/(tag+'.json');old=json.loads(oldfit.read_text());gold=load(G/t['prediction'])
    source=OLD/'cache'/('native_scale_v2' if t['dataset']=='native' else 'humman_development_v1' if t['dataset']=='real' else 'behave/s%d'%t['seed'])/(t['key']+'.pt')
    rec=torch.load(source,map_location='cpu',weights_only=False)
    source_sha=sha(source);inputs,outputs=prior_records();expected=inputs[tag]
    assert sha(oldfit)==outputs[tag]['fit_sha256']
    assert source_sha==expected['sources'][str(source)]
    np.testing.assert_array_equal(rec['official']['pred_vertices'].numpy().reshape(-1,3),gold['body_m'])
    body=gold['body_m'];coarse=gold['coarse_camera'].reshape(3);original=np.asarray(old['methods']['official_hist6']['camera_m'])-np.asarray(old['methods']['official_hist6']['applied_delta_m'])
    original=original.astype(np.float32)
    projector.bind(rec,body,coarse);ids=nested_ids()
    initial={n:projector.sample(np.zeros(3),n) for n in [256,1024,4096]}
    replay=load(OLD/'query_replay_frozen_coarse'/('s%d'%t['seed'])/(t['dataset']+'_'+t['key']+'.npz'))
    first=initial[256];geo=replay['geometry'];obs_diff=int(np.sum(first['observed']!=replay['observed']))
    numeric=max(float(np.max(abs(first['query']-geo[:,:3]))),float(np.max(abs(first['measured']-geo[:,3:6]))),float(np.max(abs(first['grid']-geo[:,15:17]))))
    # Same GPU camera operations: no tolerance adjustment to hide a pixel mismatch.
    assert numeric<2e-6,(tag,'PROJECTION_REPLAY_MISMATCH',numeric)
    known=(t['dataset']=='behave' and t['seed']==23 and t['key']=='Date03_Sub03_tablesmall_move_t0025.000')
    assert obs_diff==0 or known,(tag,'VISIBILITY_REPLAY_MISMATCH',obs_diff)
    result={n:old['methods'][n] for n in ['official_hist6','coarse','fine','hist_plane6']}
    def add(name,raw,tr):
        applied,fb=finish(raw)
        result[name]=dict(camera_m=(coarse+applied).tolist(),raw_delta_m=raw.tolist(),applied_delta_m=applied.tolist(),
            displacement_from_official_m=(coarse+applied-original).tolist(),fallback=fb,trace=tr.copy())
    paths=[('med',256,'median',True,False,6),('plane',256,'plane',True,False,6),
        ('gate',256,'plane',True,True,3),('trim_huber',256,'huber',True,False,3),
        ('plain',256,'plane',False,False,3),('huber',256,'huber',False,False,3),
        ('1024_plane',1024,'plane',True,False,3),('4096_plane',4096,'plane',True,False,3)]
    for label,count,kind,trim,gate,steps in paths:
        delta=np.zeros(3);trace=[]
        for i in range(steps):
            s=initial[count] if i==0 else projector.sample(delta,count);mask=s['observed']
            step,stats=update((s['measured'][mask]-s['query'][mask]).astype(np.float64),s['normal'][mask],kind,trim,gate)
            delta+=step
            trace.append(dict(iteration=i+1,step_m=step.tolist(),raw_t_m=delta.tolist(),
                visible_anchor_ids=ids[count][mask].tolist(),**stats))
            if label in ['med','plane'] and i+1 in [1,2,3,6]:
                name='proj_vis_med1' if label=='med' and i==0 else 'proj_%s%d'%(label,i+1);add(name,delta,trace)
        if label not in ['med','plane']:add('proj_'+label+'3',delta,trace)
    reference_delta=np.asarray(old['methods']['proj_vis_med1']['raw_delta_m'])
    difference=float(np.max(abs(np.asarray(result['proj_vis_med1']['raw_delta_m'])-reference_delta)))
    assert difference<2e-6,(tag,'ONE_STEP_MEDIAN_MISMATCH',difference)
    assert set(result)==set(CFG['methods'])
    input_path=W/'inputs'/(tag+'.npz');input_path.parent.mkdir(exist_ok=True)
    np.savez_compressed(input_path,depth=rec['depth'].numpy(),valid=rec['valid'].numpy(),rays=rec['rays'].numpy(),
        K=rec['batch']['cam_int'].numpy(),size=rec['batch']['ori_img_size'].numpy(),affine=rec['batch']['affine_trans'].numpy())
    out=W/'fits';out.mkdir(exist_ok=True);npz=out/(tag+'.npz')
    np.savez_compressed(npz,method_names=np.array(CFG['methods']),cameras_m=np.array([result[n]['camera_m'] for n in CFG['methods']]),
        raw_deltas_m=np.array([result[n]['raw_delta_m'] for n in CFG['methods']]),applied_deltas_m=np.array([result[n]['applied_delta_m'] for n in CFG['methods']]),
        body_m=body,coarse_camera_m=coarse,original_camera_m=original)
    sources={str(source):source_sha,str(oldfit):sha(oldfit),str(G/t['prediction']):sha(G/t['prediction'])}
    record=dict(task=t,methods=result,compact_prediction=str(npz),compact_prediction_sha256=sha(npz),
        fit_input_sha256=sha(input_path),prediction_sha256=sha(G/t['prediction']),official_reproduction=old['official_reproduction'],
        sources=sources,input=str(input_path),input_sha256=sha(input_path),Camera_B_read=False,body_exact_unchanged=True,
        replay_numeric_max_m=numeric,replay_observed_difference=obs_diff,one_step_median_delta_difference_m=difference,
        seconds=time.monotonic()-started)
    dump(out/(tag+'.json'),record)
    return dict(tag=tag,dataset=t['dataset'],seed=t['seed'],key=t['key'],input=str(input_path),sha256=sha(input_path),
        sources=sources,replay_numeric_max_m=numeric,replay_observed_difference=obs_diff,one_step_median_delta_difference_m=difference,seconds=record['seconds'])


def main(seed,pilot):
    torch.set_num_threads(1);start=time.monotonic();p=Projector()
    rr=[t for t in tasks() if t['seed']==seed]
    if pilot:
        rr=[next(t for t in rr if t['dataset']==d) for d in ['native','real','behave']]+[next(t for t in rr if t['dataset']=='real' and t['identity']==i) for i in ['p001195','p001196']]
    records=[]
    for i,t in enumerate(rr,1):
        r=one(t,p);records.append(r)
        if i%25==0 or pilot:print('FITS',seed,i,len(rr),round(time.monotonic()-start,1),flush=True)
    dump(W/('PILOT_s%d.json'%seed if pilot else 'FITS_s%d.json'%seed),dict(status='PASS' if pilot else 'COMPLETE',records=records,seconds=time.monotonic()-start,analytic=analytic_qa() if pilot else None))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--pilot',action='store_true');a=p.parse_args();main(a.seed,a.pilot)
