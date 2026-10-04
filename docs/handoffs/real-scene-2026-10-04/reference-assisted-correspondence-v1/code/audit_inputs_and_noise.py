"""Postprocess input identity, linear noise transport and all paired outcomes."""
import numpy as np
from common import ROOT,INPUT,QUERY,METHODS,CASES,read,write,sha

def main():
    cfg=read(ROOT/'CONTRACT.json');rows=[];source_checks=[];paired=[]
    for subject in cfg['subjects']:
        noises=[]
        for case in CASES:
            d=ROOT/'runs'/subject/case;inputs=np.load(ROOT/'inputs'/subject/(case+'.npz'));truth=np.load(ROOT/'evaluation_truth'/subject/(case+'.npz'))
            assert np.array_equal(inputs['input_indices'],INPUT) and np.array_equal(truth['query_indices'],QUERY) and not set(INPUT)&set(QUERY)
            np.testing.assert_allclose(inputs['exact_xyz_m'],truth['reference_xyz_m'][INPUT],rtol=0,atol=1e-12)
            np.testing.assert_allclose(np.linalg.norm(inputs['noise_m'],axis=1),np.full(4,.005),rtol=0,atol=1e-12)
            np.testing.assert_allclose(inputs['noisy_xyz_m']-inputs['exact_xyz_m'],inputs['noise_m'],rtol=0,atol=1e-12)
            noises.append(inputs['noise_m']);exact=np.load(d/'REF4_EXACT.npz');noisy=np.load(d/'REF4_NOISY5.npz')
            assert np.array_equal(exact['graph_distance_m'],noisy['graph_distance_m'])
            dist=exact['graph_distance_m'];pair=dist[:,INPUT];width=np.median(pair[np.triu_indices(4,1)])
            G=np.exp(-.5*(pair/width)**2);A=np.block([[G+1e-6*np.eye(4),np.ones((4,1))],[np.ones((1,4)),np.zeros((1,1))]])
            W=np.c_[np.exp(-.5*(dist.T/width)**2),np.ones(8)]@np.linalg.solve(A,np.vstack([np.eye(4),np.zeros((1,4))]))
            predicted=W@inputs['noise_m'];actual=noisy['interpolated_offset_m']-exact['interpolated_offset_m']
            np.testing.assert_allclose(predicted,actual,rtol=0,atol=1e-12)
            np.testing.assert_allclose(W.sum(1),np.ones(8),rtol=0,atol=1e-12)
            for i in QUERY:
                rows.append(dict(subject=subject,case=case,query_index=i,weights=W[i].tolist(),
                    weights_l1_sum=float(np.abs(W[i]).sum()),actual_preprojection_noise_effect_mm=float(np.linalg.norm(actual[i])*1000)))
            source_checks.append(dict(subject=subject,case=case,status='PASS',primary_query_inputs_intersection=[],
                exact_reference_matches_truth=True,noise_length_mm=5,linear_transport_recomputed=True))
        assert np.array_equal(noises[0],noises[1]) and np.array_equal(noises[0],noises[2])
    data=read(ROOT/'AGGREGATED_RESULTS.json')
    for role in ['dev','validation_consumed']:
        for case in CASES:
            for method in METHODS[1:]:
                selected=[r for r in data['paired_changes'] if r['role']==role and r['case']==case and r['method']==method]
                paired.append(dict(role=role,case=case,method=method,sources=len(selected),
                    improved=sum(r['query_change_vs_fixed_mm']<0 for r in selected),
                    worsened=sum(r['query_change_vs_fixed_mm']>0 for r in selected),
                    paired_query_change_median_mm=float(np.median([r['query_change_vs_fixed_mm'] for r in selected]))))
    write(ROOT/'INPUT_NOISE_AND_PAIR_AUDIT.json',dict(status='PASS',script_sha256=sha(__file__),cases_checked=len(source_checks),
        checks=source_checks,query_noise_transport=rows,paired_counts=paired,
        max_query_weights_l1_sum=max(r['weights_l1_sum'] for r in rows),
        max_preprojection_noise_effect_mm=max(r['actual_preprojection_noise_effect_mm'] for r in rows),
        interpretation='Non-convex interpolation weights can amplify 5mm input perturbations before nonlinear surface projection; diagnostic, no changed weights or case selection.'))
    print('INPUT_NOISE_AUDIT_PASS',len(source_checks),'max L1',max(r['weights_l1_sum'] for r in rows),
        'max noise effect mm',max(r['actual_preprojection_noise_effect_mm'] for r in rows),flush=True)
    for r in paired:
        if r['role']=='validation_consumed':print(r,flush=True)

if __name__=='__main__':main()
