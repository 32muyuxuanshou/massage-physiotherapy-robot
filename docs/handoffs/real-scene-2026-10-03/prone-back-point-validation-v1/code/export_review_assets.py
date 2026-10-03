"""Export indices, cache identities and non-RGB scientific figures.

No original dataset images, sensor XYZ arrays, weights or native MHR assets are
copied to the public delivery. Complete RGB reviews remain server/local.
"""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_cached_point_diagnostics import read,write,sha

METHODS=['Official','Official+Txyz','Official+Txyz+Pose','Official+Rigid','Official+Rigid+D']


def public_point_figures(a):
    cache=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
    contract=read(a.root/'assets/EXPERIMENT_CONTRACT.json')
    points=[json.loads(line) for line in (a.root/'p1_cached_transfer/PROPAGATED_POINTS.jsonl').read_text().splitlines()]
    manifest=[]
    for subject in contract['subjects']:
        inp=np.load(cache/'inputs'/subject/'input.npz');x0,y0,x1,y1=inp['bbox_xyxy'].astype(int)
        h,w=inp['rgb'].shape[:2];x0=max(0,x0);y0=max(0,y0);x1=min(w-1,x1);y1=min(h-1,y1)
        for seed in contract['seeds']:
            paths=[cache/'visualizations'/subject/f'seed_{seed}'/(m.replace('+','_')+'_render.npz') for m in METHODS]
            before={str(p):sha(p) for p in paths};depths=[np.load(p)['depth_m'] for p in paths]
            allz=np.concatenate([z[z>0] for z in depths]);lo,hi=np.percentile(allz,[1,99])
            canvas=Image.new('RGB',(1800,600),'white');draw=ImageDraw.Draw(canvas)
            draw.text((5,5),f'{subject} seed {seed} | cached perspective Mesh depth + propagated engineering seeds | no RGB data',fill='black')
            draw.text((5,25),'Numbered points retain OLD atlas bindings; anatomy labels ON HOLD. Shading range shared across five methods.',fill='black')
            for j,(m,dep) in enumerate(zip(METHODS,depths)):
                z=dep[y0:y1+1,x0:x1+1];valid=z>0;norm=np.clip((z-lo)/max(hi-lo,1e-8),0,1)
                arr=(plt.get_cmap('viridis')(norm)[...,:3]*255).astype(np.uint8);arr[~valid]=245
                scale=min(350/arr.shape[1],500/arr.shape[0]);W,H=int(arr.shape[1]*scale),int(arr.shape[0]*scale)
                pic=Image.fromarray(cv2.resize(arr,(W,H)));canvas.paste(pic,(j*360+5,70));draw.text((j*360+5,50),m,fill='black')
                rows=[r for r in points if r['subject']==subject and r['seed']==seed and r['method']==m]
                for n,r in enumerate(rows):
                    u,v=r['uv_px'];x=j*360+5+(u-x0)*scale;y=70+(v-y0)*scale
                    if 0<=u-x0<x1-x0+1 and 0<=v-y0<y1-y0+1:
                        draw.ellipse((x-3,y-3,x+3,y+3),fill=(255,70,35));draw.text((x+4,y),str(n+1),fill='black')
            draw.text((5,580),' | '.join(f'{n+1}:{r["point_id"]}' for n,r in enumerate(rows)),fill='black')
            target=a.root/'p1_cached_transfer/public_point_figures'/subject/f'seed_{seed}.jpg'
            target.parent.mkdir(parents=True,exist_ok=True);canvas.save(target,quality=92)
            assert before=={str(p):sha(p) for p in paths}
            manifest.append(dict(subject=subject,seed=seed,path=str(target),sha256=sha(target),source_render_identities=before,original_rgb_included=False))
    write(a.root/'p1_cached_transfer/PUBLIC_POINT_FIGURE_MANIFEST.json',manifest)
    print('PUBLIC_POINT_FIGURES',len(manifest),flush=True)


