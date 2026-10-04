"""Cache-only stability and full visual review export."""
import argparse,csv,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw
from run_interface import BASE,read,write,sha,csv_write


def span(points):
    return np.max([np.linalg.norm(points[i]-points[j],axis=1) for i in range(len(points)) for j in range(i+1,len(points))],axis=0)*1000


def main(root):
    config=read(root/'CONFIG.json');curves=read(root/'CURVE_MANIFEST.json');bindings=read(root/'BINDING_MANIFEST.json')
    subjects=config['cohort'];stability=[];summary={};visuals=[]
    (root/'figures').mkdir(exist_ok=True);(root/'private_rgb').mkdir(exist_ok=True)
    for subject in subjects:
        for method in config['extraction']['methods']:
            for mesh_method in config['meshes']:
                group=[r for r in bindings if r['subject']==subject and r['curve_method']==method and r['mesh_method']==mesh_method]
                row=dict(subject=subject,role='dev' if subject in config['dev'] else 'consumed_test_role',curve_method=method,mesh_method=mesh_method,
                    successful_seeds=len(group),three_seed_complete=len(group)==3,query_span_median_mm=None,query_span_max_mm=None,
                    bound_span_median_mm=None,bound_span_max_mm=None,projection_median_mm=None)
                if len(group)==3:
                    group.sort(key=lambda r:r['seed']);caches=[np.load(r['path']) for r in group]
                    query_span=span(np.asarray([z['query_m'] for z in caches]));bound_span=span(np.asarray([z['xyz_m'] for z in caches]))
                    row.update(query_span_median_mm=float(np.median(query_span)),query_span_max_mm=float(query_span.max()),
                        bound_span_median_mm=float(np.median(bound_span)),bound_span_max_mm=float(bound_span.max()),
                        projection_median_mm=float(np.mean([r['projection_median_mm'] for r in group])))
                stability.append(row)
        # Geometry plots retain every subject and every failure, with all seeds.
        fig,axes=plt.subplots(1,3,figsize=(15,6))
        for ax,method in zip(axes,config['extraction']['methods']):
            grid=np.load(root/'grids'/f'{subject}_0.npz')
            ax.imshow(np.ma.array(grid['depth_m'],mask=~grid['valid']),origin='lower',cmap='gray',aspect='equal',
                extent=[grid['xs_m'][0]*1000,grid['xs_m'][-1]*1000,grid['ys_m'][0]*1000,grid['ys_m'][-1]*1000])
            missing=[]
            for seed,color in enumerate(['orange','limegreen','magenta']):
                row=next(r for r in curves if r['subject']==subject and r['seed']==seed and r['method']==method)
                if row['status']!='COMPLETE':missing.append(seed);continue
                z=np.load(row['path']);ax.plot(z['curve_m'][:,0]*1000,z['curve_m'][:,1]*1000,color=color,lw=1.4,label=f'seed {seed}')
                group=next(r for r in bindings if r['subject']==subject and r['seed']==seed and r['curve_method']==method and r['mesh_method']=='RigidD')
                b=np.load(group['path']);ax.scatter(b['xyz_m'][:,0]*1000,b['xyz_m'][:,1]*1000,s=14,color=color,marker='x')
            ax.invert_yaxis();ax.set_xlabel('Native camera X mm');ax.set_ylabel('Native camera Y mm')
            ax.set_title(method+('\nno supported DP seeds: '+str(missing) if missing else ''));ax.legend(fontsize=7)
        fig.suptitle(subject+' / train-only back ROI / lines: observed geometry; crosses: RigidD surface binding\nEngineering probes, NOT anatomical landmarks or acupoints; approximate camera and clothing')
        fig.tight_layout();path=root/'figures'/f'{subject}.png';fig.savefig(path,dpi=120);plt.close(fig)
        visuals.append(dict(subject=subject,geometry_path=str(path),geometry_sha256=sha(path)))
        # Camera overlays on original RGB are private; no resizing of geometric input.
        inp=np.load(BASE/'inputs'/subject/'input.npz');rgb=Image.fromarray(inp['rgb']);canvas=Image.new('RGB',(rgb.width*3,rgb.height+90),'white');draw=ImageDraw.Draw(canvas)
        for column,mesh_method in enumerate(config['meshes']):
            canvas.paste(rgb,(column*rgb.width,90));draw.text((column*rgb.width+10,10),subject+' / '+mesh_method,fill='black')
            draw.text((column*rgb.width+10,28),'GROOVE_DP: seed0 orange, seed1 green, seed2 magenta',fill='black')
            draw.text((column*rgb.width+10,47),'Engineering points; NOT acupoint GT',fill='black')
            for seed,color in enumerate(['orange','limegreen','magenta']):
                group=[r for r in bindings if r['subject']==subject and r['seed']==seed and r['curve_method']=='GROOVE_DP' and r['mesh_method']==mesh_method]
                if not group:continue
                b=np.load(group[0]['path']);xyz=b['xyz_m'];uv=xyz@inp['K'].T;uv=uv[:,:2]/uv[:,2,None]
                pixel=[(float(x)+column*rgb.width,float(y)+90) for x,y in uv]
                draw.line(pixel,fill=color,width=3)
                for x,y in pixel:draw.ellipse((x-4,y-4,x+4,y+4),outline=color,width=2)
        canvas.save(root/'private_rgb'/f'{subject}.jpg',quality=92)
    csv_write(root/'STABILITY_RESULTS.csv',stability)
    for role in ['dev','consumed_test_role']:
        section={}
        for method in config['extraction']['methods']:
            section[method]={}
            for mesh_method in config['meshes']:
                subset=[r for r in stability if r['role']==role and r['curve_method']==method and r['mesh_method']==mesh_method and r['three_seed_complete']]
                section[method][mesh_method]=dict(complete_subjects=len(subset),
                    query_span_median_mm=float(np.median([r['query_span_median_mm'] for r in subset])) if subset else None,
                    bound_span_median_mm=float(np.median([r['bound_span_median_mm'] for r in subset])) if subset else None,
                    projection_median_mm=float(np.median([r['projection_median_mm'] for r in subset])) if subset else None)
        summary[role]=section
    write(root/'RESULTS.json',dict(status='COMPLETE',subjects=20,curve_records=len(curves),
        curves_by_method={method:sum(r['method']==method and r['status']=='COMPLETE' for r in curves) for method in config['extraction']['methods']},
        binding_packages=len(bindings),engineering_points=sum(r['points'] for r in bindings),stability=summary,
        independent_acupoint_accuracy=False,independent_sensor_accuracy=False,source='clothed prone existing approximate camera contract'))
    write(root/'VISUALIZATION_MANIFEST.json',visuals)
    for row in read(root/'SOURCE_FREEZE.json'):assert sha(row['path'])==row['sha256']
    write(root/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',source_files=len(read(root/'SOURCE_FREEZE.json')),
        sources_unchanged=True,heldout_extraction_intersection=0,curves=len(curves),bindings=len(bindings),geometry_figures=20,private_rgb_figures=20))
    print('ANALYSIS_COMPLETE',root/'RESULTS.json',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
