"""All old 16 review frames and 11 old fallback frames, all three G1 seeds."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from visualize_r41_txyz import project, overlay, bounds


def panel(task):
    source,work,seed,row=task;source,work=Path(source),Path(work);key=row['key']
    data=json.loads((work/'ALL_RESULTS.json').read_text());lookup={(r['cell'],r['key']):r for r in data['records']}
    compact=np.load(source/'assets/original_assets/inputs'/(key+'.npz'))
    rgbdir=work/'rgb' if (work/'rgb'/(key+'_A.png')).exists() else source/'assets/original_assets/rgb'
    rgb=np.asarray(Image.open(rgbdir/(key+'_A.png')));rgb_b=np.asarray(Image.open(rgbdir/(key+'_B.png')))
    pb=np.load(source/'assets/datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
    ua=project(compact['points_camera_A'],compact['A_K']);ub=project(pb,compact['B_K'])
    faces=np.load(source/'assets/original_assets/official/faces.npy')
    ob=f'official_body_g1_camera_seed{seed}';go=f'g1_body_official_camera_seed{seed}';g=f'g1_seed{seed}'
    specs=[('Official','official','before',source/'assets/original_assets/official'),
        ('Official + T','official','after',source/'corrected/official'),
        ('G1',g,'before',source/f'assets/r4/formal/{g}/real'),('G1 + T',g,'after',source/f'corrected/{g}'),
        ('Official body / G1 cam',ob,'before',work/'raw'/ob),('Official body / G1 cam + T',ob,'after',work/'corrected'/ob),
        ('G1 body / Official cam + T',go,'after',work/'corrected'/go),
        ('Learned Camera-only','camera_only','before',work/'raw/camera_only'),('Camera-only + T','camera_only','after',work/'corrected/camera_only')]
    fig,ax=plt.subplots(2,10,figsize=(31,9),layout='constrained')
    ax[0,0].imshow(rgb);ax[0,0].scatter(ua[::10,0],ua[::10,1],s=2,c='cyan',alpha=.6);ax[0,0].set_title('A RGB / fitting samples',fontsize=10)
    ax[1,0].imshow(rgb_b);ax[1,0].scatter(ub[:,0],ub[:,1],s=2,c='cyan',alpha=.6);ax[1,0].set_title('B RGB / fixed exam points',fontsize=10)
    entry=dict(key=key,seed=seed,identity=row['identity'],role=row['role'],methods={})
    for i,(label,cell,stage,directory) in enumerate(specs,1):
        z=np.load(directory/(key+'.npz'));img,mask=overlay(rgb,z['vertices_camera_A'],faces,compact['A_K'])
        r=lookup[cell,key];m=r['triangle_'+stage]
        if cell=='official' or cell.startswith('g1_seed'):
            d=np.load(source/'distances'/cell/(key+'.npz'))[stage+'_mm']
        else:d=np.load(work/'distances'/cell/(key+'.npz'))[stage+'_mm']
        ax[0,i].imshow(img);ax[0,i].contour(mask,levels=[.5],colors=['lime'],linewidths=.5)
        ax[0,i].set_title(f"{label}\nB {m['median_mm']:.1f} / {m['p95_mm']:.1f} mm",fontsize=9)
        ax[1,i].imshow(rgb_b,alpha=.6);im=ax[1,i].scatter(ub[:,0],ub[:,1],s=5,c=d,cmap='inferno',vmin=0,vmax=150)
        ax[1,i].set_title('B point -> triangle'+('\nT fallback' if stage=='after' and r['fallback'] else ''),fontsize=9)
        entry['methods'][label]=m
    for level,uv,img in [(0,ua,rgb),(1,ub,rgb_b)]:
        x0,x1,y1,y0=bounds(uv,img.shape[1],img.shape[0])
        for axis in ax[level]:axis.set_xlim(x0,x1);axis.set_ylim(y1,y0);axis.axis('off')
    fig.colorbar(im,ax=ax[1,1:].tolist(),shrink=.65,label='Independent B surface residual mm; clipped colour at 150')
    fig.suptitle(f'{key} | G1 training seed {seed} | magenta = predicted mesh; green = SAME predicted boundary; B never fitted',fontsize=12)
    filename=f'{key}_seed{seed}.jpg';fig.savefig(work/'visualizations'/filename,dpi=100);plt.close(fig)
    entry['file']=filename;entry['historical_official_fallback']=lookup['official',key]['fallback']
    return entry


def main(a):
    work=a.work;out=work/'visualizations';out.mkdir(exist_ok=True)
    selection=json.loads((work/'VISUAL_SELECTION.json').read_text())
    tasks=[(str(a.source),str(work),s,r) for s in [11,23,37] for r in selection['records']]
    records=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for r in pool.map(panel,tasks):
            records.append(r)
            if len(records)%9==0:print('R42_VISUAL',len(records),'/',len(tasks),flush=True)
    (out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(status='COMPLETE',selection=selection['selection'],
        unique_frames=len(selection['records']),panels=len(records),records=records,
        rendering='pinhole projected triangle union for display only; all metrics exact fixed B point-to-triangle',
        colours='magenta and green both describe prediction, never annotation GT; cyan measured points'),indent=2))
    data=json.loads((work/'ALL_RESULTS.json').read_text())
    cells=['official',*[f'g1_seed{s}' for s in [11,23,37]],*[f'official_body_g1_camera_seed{s}' for s in [11,23,37]],'camera_only']
    fig,axes=plt.subplots(1,2,figsize=(15,5),layout='constrained')
    for axis,role in zip(axes,['TRAIN','VAL']):
        x=np.arange(len(cells));med=[data['results'][c]['after'][role]['identity_equal_mean']['median_mm'] for c in cells]
        tail=[data['results'][c]['after'][role]['identity_equal_mean']['p95_mm'] for c in cells]
        axis.bar(x-.18,med,.36,label='median');axis.bar(x+.18,tail,.36,label='P95');axis.set_ylabel('mm');axis.set_title(role+' all methods + SAME Txyz')
        axis.set_xticks(x,[c.replace('official_body_g1_camera','O-body/G1-cam') for c in cells],rotation=35,ha='right');axis.legend()
    fig.savefig(out/'R42_PRIMARY_COMPARISON.png',dpi=160);plt.close(fig)
    ids=list(data['results']['official']['after']['TRAIN']['per_identity'])+list(data['results']['official']['after']['VAL']['per_identity'])
    fig,axes=plt.subplots(1,4,figsize=(20,6),layout='constrained')
    for axis,cell in zip(axes,[*[f'official_body_g1_camera_seed{s}' for s in [11,23,37]],'camera_only']):
        delta=[]
        for identity in ids:
            role='TRAIN' if identity in data['results']['official']['after']['TRAIN']['per_identity'] else 'VAL'
            delta.append(data['results'][cell]['after'][role]['per_identity'][identity]['metrics']['p95_mm']-data['results']['official']['after'][role]['per_identity'][identity]['metrics']['p95_mm'])
        axis.barh(ids,delta,color=['#bc382c' if d>0 else '#247ca4' for d in delta]);axis.axvline(0,color='black',lw=.5)
        axis.set_title(cell.replace('official_body_g1_camera','O-body/G1-cam'));axis.set_xlabel('P95 delta vs Official+Txyz mm; right worse')
    fig.savefig(out/'ALL_IDENTITY_P95.png',dpi=160);plt.close(fig)
    print('R42_VISUAL_COMPLETE',len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True);main(p.parse_args())
