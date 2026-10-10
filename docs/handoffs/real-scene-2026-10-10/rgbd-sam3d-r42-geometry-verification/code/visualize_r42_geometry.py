"""Fixed four cases x three seeds: RGB, measured rays, side geometry and B evidence."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from visualize_r41_txyz import overlay,project,bounds


def main(a):
    out=a.work/'visualizations';out.mkdir(exist_ok=True)
    geometry=json.loads((a.work/'GEOMETRY_AUDIT.json').read_text())
    old=json.loads((a.previous/'ALL_RESULTS.json').read_text());lookup={(r['key'],r['cell']):r for r in old['records']}
    keys=['p001195_a000053_000037','p001196_a000388_000040','p001194_a000062_000005','p100069_a005191_000006']
    records=[];assets=a.source/'assets';faces=np.load(assets/'original_assets/official/faces.npy')
    for key in keys:
        g=next(x for x in geometry['detailed_27_frames'] if x['key']==key)
        compact=np.load(assets/'original_assets/inputs'/(key+'.npz'));p=compact['points_camera_A']
        b=np.load(assets/'datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
        rgbdir=a.previous/'rgb' if (a.previous/'rgb'/(key+'_A.png')).exists() else assets/'original_assets/rgb'
        rgb=np.asarray(Image.open(rgbdir/(key+'_A.png')));rgbb=np.asarray(Image.open(rgbdir/(key+'_B.png')))
        uv=project(p,compact['A_K']);uvb=project(b,compact['B_K'])
        for seed in [11,23,37]:
            cell=f'g1_seed{seed}';swap=f'official_body_g1_camera_seed{seed}'
            specs=[('Official','official','before',assets/'original_assets/official'),
                ('Official + T','official','after',a.source/'corrected/official'),
                ('G1',cell,'before',assets/f'r4/formal/{cell}/real'),('G1 + T',cell,'after',a.source/f'corrected/{cell}'),
                ('Official body / G1 cam',swap,'before',a.previous/f'raw/{swap}'),
                ('Official body / G1 cam + T',swap,'after',a.previous/f'corrected/{swap}')]
            fig,ax=plt.subplots(3,7,figsize=(28,12),layout='constrained')
            ax[0,0].imshow(rgb);ax[0,0].scatter(uv[::10,0],uv[::10,1],s=3,c='cyan');ax[0,0].set_title('A RGB + measured points')
            ax[1,0].imshow(rgbb);ax[1,0].scatter(uvb[:,0],uvb[:,1],s=3,c='cyan');ax[1,0].set_title('B RGB + independent points')
            ax[2,0].scatter(p[:,2],p[:,1],s=1,c='cyan');ax[2,0].set_title('A measurements | side Y-Z')
            zlo,zhi=p[:,2].min()-.15,p[:,2].max()+.45;ylo,yhi=p[:,1].min()-.1,p[:,1].max()+.1
            for i,(label,name,stage,directory) in enumerate(specs,1):
                z=np.load(directory/(key+'.npz'));v=z['vertices_camera_A'];vb=z['vertices_camera_B']
                img,mask=overlay(rgb,v,faces,compact['A_K']);bimg,bmask=overlay(rgbb,vb,faces,compact['B_K'])
                diagnostics=next(x for x in g['methods'] if x['cell']==name and x['stage']==stage)
                ar=diagnostics['A_ray'];br=lookup[key,name]['triangle_'+stage]
                ax[0,i].imshow(img);ax[0,i].contour(mask,levels=[.5],colors=['gold'],linewidths=.5)
                ax[0,i].set_title(f"{label}\nA ray signed Z {ar['signed_z_median_mm']:.1f} mm | hit {100*ar['hit_fraction']:.0f}%",fontsize=10)
                ax[1,i].imshow(bimg);ax[1,i].scatter(uvb[::3,0],uvb[::3,1],s=2,c='cyan')
                ax[1,i].set_title(f"B surface {br['median_mm']:.1f} / {br['p95_mm']:.1f} mm",fontsize=10)
                ax[2,i].scatter(v[::4,2],v[::4,1],s=1,c='magenta',alpha=.4)
                ax[2,i].scatter(p[:,2],p[:,1],s=1,c='cyan',alpha=.6)
                ax[2,i].set_title(f"A surface median {diagnostics['A_observed_to_mesh']['median_mm']:.1f} mm",fontsize=10)
            for row,pts,image in [(0,uv,rgb),(1,uvb,rgbb)]:
                limits=bounds(pts,image.shape[1],image.shape[0])
                for panel in ax[row]:panel.set_xlim(limits[:2]);panel.set_ylim(limits[2:]);panel.axis('off')
            for panel in ax[2]:
                panel.set_xlim(zlo,zhi);panel.set_ylim(yhi,ylo);panel.set_aspect('equal',adjustable='box')
                panel.set_xlabel('camera A Z (m)');panel.set_ylabel('camera A Y (m)');panel.grid(alpha=.2)
            fig.suptitle(f'{key} | seed {seed} | cyan=measured; magenta/gold=prediction | side view includes hidden mesh surface; no B alignment',fontsize=13)
            filename=f'{key}_seed{seed}_geometry.jpg';fig.savefig(out/filename,dpi=110);plt.close(fig)
            records.append(dict(key=key,seed=seed,file=filename,selection='four preregistered sensor QA cases; every G1 seed'))
            print('GEOMETRY_VISUAL',len(records),'/12',flush=True)
    (out/'MANIFEST.json').write_text(json.dumps(dict(records=records,source='saved meshes and original fixed A/B points; no refit',test_read=False),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True);p.add_argument('--work',type=Path,required=True);main(p.parse_args())