def p2_indices(a):
    out=a.root/'p2_behave_crossview';contract=read(out/'P2_EXECUTION_CONTRACT.json');rows=[];meshes=[]
    for s in contract['frames']:
        folder=out/'run'/s['sequence']/s['frame'];inputs=out/'inputs'/s['sequence']/s['frame']
        for k in range(4):
            f=inputs/f'K{k}.npz';z=np.load(f);idx=z['posterior_eval_idx']
            rows.append(dict(**s,camera=f'K{k}',input_sha256=sha(f),
                point_indices_zero_based=idx.tolist(),original_color_flat_pixel_indices=z['original_flat_pixel_idx'][idx].tolist(),
                optimization='ALL_VALID_PERSON_K0_POINTS' if k==0 else 'NEVER_USED_FOR_OPTIMIZATION',
                missing=len(idx)==0))
        for m in METHODS:
            f=folder/(m.replace('+','_')+'.npz');z=np.load(f)
            assert z['vertices_m'].shape==(18439,3) and z['faces'].shape==(36874,3)
            meshes.append(dict(**s,method=m,path=str(f),sha256=sha(f),vertices=18439,faces=36874,
                optimization_camera='NONE' if m=='Official' else 'K0',optimization_point_count=len(z['optimization_point_idx']),
                O2_subset_count=len(z['pose_point_idx']),cached_fields=list(z.files),
                parameter_state_note='Rigid/D retain original MHR state plus explicit R/t and optional displacement; vertices_m is final camera geometry'))
    write(out/'FROZEN_POSTERIOR_EVALUATION_INDICES.json',dict(index_domain='NPZ points_m; original flat RGB pixels also retained',rows=rows))
    write(out/'FINAL_MESH_CACHE_MANIFEST.json',meshes)
    pairs=read(out/'RIGID_D_PAIRED_AUDIT.json');rois=read(out/'BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json')['rows']
    lookup={(r['sequence'],r['frame'],r['camera']):r for r in rois};groups={}
    for label,visible in [('K0_POSTERIOR_VISIBLE',True),('K0_POSTERIOR_NOT_QUALIFIED',False)]:
        rr=[r for r in pairs if lookup[(r['sequence'],r['frame'],'K0')]['evaluation_qualified']==visible and r['heldout_D_minus_R_median_mm'] is not None]
        groups[label]=dict(frames=len(rr),subjects=sorted({r['subject'] for r in rr}),
            improved=sum(r['heldout_D_minus_R_median_mm']<0 for r in rr),rows=rr)
    write(out/'K0_VISIBILITY_DESCRIPTIVE_AUDIT.json',dict(status='DESCRIPTIVE_NOT_A_NEW_PRIMARY_ENDPOINT',
        group_definition='Frozen pre-model RGB visibility',groups=groups,
        limits='Only five frames / three subjects have both K0 and heldout posterior reference; no new tuning or deletion'))
    print('P2_INDEX_CACHE_EXPORT',len(rows),len(meshes),flush=True)


def report_figure(a):
    out=a.root/'p2_behave_crossview';results=read(out/'RESULTS.json')
    import csv
    rows=list(csv.DictReader((out/'PER_SUBJECT_HELDOUT.csv').open()));subjects=sorted({r['subject'] for r in rows})
    fig,ax=plt.subplots(figsize=(10,5))
    for j,m in enumerate(METHODS):
        v=[float(next(r['surface_median_mm'] for r in rows if r['subject']==s and r['method']==m)) for s in subjects]
        ax.bar(np.arange(5)+(j-2)*.15,v,width=.15,label=m)
    ax.set_xticks(np.arange(5),subjects);ax.set_ylabel('Held-out posterior patch distance (mm)');ax.legend(fontsize=8)
    ax.set_title('BEHAVE consumed cohort | cameras -> frames -> sequences -> subject')
    fig.tight_layout();fig.savefig(out/'per_subject_posterior_distance.png',dpi=160);plt.close(fig)
    v=np.load(a.root/'assets/mhr_rest_vertices.npy')*10;candidate=read(a.root/'p4_rule_comparison/CANDIDATE_CANONICAL_RULE_PROXY_V2.json')
    fig,ax=plt.subplots(figsize=(6,9));ax.scatter(v[::5,0],v[::5,1],s=1,c='lightgray')
    for r in candidate['rules']:
        p=r['canonical_xyz_mm'];ax.scatter(p[0],p[1],s=20,c='blue');ax.text(p[0]+5,p[1],r['id'],fontsize=8)
    ax.set_aspect('equal');ax.set_xlabel('Canonical X (mm)');ax.set_ylabel('Canonical Y (mm)')
    ax.set_title('Separate fraction/width proxy candidate\nNOT validated vertebrae, B-cun or acupoint GT')
    fig.tight_layout();fig.savefig(a.root/'p4_rule_comparison/candidate_proxy_review.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    p2_indices(a);report_figure(a);public_point_figures(a)
