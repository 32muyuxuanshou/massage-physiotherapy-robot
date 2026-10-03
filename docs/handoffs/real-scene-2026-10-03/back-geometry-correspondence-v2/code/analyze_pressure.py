"""Cache-only metrics, neutral ENG transfer, full-cohort prediction figures."""
import sys,csv
import cv2,numpy as np
from PIL import Image,ImageDraw
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT,BASE,OLD,METHODS,read,write,sha,token
sys.path[:0]=[str(BASE/'delivery/code'),str(OLD/'code')]
from run_cached_point_diagnostics import interpolate,local_quality
from data_v2 import project
from l1_fit import edges

OUT=ROOT/'c_pressure_normal'

def csv_save(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def quality(V,W,F):
    t0=V[F];t1=W[F]
    n0=np.cross(t0[:,1]-t0[:,0],t0[:,2]-t0[:,0]);n1=np.cross(t1[:,1]-t1[:,0],t1[:,2]-t1[:,0])
    a0=np.linalg.norm(n0,axis=1);a1=np.linalg.norm(n1,axis=1);good=a0>1e-12
    dot=np.einsum('ij,ij->i',n0,n1)
    angle=np.degrees(np.arccos(np.clip(dot/(a0*a1+1e-30),-1,1)))
    E=edges(F);l0=np.linalg.norm(V[E[:,1]]-V[E[:,0]],axis=1);l1=np.linalg.norm(W[E[:,1]]-W[E[:,0]],axis=1)
    strain=np.abs(l1/l0-1)
    return dict(edge_strain_p99=float(np.percentile(strain,99)),edge_strain_max=float(strain.max()),
        normal_reversal_count=int((dot<0).sum()),normal_angle_p95_deg=float(np.percentile(angle,95)),
        degenerate_faces=int((a1<1e-12).sum()),area_ratio_p01=float(np.percentile(a1[good]/a0[good],1)),
        area_ratio_p99=float(np.percentile(a1[good]/a0[good],99)),
        self_intersection_test='NOT_IMPLEMENTED; normal reversal is only a proxy')

def extract(row):
    p=row['posterior'];return dict(median_mm=p['d3d']['median_mm'],p95_mm=p['d3d']['p95_mm'],
        coverage_50mm=p['d3d']['coverage_50mm'],ray_hit=p['ray_hit_fraction'],
        common_ray_median_mm=p['ray_common_hit_absolute']['median_mm'],
        silhouette_iou=row['silhouette']['iou'],boundary_p95_px=row['silhouette']['boundary_p95_px'],
        edge_strain_p99=row['mesh_quality']['edge_strain_p99'])

def main():
    cfg=read(OUT/'EXECUTION_CONTRACT.json');atlas=read(ROOT/'a_atlas/ENGINEERING_BACK_ATLAS_V2.json');records=atlas['records']
    rows=[];movement=[];points=[];public=[];qualities=[]
    (OUT/'public_visuals').mkdir(exist_ok=True)
    for s in cfg['subjects']:
        rs=read(OUT/'evaluation'/s/'results.json')
        for row in rs:
            metric=np.load(OUT/'evaluation'/s/f"seed_{row['seed']}"/(token(row['method'])+'_metrics.npz'))
            row['posterior']['d3d']['coverage_50mm']=float(np.mean(metric['posterior_d3d_m']<=.05))
        rows.extend(rs)
        inp=np.load(OUT/'inputs'/s/'input.npz');K=inp['K'];cloud=inp['points_m'];h,w=inp['rgb'].shape[:2]
        for seed in cfg['seeds']:
            split=np.load(OUT/'inputs'/s/f'split_{seed}.npz');F=None;variants={};ps={}
            for m in METHODS:
                z=np.load(OUT/'meshes'/s/f'seed_{seed}'/(token(m)+'.npz'));variants[m]=z['vertices_m'];F=z['faces']
                ps[m]=interpolate(variants[m],F,records)
                for j,rec in enumerate(records):points.append(dict(subject=s,seed=seed,method=m,id=rec['id'],
                    face_id=rec['face_id'],barycentric=rec['barycentric'],xyz_m=ps[m][0][j].tolist(),
                    normal=ps[m][1][j].tolist(),medical_truth=False))
            v0=variants['Official+Rigid'];p0,n0,_=ps['Official+Rigid'];uv0=project(p0,K)
            train=cloud[split['train_idx']];held=cloud[split['posterior_eval_idx']]
            for m in METHODS[2:]:
                p,n,area=ps[m];d=p-p0;signed=np.sum(d*n0,axis=1);tangent=d-signed[:,None]*n0
                q=quality(v0,variants[m],F);qualities.append(dict(subject=s,seed=seed,method=m,**q))
                near_train=cKDTree(train).query(p)[0]*1000;near_held=cKDTree(held).query(p)[0]*1000
                for j,rec in enumerate(records):
                    patch=np.flatnonzero(np.isin(F,F[rec['face_id']]).any(1))
                    local=local_quality(v0,variants[m],F,patch)
                    movement.append(dict(subject=s,split='dev' if s in cfg['dev'] else 'test',seed=seed,method=m,id=rec['id'],
                        total_mm=float(np.linalg.norm(d[j])*1000),normal_mm=float(abs(signed[j])*1000),
                        tangent_mm=float(np.linalg.norm(tangent[j])*1000),
                        normal_angle_deg=float(np.degrees(np.arccos(np.clip(np.dot(n[j],n0[j]),-1,1)))),
                        image_movement_px=float(np.linalg.norm(project(p,K)[j]-uv0[j])),
                        nearest_train_point_mm=float(near_train[j]),nearest_posterior_heldout_point_mm=float(near_held[j]),
                        nearby_sensor_support_is_not_point_accuracy=True,local_quality=local))
            # Every person and seed: predicted mask plus neutral ENG points, no dataset RGB redistribution.
            page=Image.new('RGB',(4*w,h+90),'white');draw=ImageDraw.Draw(page)
            for col,m in enumerate(METHODS):
                dep=np.load(OUT/'visualizations'/s/f'seed_{seed}'/(token(m)+'_render.npz'))['depth_m'];mask=dep>0
                rgb=np.full((h,w,3),255,np.uint8);rgb[mask]=(221,100,170)
                contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(rgb,contours,-1,(20,160,45),1)
                for j,uv in enumerate(project(ps[m][0],K)):
                    x,y=np.rint(uv).astype(int)
                    if 0<=x<w and 0<=y<h:
                        cv2.circle(rgb,(x,y),4,(255,220,0),-1);cv2.putText(rgb,str(j+1),(x+5,y),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,0),1)
                page.paste(Image.fromarray(rgb),(col*w,90));draw.text((col*w+6,5),s+f' seed{seed} '+m,fill='black')
                rr=next(r for r in rs if r['seed']==seed and r['method']==m)
                draw.text((col*w+6,25),f"Back med/P95 {rr['posterior']['d3d']['median_mm']:.2f}/{rr['posterior']['d3d']['p95_mm']:.2f} mm",fill='black')
                draw.text((col*w+6,45),'Prediction only / approximate K / not medical GT',fill='black')
                draw.text((col*w+6,63),'Yellow = ENG neutral surface probe',fill='black')
            file=OUT/'public_visuals'/f'{s}_seed{seed}.jpg';page.save(file,quality=93)
            public.append(dict(subject=s,seed=seed,path=str(file),sha256=sha(file),source_meshes=[
                dict(method=m,path=str(OUT/'meshes'/s/f'seed_{seed}'/(token(m)+'.npz')),sha256=sha(OUT/'meshes'/s/f'seed_{seed}'/(token(m)+'.npz'))) for m in METHODS]))
    assert len(rows)==240 and len(points)==1920 and len(movement)==960 and len(public)==60
    write(OUT/'ALL_METHOD_RESULTS.json',rows);write(OUT/'ENG_POINTS_1920.json',points)
    write(OUT/'ENG_MOVEMENT_960.json',movement);write(OUT/'GEOMETRY_QUALITY_120.json',qualities)
    write(OUT/'PUBLIC_VISUAL_MANIFEST.json',public)
    per=[]
    for s in cfg['subjects']:
        for m in METHODS:
            r=[extract(x) for x in rows if x['subject']==s and x['method']==m]
            d={k:float(np.mean([x[k] for x in r])) for k in r[0]}
            move=[x for x in movement if x['subject']==s and x['method']==m]
            if move:
                for k in ['total_mm','normal_mm','tangent_mm','normal_angle_deg','image_movement_px']:
                    # Seed average of per-seed medians across 8 neutral points.
                    d['eng_'+k]=float(np.mean([np.median([x[k] for x in move if x['seed']==seed]) for seed in cfg['seeds']]))
            per.append(dict(subject=s,split='dev' if s in cfg['dev'] else 'test',method=m,**d))
    agg=[]
    for role in ['dev','test']:
        for m in METHODS:
            subset=[x for x in per if x['split']==role and x['method']==m]
            agg.append(dict(split=role,method=m,subjects=len(subset),
                **{k:float(np.median([x[k] for x in subset])) for k in subset[0] if k not in ['subject','split','method']}))
    pairs=[]
    for s in cfg['subjects']:
        v=next(x for x in per if x['subject']==s and x['method']==METHODS[2]);n=next(x for x in per if x['subject']==s and x['method']==METHODS[3]);r=next(x for x in per if x['subject']==s and x['method']==METHODS[1])
        pairs.append(dict(subject=s,split=n['split'],normal_minus_vector_median_mm=n['median_mm']-v['median_mm'],
            normal_minus_vector_p95_mm=n['p95_mm']-v['p95_mm'],normal_minus_vector_iou=n['silhouette_iou']-v['silhouette_iou'],
            normal_minus_vector_edge_p99=n['edge_strain_p99']-v['edge_strain_p99'],
            normal_minus_vector_eng_tangent_mm=n['eng_tangent_mm']-v['eng_tangent_mm'],
            normal_minus_rigid_median_mm=n['median_mm']-r['median_mm'],normal_minus_rigid_iou=n['silhouette_iou']-r['silhouette_iou']))
    write(OUT/'AGGREGATED_RESULTS.json',dict(status='COMPLETE',aggregation='seed arithmetic mean -> subject -> role subject median',
        per_subject=per,role_summary=agg,paired_person_differences=pairs,previously_consumed_subjects=True,
        independent_sensor=False,medical_accuracy_validated=False))
    csv_save(OUT/'PER_SUBJECT_RESULTS.csv',per);csv_save(OUT/'PAIRED_PERSON_DELTAS.csv',pairs)
    # All subjects, no favorable-case selection.
    fig,axes=plt.subplots(1,3,figsize=(17,6));x=np.arange(20)
    for m in METHODS[1:]:
        subset=[next(r for r in per if r['subject']==s and r['method']==m) for s in cfg['subjects']]
        for ax,k in zip(axes,['median_mm','silhouette_iou','edge_strain_p99']):ax.plot(x,[r[k] for r in subset],'o-',ms=4,label=m)
    for ax,k in zip(axes,['same-source back distance (mm)','projected support IoU','global edge strain P99']):
        ax.set_ylabel(k);ax.set_xticks(x,cfg['subjects'],rotation=90,fontsize=8);ax.legend(fontsize=6)
    fig.suptitle('20 previously consumed subjects / seed mean / no independent sensor or acupoint accuracy claim')
    fig.tight_layout();fig.savefig(OUT/'public_visuals/ALL_SUBJECT_COMPARISON.png',dpi=140);plt.close(fig)
    print('ANALYSIS_COMPLETE',240,1920,960,60,flush=True)
    for r in agg:print(r,flush=True)

if __name__=='__main__':main()
