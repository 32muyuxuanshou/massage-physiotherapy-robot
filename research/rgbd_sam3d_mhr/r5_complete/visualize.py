"""All real frame/seed panels from cached meshes; no inference or refitting."""
import os
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json,sys
from pathlib import Path
import numpy as np
import torch
import nvdiffrast.torch as dr
from PIL import Image,ImageDraw,ImageOps
import matplotlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'r5_camera_only'))
from visualize_scan import shading

def project(points,K):return (points@K.T)[:,:2]/points[:,2:]
def overlay(rgb,mesh,faces,K,ctx):
    hit,intensity=shading(ctx,mesh,faces,K,*rgb.shape[:2]);out=rgb.astype(float).copy()
    out[hit]=.3*out[hit]+.7*intensity[hit,None]*np.array([65,185,235])
    return np.uint8(np.clip(out,0,255))
def dots(rgb,uv,colours):
    out=Image.fromarray(rgb.copy());draw=ImageDraw.Draw(out)
    for (u,v),colour in zip(uv,colours):
        if np.isfinite(u+v):draw.ellipse((u-2,v-2,u+2,v+2),fill=tuple(map(int,colour)))
    return np.asarray(out)
def box(uv,h,w):
    lo=uv.min(0);hi=uv.max(0);pad=.1*max(hi-lo)
    return (max(0,int(lo[0]-pad)),max(0,int(lo[1]-pad)),min(w,int(hi[0]+pad)),min(h,int(hi[1]+pad)))
def panel(image,crop):return ImageOps.pad(Image.fromarray(image).crop(crop),(320,340),color='white')

