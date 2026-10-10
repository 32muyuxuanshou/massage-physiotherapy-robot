"""All 16 historical review frames x 3 seeds, cached final meshes only."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def project(p,K):
    return p[:,:2]/p[:,2,None]*np.array([K[0,0],K[1,1]])+K[:2,2]


def overlay(rgb,vertices,faces,K):
    # Rasterized pinhole projection for illustration; not a depth evaluator.
    uv=project(vertices,K);valid=(vertices[faces,2]>0).all(1)
    mask=Image.new('L',(rgb.shape[1],rgb.shape[0]));draw=ImageDraw.Draw(mask)
    for triangle in uv[faces[valid]]:draw.polygon([tuple(x) for x in triangle],fill=255)
    hit=np.asarray(mask)>0;result=rgb.copy();result[hit]=(.45*rgb[hit]+.55*np.array([190,70,220])).astype(np.uint8)
    return result,hit


def bounds(uv,width,height):
    lo=np.min(uv,axis=0);hi=np.max(uv,axis=0);pad=.12*max(hi-lo)
    return max(0,lo[0]-pad),min(width,hi[0]+pad),min(height,hi[1]+pad),max(0,lo[1]-pad)


def main(work):
    out=work/'visualizations';out.mkdir(exist_ok=True)
    data=json.loads((work/'PAIRED_RESULTS.json').read_text());lookup={(r['cell'],r['key']):r for r in data['records']}
    selected=json.loads((work/'assets/original_assets/VISUAL_SELECTION.json').read_text())['records']
    faces=np.load(work/'assets/original_assets/official/faces.npy');records=[]
    for seed in [11,23,37]:
        for r in selected:
            key=f"{r['sequence']}_{r['frame']:06d}";compact=np.load(work/'assets/original_assets/inputs'/(key+'.npz'))
            rgb=np.asarray(Image.open(work/'assets/original_assets/rgb'/f'{key}_A.png'))
            rgb_b=np.asarray(Image.open(work/'assets/original_assets/rgb'/f'{key}_B.png'))
            pb=np.load(work/'assets/datasets/heldout/humman_r3_k1_v1'/(key+'.npz'))['points_camera_B']
            ua=project(compact['points_camera_A'],compact['A_K']);ub=project(pb,compact['B_K'])
            specs=[('Official','official','before',work/'assets/original_assets/official'),
                ('Official + Txyz','official','after',work/'corrected/official'),
                (f'G0 + Txyz (s{seed})',f'g0_seed{seed}','after',work/f'corrected/g0_seed{seed}'),
                (f'G1 (s{seed})',f'g1_seed{seed}','before',work/f'assets/r4/formal/g1_seed{seed}/real'),
                (f'G1 + Txyz (s{seed})',f'g1_seed{seed}','after',work/f'corrected/g1_seed{seed}')]
            fig,ax=plt.subplots(2,6,figsize=(22,9),layout='constrained')
            ax[0,0].imshow(rgb);ax[0,0].scatter(ua[::10,0],ua[::10,1],s=2,c='#00d9e8',alpha=.6);ax[0,0].set_title('Camera A: RGB + fitting samples')
            ax[1,0].imshow(rgb_b);ax[1,0].scatter(ub[:,0],ub[:,1],s=2,c='#00d9e8',alpha=.7);ax[1,0].set_title('Camera B: 2048 evaluation points')
            entry=dict(key=key,seed=seed,identity=r['identity'],role=r['role'],selection='Unchanged R3.1 16-frame review selection',methods={},file=f'{key}_seed{seed}.jpg')
            for i,(label,cell,stage,directory) in enumerate(specs,1):
                z=np.load(directory/(key+'.npz'));panel,mask=overlay(rgb,z['vertices_camera_A'],faces,compact['A_K'])
                d=np.load(work/'distances'/cell/(key+'.npz'))[stage+'_mm'];m=lookup[cell,key]['triangle_'+stage]
                ax[0,i].imshow(panel);ax[0,i].contour(mask,levels=[.5],colors=['lime'],linewidths=.5)
                ax[0,i].set_title(f"{label}\nB median {m['median_mm']:.1f} / P95 {m['p95_mm']:.1f} mm")
                ax[1,i].imshow(rgb_b,alpha=.6);im=ax[1,i].scatter(ub[:,0],ub[:,1],s=5,c=d,cmap='inferno',vmin=0,vmax=150)
                fallback=lookup[cell,key]['fallback'] if stage=='after' else False
                ax[1,i].set_title('B point -> exact triangle'+('\nTxyz fallback: original retained' if fallback else ''))
                entry['methods'][label]=m
            for level,uv,image in [(0,ua,rgb),(1,ub,rgb_b)]:
                x0,x1,y1,y0=bounds(uv,image.shape[1],image.shape[0])
                for panel in ax[level]:panel.set_xlim(x0,x1);panel.set_ylim(y1,y0);panel.axis('off')
            fig.colorbar(im,ax=ax[1,1:].tolist(),shrink=.65,label='Held-out surface residual mm (colours clipped at 150)')
            fig.suptitle(key+f' | seed {seed} | magenta = predicted projection; green = same predicted boundary | B never fitted',fontsize=13)
            fig.savefig(out/entry['file'],dpi=105);plt.close(fig);records.append(entry)
            print('VISUAL',len(records),'/48',flush=True)
    (out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(records=records,rendering='Pinhole projected triangle union, visualization only; metrics use cached exact triangle distances.',
        selection='All 16 historical frames x all 3 seeds; no new favourable-case selection',test_read=False),indent=2))
    analysis=json.loads((work/'ANALYSIS.json').read_text())
    fig,ax=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    cells=['official']+[f'{m}_seed{s}' for m in ['g0','g1'] for s in [11,23,37]]
    for axis,role in zip(ax,['TRAIN','VAL']):
        x=np.arange(len(cells));before=[data['results'][c]['before'][role]['identity_equal_mean']['median_mm'] for c in cells]
        after=[data['results'][c]['after'][role]['identity_equal_mean']['median_mm'] for c in cells]
        axis.bar(x-.18,before,.36,label='Raw');axis.bar(x+.18,after,.36,label='+ same Txyz');axis.set_xticks(x,cells,rotation=35,ha='right');axis.set_title(role+' identity-equal median');axis.set_ylabel('mm');axis.legend()
    fig.savefig(out/'FAIR_COMPARISON.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(1,3,figsize=(16,5),layout='constrained')
    ids=sorted(data['results']['official']['after']['TRAIN']['per_identity'])+sorted(data['results']['official']['after']['VAL']['per_identity'])
    for axis,seed in zip(ax,[11,23,37]):
        delta=[]
        for identity in ids:
            x=next(r for r in analysis['paired_identities'] if r['cell']==f'g1_seed{seed}' and r['identity']==identity)
            delta.append(x['delta_from_official_txyz']['p95_mm'])
        axis.barh(ids,delta,color=['#b83b2b' if x>0 else '#247ba0' for x in delta]);axis.axvline(0,color='black',lw=.7);axis.set_title(f'G1+Txyz - Official+Txyz | seed {seed}');axis.set_xlabel('Identity P95 delta mm; right = worse')
    fig.savefig(out/'ALL_IDENTITY_P95.png',dpi=170);plt.close(fig)
    print('VISUALIZATION_COMPLETE',len(records),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work)
