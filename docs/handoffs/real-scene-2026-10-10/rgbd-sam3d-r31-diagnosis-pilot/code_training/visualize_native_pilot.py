"""Regenerate geometry/plots from saved predictions; never fit a mesh here."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from render_losses import MeshRenderer


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    args=p.parse_args()
    report=json.loads((args.run/'R2_PILOT_RESULTS.json').read_text())
    manifest=json.loads((args.data/'MANIFEST.json').read_text())
    out=args.run/'visualizations';out.mkdir(exist_ok=True)
    faces=torch.from_numpy(np.load(args.data/'faces.npy'))
    renderer=MeshRenderer(faces)
    methods=['official','rgb_only','residual','cross_attention']
    names=['Official RGB','RGB-only trained','Depth residual','Depth cross-attention']
    colors=['#d62728','#ff8c00','#008d62','#8250df']
    selected=[r for r in manifest['samples'] if r['role']=='VAL' and r['view'] in [0,1]]
    for row in selected:
        truth=np.load(args.data/row['file']);K=torch.from_numpy(truth['K'][None]).cuda()
        fig,axes=plt.subplots(2,5,figsize=(20,8),gridspec_kw={'height_ratios':[3,2]},layout='constrained')
        axes[0,0].imshow(truth['rgb']);axes[0,0].set_title('Synthetic RGB reference')
        reference_map=axes[1,0].imshow(np.ma.masked_equal(truth['depth_m'],0),cmap='viridis')
        fig.colorbar(reference_map,ax=axes[1,0],shrink=.7,label='Z (m)')
        axes[1,0].set_title('True surface Z (metres)')
        gt=torch.from_numpy(truth['pred_vertices']+truth['pred_cam_t'][:,None]).cuda()
        with torch.no_grad():gt_depth,_=renderer(gt,K)
        y=int(truth['bbox'][1]+.4*(truth['bbox'][3]-truth['bbox'][1]))
        all_profiles={'GT':gt_depth.cpu().numpy()[0,y]}
        for col,(mode,name,color) in enumerate(zip(methods,names,colors),1):
            pred=np.load(args.run/'predictions'/mode/'correct'/row['file'])
            v=pred['pred_vertices']+pred['pred_cam_t'][:,None]
            with torch.no_grad():depth,sil=renderer(torch.from_numpy(v).cuda(),K)
            depth=depth.cpu().numpy()[0];mask=sil.cpu().numpy()[0]>.5
            c=np.array(matplotlib.colors.to_rgb(color));overlay=truth['rgb'].astype(float)/255
            overlay[mask]=.52*overlay[mask]+.48*c
            contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay,contours,-1,tuple(c),1)
            axes[0,col].imshow(overlay);axes[0,col].axhline(y,color='white',lw=.8,ls='--')
            verror=np.linalg.norm(v-(truth['pred_vertices']+truth['pred_cam_t'][:,None]),axis=-1).mean()*1000
            axes[0,col].set_title(f'{name}\nMean vertex error {verror:.1f} mm')
            common=(depth>0)&(truth['depth_m']>0)
            residual=np.ma.masked_where(~common,(depth-truth['depth_m'])*1000)
            residual_map=axes[1,col].imshow(residual,cmap='coolwarm',vmin=-100,vmax=100)
            axes[1,col].set_title('Predicted Z - true Z, +/-100 mm\nBlank: no common hit')
            all_profiles[mode]=depth[y]
        fig.colorbar(residual_map,ax=list(axes[1,1:]),shrink=.7,label='Red: farther / blue: nearer (mm)')
        for ax in axes.flat:ax.set_axis_off()
        fig.suptitle(f"{row['identity']} / view {row['view']} | frozen cases, no best-case selection | SIMPLE MATERIAL PILOT",fontsize=15)
        fig.savefig(out/(Path(row['file']).stem+'_comparison.jpg'),dpi=140);plt.close(fig)
        fig,ax=plt.subplots(figsize=(11,4),layout='constrained')
        for name,values in all_profiles.items():
            values=np.where(values>0,values,np.nan)
            ax.plot(np.arange(len(values)),values,label=name,lw=2 if name=='GT' else 1.3)
        ax.invert_yaxis();ax.set(xlabel='Original RGB pixel u',ylabel='Camera Z (m)',
            title=f"{row['identity']} view {row['view']}: actual perspective Z section at v={y}")
        ax.legend();ax.grid(alpha=.2);fig.savefig(out/(Path(row['file']).stem+'_depth_profile.png'),dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    for mode in methods[1:]:
        rows=[r for r in report['curves'] if r['method']==mode]
        axes[0].plot([r['epoch'] for r in rows],[r['train_mean_loss'] for r in rows],label=mode)
        axes[1].plot([r['epoch'] for r in rows],[r['val']['vertex_camera_mm'] for r in rows],label=mode)
        axes[2].plot([r['epoch'] for r in rows],[r['val']['vertex_translation_removed_mm'] for r in rows],label=mode)
    for ax,title in zip(axes,['Training loss','Independent-identity val: absolute vertex mm','Val: translation removed vertex mm']):
        ax.set(xlabel='Epoch',title=title);ax.legend();ax.grid(alpha=.2)
    fig.savefig(out/'training_curves.png',dpi=160);plt.close(fig)
    (out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(
        rule='Every VAL identity, fixed views 0/1 selected independently of results',
        cases=[r['file'] for r in selected],cache_only=True,files=sorted(p.name for p in out.iterdir())),indent=2))
    print('VISUALIZATIONS',len(selected),'fixed cases',flush=True)


if __name__=='__main__':main()
