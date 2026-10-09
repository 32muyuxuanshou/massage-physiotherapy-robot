"""Summarise all seeds and draw cached predictions, including fixed failure cases."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import pyrender
import torch
import trimesh


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();formal=a.out/'formal';summary=json.loads((formal/'MULTISEED_SUMMARY.json').read_text())
    config=json.loads((formal/'EXECUTION_IDENTITY.json').read_text())['config']
    figures=a.out/'visualizations';figures.mkdir(exist_ok=True)
    methods=config['methods'];colours={'rgb_only':'#e38c23','residual':'#239954','cross_attention':'#895db1'}
    fig,axes=plt.subplots(2,3,figsize=(15,8),constrained_layout=True)
    for mode in methods:
        for seed in config['train_seeds']:
            curves=json.loads((formal/'training'/f'{mode}_seed{seed}'/'CURVES.json').read_text())
            for ax,key in zip(axes.flat,['train_loss','vertex_camera_mm','vertex_translation_removed_mm','camera_mm','joint_camera_mm','depth_common_median_mm']):
                ax.plot([r['epoch'] for r in curves],[r['train_loss'] if key=='train_loss' else r['val'][key] for r in curves],
                    color=colours[mode],alpha=.7,label=f'{mode} seed{seed}')
                ax.set_title(key);ax.set_xlabel('epoch');ax.grid(alpha=.2)
    axes.flat[0].legend(fontsize=7);fig.savefig(figures/'training_curves_all_seeds.png',dpi=150);plt.close(fig)
    paired={}
    for mode in ['residual','cross_attention']:
        differences=[]
        for seed in config['train_seeds']:
            rgb=next(r for r in summary['runs'] if r['mode']=='rgb_only' and r['seed']==seed)
            depth=next(r for r in summary['runs'] if r['mode']==mode and r['seed']==seed)
            differences.append(dict(seed=seed,vertex_camera_delta_mm=depth['best']['vertex_camera_mm']-rgb['best']['vertex_camera_mm']))
        values=[r['vertex_camera_delta_mm'] for r in differences]
        paired[mode]=dict(per_seed=differences,mean_delta_mm=float(np.mean(values)),sample_std_mm=float(np.std(values,ddof=1)),
            better_than_rgb_seeds=int(sum(x<0 for x in values)),interpretation='paired depth minus RGB; negative better; n=3 seeds, no acceptance/significance claim')
    (a.out/'PAIRED_SEED_COMPARISONS.json').write_text(json.dumps(paired,indent=2))
    depth_summary={}
    for mode in ['residual','cross_attention']:
        ablated={seed:json.loads((formal/'training'/f'{mode}_seed{seed}'/'DEPTH_ABLATIONS.json').read_text()) for seed in config['train_seeds']}
        depth_summary[mode]={}
        for kind in ablated[config['train_seeds'][0]]:
            depth_summary[mode][kind]=dict(per_seed={seed:dict(metrics=ablated[seed][kind]['identity_equal_mean'],
                output_change=ablated[seed][kind]['output_change_identity_equal_mean']) for seed in config['train_seeds']},
                vertex_camera_mean_mm=float(np.mean([ablated[s][kind]['identity_equal_mean']['vertex_camera_mm'] for s in config['train_seeds']])),
                vertex_camera_sample_std_mm=float(np.std([ablated[s][kind]['identity_equal_mean']['vertex_camera_mm'] for s in config['train_seeds']],ddof=1)))
    (a.out/'DEPTH_ABLATION_MULTISEED_SUMMARY.json').write_text(json.dumps(depth_summary,indent=2))
    real={}
    official=json.loads((a.out/'real/official/HUMMAN_RESULTS.json').read_text())
    real['official']={role:x['identity_equal_mean'] for role,x in official['results'].items()}
    for run in summary['runs']:
        key=f"{run['mode']}_seed{run['seed']}"
        rr=json.loads((formal/'real'/key/'HUMMAN_RESULTS.json').read_text())
        real[key]={role:x['identity_equal_mean'] for role,x in rr['results'].items()}
    (a.out/'HUMMAN_DEVELOPMENT_SUMMARY.json').write_text(json.dumps(real,indent=2))
    # All 50 VAL identities get one fixed posterior view per seed. Worst-case
    # selection adds examples; never substitutes for the full fixed coverage.
    data=a.root/'datasets/synthetic/native_scale_v2'
    manifest=json.loads((data/'MANIFEST.json').read_text());val=[r for r in manifest['samples'] if r['role']=='VAL']
    fixed=[r for r in val if r['pose_id']==1 and r['camera_id']==2]
    font=ImageFont.truetype('DejaVuSans.ttf',16);renderer=pyrender.OffscreenRenderer(640,480)
    faces=np.load(data/'faces.npy');visual_rows=[]
    for seed in config['train_seeds']:
        maps={mode:{r['file']:r['metrics'] for r in json.loads((formal/'training'/f'{mode}_seed{seed}'/'BEST_VAL.json').read_text())['records']} for mode in methods}
        worst=sorted(val,key=lambda r:max(maps[m][r['file']]['vertex_camera_mm'] for m in methods),reverse=True)[:8]
        selected={r['file']:r for r in fixed+worst}
        for row in selected.values():
            with np.load(data/row['file']) as z:rgb=z['rgb'];K=z['K']
            panel=Image.new('RGB',(640*4,520),'white');draw=ImageDraw.Draw(panel);panel.paste(Image.fromarray(rgb),(0,40))
            draw.text((12,10),f"{row['file']} SYNTHETIC VAL",font=font,fill='black')
            for i,mode in enumerate(methods,1):
                cached=torch.load(formal/'training'/f'{mode}_seed{seed}'/'predictions/best'/(Path(row['file']).stem+'.pt'),map_location='cpu',weights_only=False)
                vertices=(cached['pred_vertices']+cached['pred_cam_t'][:,None])[0].numpy()
                material=pyrender.MetallicRoughnessMaterial(baseColorFactor=[*matplotlib.colors.to_rgb(colours[mode]),1],metallicFactor=0,roughnessFactor=.8)
                scene=pyrender.Scene(bg_color=[0,0,0,0],ambient_light=[.7]*3)
                scene.add(pyrender.Mesh.from_trimesh(trimesh.Trimesh(vertices,faces,process=False),material=material,smooth=True))
                pose=np.diag([1.,-1.,-1.,1.])
                scene.add(pyrender.IntrinsicsCamera(K[0,0],K[1,1],K[0,2]+.5,K[1,2]+.5,znear=.05,zfar=20),pose=pose)
                scene.add(pyrender.DirectionalLight(color=np.ones(3),intensity=2),pose=pose)
                colour,depth=renderer.render(scene);overlay=rgb.copy();hit=depth>0
                overlay[hit]=(.35*rgb[hit]+.65*colour[hit]).astype(np.uint8)
                panel.paste(Image.fromarray(overlay),(640*i,40));error=maps[mode][row['file']]['vertex_camera_mm']
                draw.text((640*i+12,10),f'{mode} seed{seed} | {error:.1f} mm',font=font,fill='black')
            name=f"seed{seed}_{Path(row['file']).stem}.jpg";panel.save(figures/name,quality=90)
            visual_rows.append(dict(file=name,sample=row['file'],seed=seed,selection='fixed posterior view' if row in fixed else 'worst camera-vertex error; all failures retained in full records'))
    renderer.delete()
    (figures/'MANIFEST.json').write_text(json.dumps(dict(records=visual_rows,source='saved best-checkpoint native vertices; no fitting',test_visualized=False),indent=2))
    lines=['# R3 enlarged synthetic multi-seed results','',
        '500 synthetic parameter identities × 2 fixed poses × 4 shared physical cameras = 4,000 images. TRAIN 400 / VAL 50 / TEST 50 identities. TEST sealed.',
        '30 epochs, batch 16; three training seeds per existing model. One learning rate chosen by the frozen six-cell synthetic-VAL-only screen. Best and last both retained.','',
        '| Model | VAL camera-frame vertex mean ± seed sample SD (mm) |','|---|---:|']
    for mode,ss in summary['summary'].items():
        metric=ss['metrics']['vertex_camera_mm'];lines.append(f"| {mode} | {metric['mean']:.2f} ± {metric['sample_std']:.2f} |")
    lines += ['', 'Read PAIRED_SEED_COMPARISONS.json, every per-seed RESULTS.json and DEPTH_ABLATIONS.json together. Missing-depth degradation alone is not proof of geometry use: this architecture falls back to Official when depth is missing.',
        '', 'Real transfer: HuMMan 192 TRAIN + 40 VAL timestamps; K000 inputs, K001 independent measured points. Exact point-to-triangle distance is primary. Report TRAIN and VAL separately. No real training and no TEST evaluation.',
        '', 'These are synthetic geometry and real transfer development results, not prone clinical/acupoint accuracy or a guarantee of medical deployment. R2 data/camera distribution differs; its numbers are not direct matched comparisons.',
        '', 'Full raw outputs, metrics, best/last checkpoints and runtime source identity are in the server run directory. The static figures are generated from cached final meshes.']
    (a.out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