def main(a):
    torch.set_num_threads(2);r=a.root;original=Path('/root/autodl-tmp/rgbd_sam3d')
    history=r/'assets/real_evaluation'
    rows=json.loads((original/'datasets/cache/humman_development_v1/CACHE_MANIFEST.json').read_text())['records']
    faces=np.load(history/'assets/original_assets/official/faces.npy');ctx=dr.RasterizeCudaContext()
    baseline=json.loads((r/'evaluation/official/real_B/RESULTS.json').read_text())
    off={x['key']:x for x in baseline['records']};out=r/'visualizations';out.mkdir(exist_ok=True);public=out/'public';public.mkdir(exist_ok=True)
    records=[];cmap=matplotlib.colormaps['inferno'];first={}
    for row in rows:first.setdefault(row['identity'],f"{row['sequence']}_{row['frame']:06d}")
    for seed in [11,23,37]:
        modes=['rgb_only','residual','cross_attention','g1','pooled_mlp','coarse','full']
        lookup={m:{v['key']:v for v in json.loads((r/'evaluation'/f'{m}_s{seed}_best/real_B/RESULTS.json').read_text())['records']} for m in modes}
        worst={}
        for row in rows:
            key=f"{row['sequence']}_{row['frame']:06d}";score=lookup['full'][key]['triangle']['p95_mm']
            if row['identity'] not in worst or score>worst[row['identity']][0]:worst[row['identity']]=(score,key)
        for row in rows:
            key=f"{row['sequence']}_{row['frame']:06d}";aa=np.load(original/'datasets/registered_v1'/row['views']['kinect_000']['file']);bb=np.load(original/'datasets/registered_v1'/row['views']['kinect_001']['file'])
            inputs=np.load(history/'assets/original_assets/inputs'/(key+'.npz'));pb=np.load(history/'assets/datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
            ua=project(inputs['points_camera_A'],aa['K']);ub=project(pb,bb['K']);crops=[box(ua,*aa['rgb'].shape[:2]),box(ub,*bb['rgb'].shape[:2])]
            base_mesh=np.load(history/'assets/original_assets/official'/(key+'.npz'))['vertices_camera_A']
            meshes={'Official':base_mesh,'Official+Txyz':base_mesh+np.asarray(off[key]['applied_translation_m'])}
            mesh_rows={'Official':off[key]['triangle'],'Official+Txyz':off[key]['triangle_txyz']}
            dd=np.load(r/'evaluation/official/real_B/distances'/(key+'.npz'));distances={'Official':dd['raw_mm'],'Official+Txyz':dd['Official_Txyz_mm']}
            for m in modes:
                meshes[m]=np.load(r/'evaluation'/f'{m}_s{seed}_best/real/predictions'/(key+'.npz'))['vertices_camera_A']
                distances[m]=np.load(r/'evaluation'/f'{m}_s{seed}_best/real_B/distances'/(key+'.npz'))['raw_mm'];mesh_rows[m]=lookup[m][key]['triangle']
            for group,names in [('core',['Official','Official+Txyz','g1','coarse','full']),('controls',['Official','rgb_only','residual','cross_attention','pooled_mlp'])]:
                canvas=Image.new('RGB',(1920,798),'white');draw=ImageDraw.Draw(canvas)
                draw.text((8,6),f'{key} | seed{seed} | cached meshes; no refitting | BLUE=predicted surface; B colour cap150mm',fill='black')
                inputA=dots(aa['rgb'],ua[::5],np.tile([255,160,0],(len(ua[::5]),1)));inputB=dots(bb['rgb'],ub,np.tile([255,160,0],(len(ub),1)))
                canvas.paste(panel(inputA,crops[0]),(0,48));canvas.paste(panel(inputB,crops[1]),(0,436))
                draw.text((8,27),'Camera A RGB + measured points',fill='black');draw.text((8,402),'Camera B independent points',fill='black')
                for col,name in enumerate(names,1):
                    painted=overlay(aa['rgb'],meshes[name],faces,aa['K'],ctx)
                    heat=dots(bb['rgb'],ub,np.uint8(cmap(np.clip(distances[name]/150,0,1))[:,:3]*255))
                    canvas.paste(panel(painted,crops[0]),(col*320,48));canvas.paste(panel(heat,crops[1]),(col*320,436))
                    mm=mesh_rows[name];draw.text((col*320+5,27),name,fill='black')
                    draw.text((col*320+5,402),f"B med {mm['median_mm']:.2f} / P95 {mm['p95_mm']:.2f} mm",fill='black')
                filename=f'{key}_s{seed}_{group}.jpg';canvas.save(out/filename,quality=91)
                keep=group=='core' and key in [first[row['identity']],worst[row['identity']][1]]
                if keep:canvas.save(public/filename,quality=91)
                records.append(dict(key=key,identity=row['identity'],role=row['role'],seed=seed,group=group,file=filename,public=keep,
                    evidence='A perspective overlay + frozen B exact triangle residual; same cached final meshes',
                    displayed_resize='aspect-preserving display crop letterboxed to320x340 AFTER original-K rendering; not inference preprocessing'))
            print('REAL_FRAME_VISUAL',seed,key,flush=True)
    assert len(records)==1392
    paths=json.loads((r/'PATHS.json').read_text());scan_source=Path(json.loads((r/'SCAN_SOURCE_READY.json').read_text())['data_root'])
    for domain,source in [('native',original/'datasets/synthetic/native_scale_v2'),('scan',scan_source)]:
        manifest=json.loads((Path(paths[domain+'_cache'])/'CACHE_MANIFEST.json').read_text())['records']
        selected=[row for row in manifest if row['role']=='VAL'];first={}
        for row in selected:first.setdefault(row['identity'],Path(row['cache_file']).stem)
        for seed in [11,23,37]:
            lookup={m:{v['sample_id']:v for v in json.loads((r/'evaluation'/f'{m}_s{seed}_best'/domain/'RESULTS.json').read_text())['records']} for m in modes}
            worst={}
            for row in selected:
                key=Path(row['cache_file']).stem;value=lookup['full'][key]
                score=value['metrics']['vertex_camera_mm'] if domain=='native' else value['full_mask_p95_mm']
                if row['identity'] not in worst or score>worst[row['identity']][0]:worst[row['identity']]=(score,key)
            for row in selected:
                key=Path(row['cache_file']).stem;z=np.load(source/row['file']);rgb=z['rgb'];K=z['K'];crop=(0,0,rgb.shape[1],rgb.shape[0])
                cached=torch.load(Path(paths[domain+'_cache'])/row['cache_file'],map_location='cpu',weights_only=False)
                gt=[]
                if domain=='native':gt=[('native GT',(cached['truth']['pred_vertices']+cached['truth']['pred_cam_t'][:,None])[0].numpy())]
                original_mesh=np.load(r/'evaluation/official'/domain/'predictions'/(key+'.npz'))['vertices_camera_A']
                specs=gt+[('Official',original_mesh)]+[(m,np.load(r/'evaluation'/f'{m}_s{seed}_best'/domain/'predictions'/(key+'.npz'))['vertices_camera_A']) for m in modes]
                canvas=Image.new('RGB',(1600,800),'white');draw=ImageDraw.Draw(canvas)
                draw.text((8,6),f'{domain} {key} | seed{seed} | actual cached mesh | BLUE=rendered mesh | original K',fill='black')
                tiles=[('RGB',rgb)]+[(name,overlay(rgb,mesh,faces,K,ctx)) for name,mesh in specs]
                for i,(name,image) in enumerate(tiles):
                    xx=(i%5)*320;yy=28+(i//5)*380;canvas.paste(panel(image,crop),(xx,yy+24));draw.text((xx+5,yy+4),name,fill='black')
                filename=f'{domain}_{key}_s{seed}.jpg';canvas.save(out/filename,quality=91)
                keep=key in [first[row['identity']],worst[row['identity']][1]]
                if keep:canvas.save(public/filename,quality=91)
                records.append(dict(dataset=domain,key=key,identity=row['identity'],role='VAL',seed=seed,file=filename,public=keep,
                    evidence='source RGB and cached full native mesh at original perspective K; GT shown only for native MHR'))
        print('SYNTHETIC_VISUAL_COMPLETE',domain,len(selected)*3,flush=True)
    assert len(records)==4896
    (out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(records=records,
        selection='private all232 real frames/all3 seeds/two panels and all1168 synthetic VAL images/all3 seeds; public first and worst full-model frame per identity/seed, never best-seed selection',
        camera_B_fit=False,TEST_read=False),indent=2))
    (r/'VISUALIZE_COMPLETE.json').write_text(json.dumps(dict(status='PASS',private_panels=4896,public_panels=sum(x['public'] for x in records)),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
