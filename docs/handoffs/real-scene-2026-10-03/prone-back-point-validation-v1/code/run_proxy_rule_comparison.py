"""Proxy rules on cached surfaces. Shared reference frame comes from Rigid only.

Template fractions and width/8 are engineering proxies, never observed vertebrae
or independently measured B-cun. Old T0 bindings remain unchanged.
"""
import argparse,json
from pathlib import Path
import numpy as np
from rule_engine import project_rules
from run_cached_point_diagnostics import read,write,sha,interpolate,save_csv,canonical_preview


FRACTIONS={'C7_T1':.08,'T3':.23,'T5':.38,'T9':.68,'L2':.90}


def build_template_references(vertices,faces,mask):
    centers=vertices[faces[mask]].mean(1);ymin,ymax=centers[:,1].min(),centers[:,1].max()
    width=np.percentile(centers[:,0],95)-np.percentile(centers[:,0],5)
    specs=[];levels={}
    for level,fraction in FRACTIONS.items():
        y=ymax-fraction*(ymax-ymin)
        band=centers[(np.abs(centers[:,1]-y)<.035*(ymax-ymin)) & (np.abs(centers[:,0])<1.0)]
        assert len(band)>0
        z=np.median(band[:,2])
        for position,x in [('center',0),('negative_x',-width/2),('positive_x',width/2)]:
            key=level+'_'+position
            specs.append(dict(id=key,name=key,reference_level=key,lateral_b_cun=0,laterality='midline'))
            levels[key]=dict(point=[float(x),float(y),float(z)],lateral_axis=[1,0,0],native_per_b_cun=1)
    frame=dict(status='TEMPLATE_FRACTION_PROXY_NOT_OBSERVED_ANATOMY',levels=levels)
    binding=project_rules(vertices,faces,mask,specs,frame)
    for row in binding['rules']:row['medical_truth']=False
    binding.update(vertical_order='canonical +Y up; fractions measured downward',fractions=FRACTIONS,
        span_divisor_proxy=8,unit='cm',laterality='legacy rule-engine negative-X=left alias; anatomical side unresolved',
        limitations=['Template fraction is not vertebral localization','Width/8 is not observed bone-proportional B-cun'])
    return binding


def frame_from_reference_bindings(vertices,faces,binding):
    refs={r['id']:r for r in binding['rules']};levels={}
    for level in FRACTIONS:
        p={}
        for position in ['center','negative_x','positive_x']:
            ref=refs[level+'_'+position];p[position]=(vertices[faces[ref['face_index']]]*np.array(ref['barycentric'])[:,None]).sum(0)
        axis=p['positive_x']-p['negative_x'];width=np.linalg.norm(axis);assert width>0
        levels[level]=dict(point=p['center'].tolist(),lateral_axis=(axis/width).tolist(),native_per_b_cun=float(width/8))
    return dict(status='TOPOLOGY_DERIVED_PROXY_NOT_INDEPENDENT_REFERENCE',coordinate_frame='camera_m',levels=levels,
        reference_mesh_method='Official+Rigid',span_divisor_proxy=8,medical_truth=False)


