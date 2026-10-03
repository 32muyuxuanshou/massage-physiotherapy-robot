"""Frozen aggregation and visual review, exclusively from final cached meshes.

No inference or optimization. Original RGB review stays on the server/local;
the public figure variant contains predictions and numeric metrics only.
"""
import argparse,json,sys
from collections import defaultdict
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from run_cached_point_diagnostics import read,write,sha,save_csv
from behave_v2_io import read_camera,transform_between

METHODS=['Official','Official+Txyz','Official+Txyz+Pose','Official+Rigid','Official+Rigid+D']
KEYS=['surface_median_mm','surface_p95_mm','surface_coverage_50mm','ray_hit_fraction','ray_common_median_mm','ray_common_p95_mm']


def token(m):return m.replace('+','_')


def pack(rows):
    result={}
    for key in KEYS:
        v=[r[key] for r in rows if r.get(key) is not None]
        result[key]=float(np.median(v)) if v else None
    return result


def flatten(r):
    return {**{k:r[k] for k in ['subject','sequence','frame','camera','method','role','reference','posterior_point_count']},
        'surface_median_mm':r['surface']['median_mm'],'surface_p95_mm':r['surface']['p95_mm'],
        'surface_coverage_50mm':r['surface']['coverage_50mm'],'ray_hit_fraction':r['ray_hit_fraction'],
        'ray_common_count':r['ray_common_count'],'ray_common_median_mm':r['ray_common']['median_mm'],
        'ray_common_p95_mm':r['ray_common']['p95_mm'],
        'surface_max_mm':r['surface']['max_mm'],'above_500mm_count':r['surface']['above_500mm_count']}


