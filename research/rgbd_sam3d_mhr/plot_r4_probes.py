"""Raw consistent-camera input montage and full predicted-Z curves."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    m=json.loads((a.run/'physical_camera_data/MANIFEST.json').read_text());ids=sorted({r['identity'] for r in m['samples']})
    fig,axes=plt.subplots(4,4,figsize=(14,12),layout='constrained')
    for i,identity in enumerate(ids):
        for j,r in enumerate(x for x in m['samples'] if x['identity']==identity):
            axes[i,j].imshow(Image.open(a.run/'physical_camera_data'/r['file'].replace('.npz','.jpg')))
            axes[i,j].set_title(f"{identity} {r['role']} | factor {r['physical_camera_factor']:.2f}\nGT root Z {r['truth_camera_xyz_m'][2]:.2f} m");axes[i,j].axis('off')
    fig.suptitle('Same posed mesh/texture/light/K; RGB and Depth jointly rerendered; no TEST')
    fig.savefig(a.out/'PHYSICAL_INPUT_MONTAGE.jpg',dpi=130);plt.close(fig)
    files={p.stem:p for p in (a.run/'physical_baselines').glob('*.json')}
    files.update({('pilot_'+p.parent.name):p for p in (a.run/'pilots').glob('*/physical.json')})
    files.update({('formal_'+p.parent.name):p for p in (a.run/'formal').glob('*/physical.json')})
    fig,axes=plt.subplots(1,4,figsize=(18,4.8),layout='constrained')
    for ax,identity in zip(axes,ids):
        for label,p in files.items():
            rr=[r for r in json.loads(p.read_text())['records'] if r['identity']==identity]
            z=[r['camera_gt_xyz_m'][2] for r in rr];v=[r['camera_pred_xyz_m'][2] for r in rr]
            ax.plot(z,v,'o-',label=label,alpha=.7)
        ax.plot([min(z),max(z)],[min(z),max(z)],'k--',label='ideal response',linewidth=2)
        ax.set_title(identity);ax.set_xlabel('Ground-truth camera Z (m)');ax.set_ylabel('Predicted camera Z (m)');ax.grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncols=5,fontsize=7)
    fig.savefig(a.out/'PHYSICAL_CAMERA_Z_RESPONSE.png',dpi=150);plt.close(fig)
