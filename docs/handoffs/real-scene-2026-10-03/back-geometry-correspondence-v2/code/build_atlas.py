"""Neutral geometric engineering probes; no vertebral or acupoint inference."""
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from common import ROOT,OLD,BASE,read,write,sha
sys.path.insert(0,str(OLD/'code'))
from run_cached_point_diagnostics import interpolate

SPEC=[('ENG_MID_UP',.20,0),('ENG_MID_DOWN',.75,0)]+[
    (f'ENG_PAIR_{j}_{side}',f,x) for j,f in enumerate([.30,.50,.70],1)
    for side,x in [('NEG_X',-.20),('POS_X',.20)]]


def bind(V,F,ids,x,y):
    tri=V[F[ids]];xy=tri[:,:,:2]
    # Intersect a parallel canonical Z ray at exact x,y, with every candidate.
    a=xy[:,1]-xy[:,0];b=xy[:,2]-xy[:,0];q=np.array([x,y])-xy[:,0]
    den=a[:,0]*b[:,1]-a[:,1]*b[:,0]
    ok=np.abs(den)>1e-10
    t=np.zeros(len(ids));s=t.copy()
    t[ok]=(q[ok,0]*b[ok,1]-q[ok,1]*b[ok,0])/den[ok]
    s[ok]=(a[ok,0]*q[ok,1]-a[ok,1]*q[ok,0])/den[ok]
    bary=np.c_[1-t-s,t,s];hit=ok&(bary.min(1)>=-1e-8)
    assert hit.any(),f'Frozen engineering target outside working mesh: {x,y}'
    candidates=np.flatnonzero(hit);z=(tri[candidates,:,2]*bary[candidates]).sum(1)
    i=candidates[np.argmin(z)];bary=bary[i];fi=int(ids[i])
    xyz=(V[F[fi]]*bary[:,None]).sum(0)
    n=np.cross(V[F[fi,1]]-V[F[fi,0]],V[F[fi,2]]-V[F[fi,0]]);n/=np.linalg.norm(n)
    assert np.max(np.abs(xyz[:2]-[x,y]))<1e-7
    return fi,bary,xyz,n


def preview(V,F,ids,new,old,out):
    pts=np.array([r['canonical_xyz_mm'] for r in new]);oldpts=np.array([
        (V[F[r['face_index']]]*np.array(r['barycentric'])[:,None]).sum(0) for r in old])
    fig,axes=plt.subplots(1,4,figsize=(16,8))
    for ax,(a,b,title,ascending) in zip(axes,[(0,1,'Posterior: view from -Z',False),
            (0,1,'Anterior: view from +Z',True),(2,1,'Side: view from +X',True),
            (0,1,'Posterior working region / old vs new',False)]):
        faces=F if ax is not axes[-1] else F[ids]
        tr=V[faces];d=({0,1,2}-{a,b}).pop();order=np.argsort(tr.mean(1)[:,d]);order=order if ascending else order[::-1]
        colors=np.where(np.isin(np.arange(len(F)),ids),.5,.83) if len(faces)==len(F) else np.full(len(faces),.6)
        ax.add_collection(PolyCollection(tr[order][:,:,[a,b]],facecolors=plt.cm.Greys(colors[order]),edgecolors='none'))
        ax.scatter(pts[:,a],pts[:,b],c='red',s=28,zorder=3)
        if ax is axes[-1]:
            ax.scatter(oldpts[:,a],oldpts[:,b],c='blue',s=25,zorder=3,label='Old seeds, clinically unresolved')
            for i,p in enumerate(pts):ax.text(p[a]+5,p[b],str(i+1),fontsize=8)
            ax.legend(fontsize=7)
        ax.autoscale();ax.set_aspect('equal');ax.set_title(title,fontsize=10);ax.set_xlabel('XYZ'[a]+' (mm)');ax.set_ylabel('+Y up (mm)')
    fig.suptitle('RED: ENG geometric probes / BLUE: old labels / cm x10; clinical laterality unproven')
    fig.tight_layout();fig.savefig(out,dpi=140);plt.close(fig)