def render_tile(rgb,V,F,K,dist,bbox,patch,public=False):
    x0,y0,x1,y1=bbox.astype(int);w,h=x1-x0+1,y1-y0+1;scale=min(360/w,410/h)
    uv=cv2.projectPoints(V[:,None],np.zeros(3),np.zeros(3),K,dist)[0].reshape(-1,2)
    uv=(uv-[x0,y0])*scale;polys=uv[F];W,H=int(w*scale),int(h*scale)
    mask=np.zeros((H,W),np.uint8)
    for polygon in polys[np.all(V[F,2]>0,axis=1)]:cv2.fillConvexPoly(mask,np.round(polygon).astype(np.int32),255)
    canvas=np.full((H,W,3),245,np.uint8) if public else cv2.resize(rgb[y0:y1+1,x0:x1+1],(W,H))
    # Painter shading is qualitative; numerical ray z-buffer is separate.
    painted=canvas.copy();tri=V[F];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
    shade=.6+.4*np.abs(n[:,2])
    for i in np.argsort(tri[:,:,2].mean(1))[::-1]:
        if np.all(tri[i,:,2]>0):cv2.fillConvexPoly(painted,np.round(polys[i]).astype(np.int32),tuple(int(v*shade[i]) for v in [178,35,130]))
    covered=mask>0;canvas[covered]=painted[covered] if public else (.45*canvas[covered]+.55*painted[covered]).astype(np.uint8)
    edges=cv2.morphologyEx(mask,cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8))>0;canvas[edges]=[50,230,50]
    if not public and patch is not None:
        pp=cv2.resize(patch[y0:y1+1,x0:x1+1],(W,H),interpolation=cv2.INTER_NEAREST)
        pe=cv2.morphologyEx(pp,cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8))>0;canvas[pe]=[20,230,240]
    tile=Image.new('RGB',(370,465),'white');tile.paste(Image.fromarray(canvas),((370-W)//2,40));return tile


def visuals(a,contract):
    rows=[];roi={(r['sequence'],r['frame'],r['camera']):r for r in read(a.out/'BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json')['rows']}
    for s in contract['frames']:
        seq,frame=s['sequence'],s['frame'];folder=a.out/'run'/seq/frame;inputs=a.out/'inputs'/seq/frame
        evaluation=read(folder/'evaluation.json');by={(r['camera'],r['method']):r for r in evaluation}
        identity=read(inputs/'identity.json');cams=[read_camera(a.behave/'data/calibs',seq,k) for k in range(4)]
        variants={m:np.load(folder/(token(m)+'.npz')) for m in METHODS}
        for public in [False,True]:
            canvas=Image.new('RGB',(1850,4*465+70),'white');draw=ImageDraw.Draw(canvas)
            draw.text((10,5),seq+'/'+frame+' | K0 fit; K1-K3 held-out | SAME FINAL CACHES',fill='black')
            draw.text((10,25),'Purple mesh; green predicted silhouette; cyan pre-frozen RGB reference patch. NO ACUPOINT GT.',fill='black')
            for k in range(4):
                z=np.load(inputs/f'K{k}.npz');patch=cv2.imread(roi[(seq,frame,f'K{k}')]['roi_path'],0)
                for j,m in enumerate(METHODS):
                    V=variants[m]['vertices_m'];F=variants[m]['faces'];V=V if k==0 else transform_between(V,cams[0],cams[k])
                    tile=render_tile(z['rgb'],V,F,z['K'],z['dist'],z['bbox_xyxy'],patch,public)
                    td=ImageDraw.Draw(tile);r=by[(f'K{k}',m)];value=r['surface']['median_mm']
                    text=f'K{k} {m}\nposterior med {value:.2f} mm' if value is not None else f'K{k} {m}\nNO QUALIFIED POSTERIOR REFERENCE'
                    td.text((5,2),text,fill='black');canvas.paste(tile,(370*j,465*k+70))
            kind='public_prediction_figures' if public else 'private_rgb_review'
            path=a.out/kind/seq/(frame+'.jpg');path.parent.mkdir(parents=True,exist_ok=True);canvas.save(path,quality=91)
            rows.append(dict(sequence=seq,frame=frame,kind=kind,path=str(path),sha256=sha(path),
                cameras=4,methods=5,source='final NPZ, no fitting',original_rgb_included=not public))
        print('VISUALIZED',seq,frame,flush=True)
    write(a.out/'VISUALIZATION_MANIFEST.json',rows)


def recompute_first(a,contract):
    sys.path.insert(0,'/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/delivery/code')
    from surface_metrics import point_to_triangle_distances
    from metrics_v2 import ray_depth_residual
    # First three qualified held-out views in frozen order; not selected by result.
    checked=[];mask=np.array(read(a.root/'assets/candidate_posterior_mask.json')['face_ids'])
    for s in contract['frames']:
        seq,frame=s['sequence'],s['frame'];folder=a.out/'run'/seq/frame;inputs=a.out/'inputs'/seq/frame
        cams=[read_camera(a.behave/'data/calibs',seq,k) for k in range(4)]
        for k in [1,2,3]:
            z=np.load(inputs/f'K{k}.npz');idx=z['posterior_eval_idx']
            if len(idx)==0:continue
            stored=np.load(folder/f'K{k}_residual_arrays.npz');p=z['points_m'][idx]
            assert np.array_equal(idx,stored['posterior_eval_idx'])
            for m in METHODS:
                q=np.load(folder/(token(m)+'.npz'));V=transform_between(q['vertices_m'],cams[0],cams[k]);F=q['faces']
                d=point_to_triangle_distances(p,V,F[mask]);rr=ray_depth_residual(p,V,F)[0]
                assert np.array_equal(d,stored[token(m)+'_distance_m'])
                assert np.array_equal(rr,stored[token(m)+'_ray_m'],equal_nan=True)
            checked.append(dict(sequence=seq,frame=frame,camera=f'K{k}',methods=5,exact_array_match=True))
            if len(checked)==3:
                write(a.out/'CACHE_ONLY_RECOMPUTATION_CHECK.json',dict(status='PASS',rows=checked,inference=0,fit=0));return


def main(a):
    a.out=a.root/'p2_behave_crossview';contract=read(a.out/'P2_EXECUTION_CONTRACT.json')
    if a.phase=='freeze':
        write(a.out/'P2_AGGREGATION_VISUAL_FREEZE.json',dict(status='FROZEN_BEFORE_FORMAL_RESULTS',code_sha256=sha(Path(__file__)),
            primary='same posterior sensor points -> exact posterior predicted triangles',
            aggregation='heldout cameras median -> frame -> sequence median -> subject median -> equal-subject mean',
            missing='zero reference points = missing; never zero mm; no result-based sample selection',
            figures='45 frames x 4 cameras x 5 methods; all included. Original RGB server/local only. Public predictions on blank background.',
            compare='Rigid versus Rigid+D; all five also reported',source_contract_sha256=sha(a.out/'P2_EXECUTION_CONTRACT.json')))
        print('POSTPROCESS_CONTRACT_FROZEN',flush=True);return
    assert read(a.out/'P2_AGGREGATION_VISUAL_FREEZE.json')['code_sha256']==sha(Path(__file__))
    allrows=[];fallback=[]
    for s in contract['frames']:
        p=a.out/'run'/s['sequence']/s['frame'];allrows+=read(p/'evaluation.json');meta=read(p/'mesh_metadata.json')
        fallback.append(dict(**s,fallback=meta['fallback'],raw_txyz_m=meta['raw_txyz_m'],applied_txyz_m=meta['applied_txyz_m'],D_quality=meta['D_mesh_quality']))
    assert len(allrows)==900
    flat=[flatten(r) for r in allrows];save_csv(a.out/'PER_CAMERA_METHOD.csv',flat);frames=[]
    for s in contract['frames']:
        for m in METHODS:
            rr=[r for r in flat if r['sequence']==s['sequence'] and r['frame']==s['frame'] and r['method']==m and r['camera']!='K0' and r['posterior_point_count']>0]
            frames.append(dict(subject=s['subject'],sequence=s['sequence'],frame=s['frame'],method=m,heldout_views=len(rr),**pack(rr)))
    save_csv(a.out/'PER_FRAME_HELDOUT.csv',frames);sequences=[];subjects=[]
    for seq in sorted({s['sequence'] for s in contract['frames']}):
        for m in METHODS:
            rr=[r for r in frames if r['sequence']==seq and r['method']==m and r['heldout_views']>0]
            sub=next(s['subject'] for s in contract['frames'] if s['sequence']==seq)
            sequences.append(dict(subject=sub,sequence=seq,method=m,evaluable_frames=len(rr),**pack(rr)))
    save_csv(a.out/'PER_SEQUENCE_HELDOUT.csv',sequences)
    for sub in sorted({s['subject'] for s in contract['frames']}):
        for m in METHODS:
            rr=[r for r in sequences if r['subject']==sub and r['method']==m and r['evaluable_frames']>0]
            subjects.append(dict(subject=sub,method=m,evaluable_sequences=len(rr),**pack(rr)))
    save_csv(a.out/'PER_SUBJECT_HELDOUT.csv',subjects);overall=[]
    for m in METHODS:
        rr=[r for r in subjects if r['method']==m and r['evaluable_sequences']>0]
        overall.append(dict(method=m,evaluable_subjects=len(rr),**{key:float(np.mean([r[key] for r in rr if r[key] is not None])) if any(r[key] is not None for r in rr) else None for key in KEYS}))
    paired=[]
    for s in contract['frames']:
        r=next(r for r in frames if r['sequence']==s['sequence'] and r['frame']==s['frame'] and r['method']=='Official+Rigid')
        d=next(r for r in frames if r['sequence']==s['sequence'] and r['frame']==s['frame'] and r['method']=='Official+Rigid+D')
        k0=[r for r in flat if r['sequence']==s['sequence'] and r['frame']==s['frame'] and r['camera']=='K0']
        rk=next(r for r in k0 if r['method']=='Official+Rigid');dk=next(r for r in k0 if r['method']=='Official+Rigid+D')
        h=d['surface_median_mm']-r['surface_median_mm'] if r['surface_median_mm'] is not None else None
        fit=dk['surface_median_mm']-rk['surface_median_mm'] if rk['surface_median_mm'] is not None else None
        paired.append(dict(**s,heldout_D_minus_R_median_mm=h,K0_D_minus_R_median_mm=fit,
            K0_improved_heldout_degraded=fit is not None and h is not None and fit<0 and h>0))
    write(a.out/'RIGID_D_PAIRED_AUDIT.json',paired);write(a.out/'FALLBACK_AND_MESH_QUALITY.json',fallback)
    write(a.out/'RESULTS.json',dict(status='ACTUAL_45_FRAME_CACHED_RUN_COMPLETE',frame_count=45,method_meshes=225,
        records_all_cameras=900,records_heldout=675,evaluable_heldout_views=sum(r['camera']!='K0' and r['posterior_point_count']>0 for r in allrows)//5,
        evaluable_heldout_frames=sum(r['method']=='Official' and r['heldout_views']>0 for r in frames),
        methods=overall,subject_equal_mean=True,previously_consumed_subjects=True,prone_skin_cases=0,
        Txyz_fallback_frames=sum(r['fallback'] for r in fallback),clinical_acupoint_accuracy_measured=False))
    recompute_first(a,contract)
    visuals(a,contract)
    print('AGGREGATION_AND_VISUALS_COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--behave',type=Path,required=True)
    p.add_argument('--phase',choices=['freeze','summarize'],required=True);main(p.parse_args())