def main(a):
    a.out.mkdir(parents=True,exist_ok=True);faces=np.load(a.assets/'mhr_faces.npy')
    canonical=np.load(a.assets/'mhr_rest_vertices.npy').astype(float);mask=read(a.assets/'candidate_posterior_mask.json')['face_ids']
    rules=read(a.assets/'RULE_ENGINE_CONFIG_V1.json')['rules'];old=read(a.assets/'VIRTUAL_ACUPOINTS_ENGINEERING_V1.json')['records']
    binding=build_template_references(canonical,faces,mask)
    write(a.out/'TEMPLATE_REFERENCE_BINDINGS_PROXY_V2.json',binding)
    # Separate proxy candidate only. Never overwrites the old atlas.
    cframe=frame_from_reference_bindings(canonical,faces,binding);cframe['coordinate_frame']='canonical_cm'
    candidate=project_rules(canonical,faces,mask,rules,cframe)
    candidate['status']='CANDIDATE_PROXY_V2_REQUIRES_ANATOMICAL_REVIEW';candidate['unit']='cm';candidate['native_to_mm']=10
    for row in candidate['rules']:row['canonical_xyz_mm']=(np.array(row['surface_xyz'])*10).tolist()
    write(a.out/'CANDIDATE_CANONICAL_RULE_PROXY_V2.json',candidate)
    canonical_preview(canonical,faces,mask,[dict(id=r['id'],face_index=r['face_index'],barycentric=r['barycentric']) for r in candidate['rules']],a.out/'canonical_rule_proxy_v2.jpg')
    contract=read(a.assets/'EXPERIMENT_CONTRACT.json');rows=[];frames=[];sources={}
    for subject in contract['subjects']:
        for seed in contract['seeds']:
            base=a.cache/'meshes'/subject/f'seed_{seed}'
            rp=base/'Official_Rigid.npz';rigid=np.load(rp)['vertices_m'];frame=frame_from_reference_bindings(rigid,faces,binding)
            write(a.out/'reference_frames'/subject/f'seed_{seed}.json',frame)
            frames.append(dict(subject=subject,seed=seed,reference_sha256=sha(rp),source='Official+Rigid cached mesh; shared across all five methods',independent_reference=False))
            for method in contract['methods']:
                path=base/(method.replace('+','_')+'.npz');sources[str(path)]=sha(path)
                meta=read(path.with_suffix('.json'));assert meta['mesh_sha256']==sources[str(path)]
                vertices=np.load(path)['vertices_m'];old_xyz,_,_=interpolate(vertices,faces,old);old_map={r['id']:p for r,p in zip(old,old_xyz)}
                output=project_rules(vertices,faces,mask,rules,frame)
                for row in output['rules']:
                    point=np.array(row['surface_xyz']);delta=point-old_map[row['id']];normal=np.array(row['surface_normal']);along=float(delta@normal)
                    bary=np.array(row['barycentric']);reconstructed=(vertices[faces[row['face_index']]]*bary[:,None]).sum(0)
                    assert np.allclose(reconstructed,point,atol=1e-10) and abs(bary.sum()-1)<1e-10 and min(bary)>=-1e-10
                    rows.append(dict(subject=subject,seed=seed,method=method,point_id=row['id'],
                        reference_method='Official+Rigid',independent_reference=False,medical_truth=False,
                        rule_target_m=row['rule_target'],xyz_m=row['surface_xyz'],face_id=row['face_index'],barycentric=row['barycentric'],normal=row['surface_normal'],
                        surface_projection_distance_mm=row['projection_distance_native']*1000,
                        old_T0_disagreement_mm=float(np.linalg.norm(delta)*1000),old_T0_disagreement_normal_mm=abs(along)*1000,
                        old_T0_disagreement_tangent_mm=float(np.linalg.norm(delta-along*normal)*1000),
                        source_mesh_sha256=sources[str(path)],interpretation='Disagreement only: old T0 has known semantic errors; T1 is a fraction/width proxy, not accuracy'))
            print('PROXY_RULE',subject,seed,flush=True)
    assert len(rows)==2400
    (a.out/'RULE_PROXY_POINTS.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    write(a.out/'SHARED_REFERENCE_FRAME_MANIFEST.json',frames)
    after={p:sha(p) for p in sources};assert after==sources
    write(a.out/'SOURCE_PRE_POST_IDENTITY.json',dict(status='PASS',before=sources,after=after))
    summary=[]
    for method in contract['methods']:
        for pid in [r['id'] for r in rules]:
            subject_means=[]
            for subject in contract['subjects']:
                selected=[r for r in rows if r['method']==method and r['point_id']==pid and r['subject']==subject]
                subject_means.append(np.mean([r['old_T0_disagreement_mm'] for r in selected]))
            summary.append(dict(method=method,point_id=pid,subject_equal_median_disagreement_mm=float(np.median(subject_means)),
                medical_truth=False,interpretation='NOT_AN_ACUPOINT_ERROR'))
    save_csv(a.out/'METHOD_POINT_DISAGREEMENT_SUMMARY.csv',summary)
    write(a.out/'SUMMARY.json',dict(status='PROXY_RULE_CHAIN_COMPLETE_INDEPENDENT_REFERENCE_NOT_AVAILABLE',point_records=len(rows),
        shared_reference_frames=len(frames),inference_runs=0,fit_runs=0,
        template_orientation_corrected_in_separate_proxy_candidate=True,legacy_T0_unchanged=True,
        independent_target_accuracy_measured=False,clinical_use_approved=False))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['assets','cache','out']:p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
