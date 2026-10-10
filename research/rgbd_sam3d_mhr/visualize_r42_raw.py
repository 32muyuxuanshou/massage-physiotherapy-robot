"""Four fixed sensor QA cases; show original observations without model alignment."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from audit_r42_geometry import official_functions


def main(a):
    project=official_functions(a.work/'official_sources/visualizer_rgbd.py')['perspective_projection']
    selected=json.loads((a.previous/'VISUAL_SELECTION.json').read_text())['records']
    keys=['p001195_a000053_000037','p001196_a000388_000040',
          'p001194_a000062_000005','p100069_a005191_000006']
    files=[]
    for key in keys:
        row=next(r for r in selected if r['key']==key)
        folder=a.work/'raw'/row['sequence']
        fig,axes=plt.subplots(2,3,figsize=(17,9),layout='constrained')
        for i,device in enumerate(['kinect_000','kinect_001']):
            z=np.load(folder/f"{device}_{row['frame']:06d}.npz")
            points=z['points_color'];uv=project(points,z['K'])
            lo,hi=np.quantile(points[:,2],[.01,.99]);norm=Normalize(lo,hi)
            axes[i,0].imshow(z['rgb']);axes[i,0].set_title(f'{device}: original RGB')
            axes[i,1].imshow(z['rgb'])
            c=axes[i,1].scatter(uv[::4,0],uv[::4,1],c=points[::4,2],
                              s=2,cmap='turbo',norm=norm)
            fig.colorbar(c,ax=axes[i,1],label='observed colour-camera Z (m)',shrink=.7)
            axes[i,1].set_title('Raw depth -> released calibration -> RGB')
            for panel in axes[i,:2]:
                panel.set_xlim(max(0,uv[:,0].min()-100),min(1920,uv[:,0].max()+100))
                panel.set_ylim(min(1080,uv[:,1].max()+100),max(0,uv[:,1].min()-100))
            raw=z['depth_raw_mm'].astype(float)/1000
            valid=(z['mask_depth']>0)&(raw>.1)&(raw<5)
            d=np.ma.masked_where(~valid,raw)
            cm=plt.get_cmap('turbo').copy();cm.set_bad('#dddddd')
            dplot=axes[i,2].imshow(d,cmap=cm)
            axes[i,2].contour(valid,levels=[.5],colors=['black'],linewidths=.5)
            fig.colorbar(dplot,ax=axes[i,2],label='raw depth-camera Z (m)',shrink=.7)
            axes[i,2].set_title('Original 640 x 576 depth + author mask')
            for panel in axes[i]:panel.axis('off')
        fig.suptitle(f'{key} | real sensor observations; no predicted mesh, registration fitting or lag correction',fontsize=12)
        path=a.work/'visualizations'/f'{key}_raw_sensors.jpg'
        fig.savefig(path,dpi=120);plt.close(fig);files.append(path.name)
    (a.work/'visualizations/RAW_MANIFEST.json').write_text(json.dumps(dict(
        files=files,selection=keys,notes='Depth-camera Z and colour-camera Z are different coordinate quantities. Point colour scales are per view, never used as error scores.',
        calibration_fitted=False,model_used=False),indent=2))
    print('RAW_SENSOR_VISUALS',len(files))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True);main(p.parse_args())
