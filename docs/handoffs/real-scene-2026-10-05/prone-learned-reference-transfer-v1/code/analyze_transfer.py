"""Cache-only prone stability, paired historical cohort, full geometric and private RGB views."""
import argparse,csv,time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw
from run_transfer import BASE,OLD,read,write,sha


def span(values):
    return np.max([np.linalg.norm(values[i]-values[j],axis=1) for i,j in [(0,1),(0,2),(1,2)]],axis=0)*1000


def main(root):
    start=time.monotonic();config=read(OLD/'CONFIG.json')
    curves=read(root/'CURVE_MANIFEST.json');bindings=read(root/'BINDING_MANIFEST.json')
    historical=read(OLD/'CURVE_MANIFEST.json');historical_bind=read(OLD/'BINDING_MANIFEST.json')
    inputs=read(root/'INPUT_MANIFEST.json')
    for row in inputs+curves+bindings:
        assert sha(row['path'])==row['sha256']
    caches={r['path']:dict(np.load(r['path'])) for r in bindings}
    stability=[];initialization=[];individual=[]
    for subject in config['cohort']:
        role='dev' if subject in config['dev'] else 'consumed_test_role'
        for strategy in ['NO_BLOCK_AUG','BLOCK_AUG']:
            for mesh in config['meshes']:
                group=[r for r in bindings if r['subject']==subject and r['strategy']==strategy and r['mesh_method']==mesh]
                for model_seed in range(3):
                    selected=sorted([r for r in group if r['model_seed']==model_seed],key=lambda r:r['split_seed'])
                    points=[caches[r['path']] for r in selected]
                    q=span([z['query_m'] for z in points]);b=span([z['xyz_m'] for z in points])
                    stability.append(dict(subject=subject,role=role,strategy=strategy,mesh_method=mesh,model_seed=model_seed,
                        query_span_median_mm=float(np.median(q)),query_span_max_mm=float(q.max()),
                        bound_span_median_mm=float(np.median(b)),bound_span_max_mm=float(b.max()),
                        projection_median_mm=float(np.mean([r['projection_median_mm'] for r in selected]))))
                for split in range(3):
                    selected=sorted([r for r in group if r['split_seed']==split],key=lambda r:r['model_seed'])
                    p=span([caches[r['path']]['xyz_m'] for r in selected])
                    initialization.append(dict(subject=subject,role=role,strategy=strategy,mesh_method=mesh,split_seed=split,
                        initialization_bound_span_median_mm=float(np.median(p)),initialization_bound_span_max_mm=float(p.max())))
                selected=[r for r in stability if r['subject']==subject and r['strategy']==strategy and r['mesh_method']==mesh]
                individual.append(dict(subject=subject,role=role,strategy=strategy,mesh_method=mesh,
                    **{metric:float(np.mean([r[metric] for r in selected])) for metric in
                       ['query_span_median_mm','bound_span_median_mm','projection_median_mm']}))
    with (OLD/'STABILITY_RESULTS.csv').open() as f:old=list(csv.DictReader(f))
    paired_subjects=[r['subject'] for r in old if r['role']=='consumed_test_role' and r['curve_method']=='GROOVE_DP'
                     and r['mesh_method']=='RigidD' and r['three_seed_complete']=='True']
    assert len(paired_subjects)==12
    aggregate=[]
    for role in ['dev','consumed_test_role']:
        for strategy in ['NO_BLOCK_AUG','BLOCK_AUG']:
            for mesh in config['meshes']:
                selected=[r for r in individual if r['role']==role and r['strategy']==strategy and r['mesh_method']==mesh]
                aggregate.append(dict(role=role,strategy=strategy,mesh_method=mesh,subjects=len(selected),
                    **{metric:float(np.median([r[metric] for r in selected])) for metric in
                       ['query_span_median_mm','bound_span_median_mm','projection_median_mm']}))
    paired=[]
    for mesh in config['meshes']:
        group=[r for r in old if r['subject'] in paired_subjects and r['curve_method']=='GROOVE_DP' and r['mesh_method']==mesh]
        paired.append(dict(method='GROOVE_DP',mesh_method=mesh,subjects=12,
            query_span_median_mm=float(np.median([float(r['query_span_median_mm']) for r in group])),
            bound_span_median_mm=float(np.median([float(r['bound_span_median_mm']) for r in group])),
            projection_median_mm=float(np.median([float(r['projection_median_mm']) for r in group]))))
        for strategy in ['NO_BLOCK_AUG','BLOCK_AUG']:
            group=[r for r in individual if r['subject'] in paired_subjects and r['strategy']==strategy and r['mesh_method']==mesh]
            paired.append(dict(method=strategy,mesh_method=mesh,subjects=12,
                **{metric:float(np.median([r[metric] for r in group])) for metric in
                   ['query_span_median_mm','bound_span_median_mm','projection_median_mm']}))
    support=[]
    for strategy in ['NO_BLOCK_AUG','BLOCK_AUG']:
        group=[]
        for subject in config['cohort']:
            if subject in config['dev']:continue
            selected=[r['supported_fraction_3mm'] for r in curves if r['subject']==subject and r['strategy']==strategy]
            group.append(np.mean(selected))
        support.append(dict(strategy=strategy,subjects=16,median_mean_supported_fraction_3mm=float(np.median(group))))
    write(root/'RESULTS.json',dict(status='COMPLETE',aggregate=aggregate,paired_12=paired,paired_subjects=paired_subjects,
        per_model=stability,per_subject=individual,initialization=initialization,support=support,
        clinical_accuracy_validated=False,domain='zero-shot clothed prone, approximate camera, no target line labels'))
    for folder in ['figures','private_rgb']:(root/folder).mkdir(exist_ok=True)
    visuals=[]
    for subject in config['cohort']:
        with np.load(root/'inputs'/f'{subject}_0.npz') as z:
            depth=z['features'][0][::-1];mask=z['valid'][::-1];xs=z['xs_m'];ys=-z['ys_feature_m'][::-1]
        fig,axes=plt.subplots(1,3,figsize=(15,6));methods=['GROOVE_DP','NO_BLOCK_AUG','BLOCK_AUG']
        with np.load(BASE/'inputs'/subject/'input.npz') as inp:
            rgb=Image.fromarray(inp['rgb']);K=inp['K'].copy()
        canvas=Image.new('RGB',(rgb.width*3,rgb.height+80),'white');draw=ImageDraw.Draw(canvas)
        for column,(ax,method) in enumerate(zip(axes,methods)):
            ax.imshow(np.where(mask,depth,np.nan),origin='lower',extent=[xs[0]*1000,xs[-1]*1000,ys[0]*1000,ys[-1]*1000],cmap='gray',aspect='equal')
            canvas.paste(rgb,(column*rgb.width,80));draw.text((column*rgb.width+5,5),subject+' / '+method,fill='black')
            draw.text((column*rgb.width+5,25),'All inputs and model seeds / engineering probes',fill='black')
            draw.text((column*rgb.width+5,45),'NOT acupoints; original approximate K',fill='black')
            failures=[]
            for split,color in enumerate(['orange','limegreen','magenta']):
                if method=='GROOVE_DP':
                    cr=[r for r in historical if r['subject']==subject and r['method']==method and r['seed']==split]
                    if cr[0]['status']!='COMPLETE':failures.append(split);continue
                    entries=[(cr[0],next(r for r in historical_bind if r['subject']==subject and r['seed']==split and r['curve_method']==method and r['mesh_method']=='RigidD'),0)]
                else:
                    entries=[(next(r for r in curves if r['subject']==subject and r['strategy']==method and r['split_seed']==split and r['model_seed']==m),
                              next(r for r in bindings if r['subject']==subject and r['strategy']==method and r['split_seed']==split and r['model_seed']==m and r['mesh_method']=='RigidD'),m) for m in range(3)]
                for curve_row,bound_row,m in entries:
                    assert sha(curve_row['path'])==curve_row['sha256'];assert sha(bound_row['path'])==bound_row['sha256']
                    with np.load(curve_row['path']) as z:q=z['curve_m']
                    with np.load(bound_row['path']) as z:b=z['xyz_m']
                    ax.plot(q[:,0]*1000,q[:,1]*1000,color=color,ls=['-','--',':'][m],alpha=.7,lw=1)
                    ax.scatter(b[:,0]*1000,b[:,1]*1000,color=color,s=12,marker='x')
                    uv=b@K.T;uv=uv[:,:2]/uv[:,2,None]
                    pixels=[(float(x)+column*rgb.width,float(y)+80) for x,y in uv]
                    draw.line(pixels,fill=color,width=2)
                    for x,y in pixels:draw.ellipse((x-3,y-3,x+3,y+3),outline=color,width=2)
            ax.invert_yaxis();ax.set_xlabel('Camera X / mm');ax.set_ylabel('Camera Y / mm')
            ax.set_title(method+('\nFailed input splits: '+str(failures) if failures else ''))
        fig.suptitle(subject+' / camera XY orthographic diagnostic, NOT RGB overlay\nColors: input0 orange, input1 green, input2 magenta; styles: model0/1/2; crosses: RigidD targets; NOT acupoints')
        fig.tight_layout();path=root/'figures'/(subject+'.png');fig.savefig(path,dpi=110);plt.close(fig)
        private=root/'private_rgb'/(subject+'.jpg');canvas.save(private,quality=90)
        visuals.append(dict(subject=subject,geometry_path=str(path),geometry_sha256=sha(path),private_rgb_path=str(private),private_rgb_sha256=sha(private)))
    write(root/'VISUALIZATION_MANIFEST.json',visuals)
    for r in read(root/'SOURCE_FREEZE.json'):assert sha(r['path'])==r['sha256']
    write(root/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',frozen_source_assets=len(read(root/'SOURCE_FREEZE.json')),
        curves_verified=len(curves),bindings_verified=len(bindings),source_unchanged=True,figures=20,private_rgb_figures=20))
    print('TRANSFER_ANALYSIS_COMPLETE',dict(seconds=time.monotonic()-start,paired_12=paired,support=support),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
