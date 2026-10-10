"""Saved meshes only: exact perspective surface rendering and held-out residuals."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'synthesis_r5'))
from raster import render_z


def project(xyz,K):
    p=xyz@K.T
    return p[:,:2]/p[:,2:]


def shaded(rgb,vertices,faces,K):
    _,face_id=render_z(vertices.astype(np.float32),faces,K,*rgb.shape[:2])
    tri=vertices[faces]
    n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
    intensity=.35+.65*np.abs(n@np.array([.3,-.4,-.866]))
    hit=face_id>=0
    result=rgb.copy()
    result[hit]=np.clip(.2*rgb[hit]+.8*intensity[face_id[hit],None]*np.array([65,185,235]),0,255)
    return result


def run(a):
    a.out.mkdir(exist_ok=True)
    rows=json.loads((a.inputs/'COMBINED_SELECTION.json').read_text())['records']
    faces=np.load(a.inputs/'faces.npy')
    data={f.stem:json.loads(f.read_text()) for f in (a.results/'real_evaluation').glob('*.json')
          if f.stem=='official' or f.stem.startswith('repaired__')}
    lookup={(cell,r['key']):r for cell,d in data.items() for r in d['records']}
    records=[]
    for seed in [11,23,37]:
        for row in rows:
            key=f"{row['sequence']}_{row['frame']:06d}"
            z=np.load(a.inputs/'inputs'/(key+'.npz'))
            rgb=np.asarray(Image.open(a.inputs/'rgb'/(key+'_A.png')))
            rgbb=np.asarray(Image.open(a.inputs/'rgb'/(key+'_B.png')))
            pb=np.load(a.inputs/'heldout'/(key+'.npz'))['points_camera_B']
            ua=project(z['points_camera_A'],z['A_K']);ub=project(pb,z['B_K'])
            specs=[('Official','official','before','predictions'),
                   ('Official + Txyz','official','after','corrected'),
                   ('Native-only + Txyz',f'repaired__continuation__native_only_s{seed}','after','corrected'),
                   ('Scan-mixed raw',f'repaired__continuation__mixed_s{seed}','before','predictions'),
                   ('Scan-mixed + Txyz',f'repaired__continuation__mixed_s{seed}','after','corrected')]
            fig,ax=plt.subplots(2,6,figsize=(21,9),layout='constrained')
            ax[0,0].imshow(rgb);ax[0,0].scatter(ua[::10,0],ua[::10,1],s=2,c='cyan')
            ax[0,0].set_title('A input + fitting samples')
            ax[1,0].imshow(rgbb);ax[1,0].scatter(ub[:,0],ub[:,1],s=2,c='cyan')
            ax[1,0].set_title('B held-out 2048 samples')
            entry=dict(row,seed=seed,file=f'{key}_s{seed}.jpg',methods={})
            for i,(name,cell,stage,folder) in enumerate(specs,1):
                mesh=np.load(a.inputs/folder/cell/(key+'.npz'))['vertices_camera_A']
                panel=shaded(rgb,mesh,faces,z['A_K'])
                metric=lookup[cell,key]['triangle_'+stage]
                ax[0,i].imshow(panel)
                ax[0,i].set_title(f"{name}\nB {metric['median_mm']:.1f} / {metric['p95_mm']:.1f} mm")
                distances=np.load(a.inputs/'distances'/cell/(key+'.npz'))[stage+'_mm']
                ax[1,i].imshow(rgbb,alpha=.55)
                im=ax[1,i].scatter(ub[:,0],ub[:,1],c=distances,s=5,cmap='inferno',vmin=0,vmax=150)
                fallback=lookup[cell,key]['fallback'] if stage=='after' else False
                ax[1,i].set_title('B point-to-triangle'+(' | FALLBACK' if fallback else ''))
                entry['methods'][name]=dict(metric,fallback=fallback)
            for j,(uv,img) in enumerate([(ua,rgb),(ub,rgbb)]):
                lo=uv.min(0);hi=uv.max(0);pad=.12*np.max(hi-lo)
                for axis in ax[j]:
                    axis.set_xlim(max(0,lo[0]-pad),min(img.shape[1],hi[0]+pad))
                    axis.set_ylim(min(img.shape[0],hi[1]+pad),max(0,lo[1]-pad));axis.axis('off')
            fig.colorbar(im,ax=ax[1,1:].tolist(),shrink=.7,label='B residual mm, colour capped at 150')
            fig.suptitle(f'{key} | seed {seed} | cyan = predicted visible mesh, not ground truth | B never fitted')
            fig.savefig(a.out/entry['file'],dpi=100);plt.close(fig);records.append(entry)
            print('REAL_VISUAL',len(records),'/',len(rows)*3,flush=True)
    (a.out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(records=records,
        rendering='actual cached full mesh; perspective z-buffer using original K; fixed normal shading',
        selection='historical16 + all Official fallback frames + first2 p001195 non-fallback; all3 seeds; visualization only',
        camera_B_fit=False,TEST_read=False),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['inputs','results','out']:p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