def main():
    a=ROOT/'assets';out=ROOT/'a_atlas';out.mkdir(exist_ok=True)
    V=np.load(a/'mhr_rest_vertices.npy').astype(float)*10;F=np.load(a/'mhr_faces.npy').astype(int)
    ids=np.array(read(a/'candidate_posterior_mask.json')['face_ids']);centers=V[F[ids]].mean(1)
    ymin,ymax=centers[:,1].min(),centers[:,1].max()
    # A separate working region, not a change to the original 2152 evaluation faces.
    work=ids[centers[:,1]>=ymin+.20*(ymax-ymin)]
    c=V[F[work]].mean(1);lo,hi=c[:,1].min(),c[:,1].max();width=np.ptp(V[np.unique(F[work])][:,0])
    source=[dict(path=str(a/name),sha256=sha(a/name)) for name in ['mhr_rest_vertices.npy','mhr_faces.npy','candidate_posterior_mask.json']]
    contract=dict(status='FROZEN_BEFORE_PROPAGATION',semantic_status='ENGINEERING_SURFACE_PROBES_NOT_ACUPOINTS',
        native_unit='cm',native_to_mm=10,prediction_unit='m',prediction_to_mm=1000,
        axis=dict(y='+Y canonical superior; verified by full-height canonical geometry',
            posterior='-Z in reviewed posterior mask and visible surface normals',
            x='Signed canonical X; patient anatomical left/right NOT ESTABLISHED'),
        target_spec=[dict(id=i,fraction_down=f,x_fraction_of_work_width=x) for i,f,x in SPEC],
        working_y_range_mm=[float(lo),float(hi)],working_width_mm=float(width),
        work_definition='original posterior face centroids, exclude bottom 20% of original centroid Y range',
        old_primary_evaluation_faces=2152,work_faces=len(work),source=source,
        limits=['No measured vertebral levels','No B-cun rule','No medical truth','Working region is geometric, not clinician-reviewed anatomy'])
    write(out/'ATLAS_BUILD_CONTRACT.json',contract)
    records=[]
    for name,f,x in SPEC:
        fi,bary,xyz,n=bind(V,F,work,x*width,hi-f*(hi-lo))
        records.append(dict(id=name,face_id=fi,face_index=fi,vertex_ids=F[fi].tolist(),barycentric=bary.tolist(),
            canonical_xyz_mm=xyz.tolist(),canonical_normal=n.tolist(),fraction_down=f,x_fraction_of_width=x,
            semantic_status=contract['semantic_status'],medical_truth=False,anatomical_side=None))
    p=np.array([r['canonical_xyz_mm'] for r in records]);assert np.max(np.abs(p[:2,0]))<1e-7
    assert p[0,1]>p[1,1] and all(p[i,0]<0<p[i+1,0] for i in [2,4,6])
    assert all(r['canonical_normal'][2]<0 for r in records)
    atlas=dict(schema='ENGINEERING_BACK_ATLAS_V2',**contract,records=records,confidence=None)
    write(out/'ENGINEERING_BACK_ATLAS_V2.json',atlas)
    write(out/'ENGINEERING_WORK_REGION_V2.json',dict(face_ids=work.tolist(),excluded_old_face_ids=sorted(set(ids.tolist())-set(work.tolist())),
        not_used_for_primary_evaluation=True,primary_faces_sha256=sha(a/'candidate_posterior_mask.json')))
    old=read(a/'VIRTUAL_ACUPOINTS_ENGINEERING_V1.json')['records']
    preview(V,F,work,records,old,out/'CANONICAL_OLD_NEW.png')
    mapping=[dict(old_id=r['id'],new_eng_counterpart=None,status='NO_MEDICAL_EQUIVALENCE_ESTABLISHED') for r in old]
    write(out/'OLD_MEDICAL_LABEL_HOLD.json',mapping)
    rows=[];identities=[];contract0=read(BASE/'delivery/EXPERIMENT_CONTRACT.json')
    for subject in [*contract0['dev'],*[s for s in contract0['subjects'] if s not in contract0['dev']]]:
        for seed in contract0['seeds']:
            for method in contract0['methods']:
                path=BASE/'run_v2/meshes'/subject/f'seed_{seed}'/(method.replace('+','_')+'.npz')
                z=np.load(path);assert np.array_equal(z['faces'],F)
                xyz,n,area=interpolate(z['vertices_m'],F,records)
                assert np.isfinite(xyz).all() and np.all(area>0)
                for i,r in enumerate(records):rows.append(dict(subject=subject,seed=seed,method=method,id=r['id'],
                    xyz_m=xyz[i].tolist(),normal=n[i].tolist(),face_id=r['face_id'],barycentric=r['barycentric'],medical_truth=False))
                identities.append(dict(path=str(path),sha256=sha(path)))
    assert len(rows)==2400 and len(identities)==300
    write(out/'PROPAGATED_2400_POINTS.json',rows);write(out/'CACHE_SOURCE_IDENTITIES.json',identities)
    write(out/'ATLAS_QA.json',dict(status='PASS_GEOMETRIC_BINDING_ONLY',points=8,propagated=2400,caches=300,
        exact_midline_max_abs_x_mm=float(abs(p[:2,0]).max()),upper_above_lower=True,three_signed_pairs=True,
        every_probe_posterior_normal=True,anatomical_left_right='UNPROVEN_USE_SIGNED_X',medical_accuracy_validated=False,
        no_new_model_runs=True,no_new_fits=True))
    print('ATLAS_PASS',len(rows),len(work),flush=True)

if __name__=='__main__':main()
