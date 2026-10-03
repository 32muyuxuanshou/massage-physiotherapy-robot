"""Descriptive figures from frozen results; subjects are the displayed units."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--delivery',type=Path,required=True);a=p.parse_args()
    result=json.loads((a.delivery/'results'/'AGGREGATED_RESULTS.json').read_text())
    subjects=result['subjects'];methods=result['methods'];rows=result['per_subject']
    index={(r['subject'],r['method']):r for r in rows}
    values=np.array([[index[s,m]['posterior_d3d_median_mm'] for m in methods] for s in subjects])
    out=a.delivery/'figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(10,9))
    im=ax.imshow(values,norm=LogNorm(vmin=values.min(),vmax=values.max()),cmap='viridis_r',aspect='auto')
    labels=['Official','+ Txyz','+ Txyz + Pose','+ Rigid','+ Rigid + D']
    ax.set_xticks(range(5),labels)
    ax.set_yticks(range(len(subjects)),[s+' ('+index[s,methods[0]]['split']+')' for s in subjects])
    for i in range(len(subjects)):
        for j in range(5):
            ax.text(j,i,f'{values[i,j]:.2f}',ha='center',va='center',fontsize=8,
                    color='white' if im.norm(values[i,j])>.6 else 'black')
    ax.set_title('Posterior held-out point-to-triangle median (mm)\nSeed mean per subject; reconstructed-camera diagnostic')
    fig.colorbar(im,ax=ax,label='mm, logarithmic colour scale',fraction=.035,pad=.02)
    fig.tight_layout();fig.savefig(out/'per_subject_back_median.png',dpi=160);plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,6))
    for s in subjects:
        rigid=index[s,'Official+Rigid'];d=index[s,'Official+Rigid+D']
        improvement=rigid['posterior_d3d_median_mm']-d['posterior_d3d_median_mm']
        change=d['silhouette_iou']-rigid['silhouette_iou']
        colour='#b64b36' if rigid['split']=='dev' else '#176399'
        ax.scatter(improvement,change,c=colour,s=35)
        ax.annotate(s,(improvement,change),fontsize=8,xytext=(3,4),textcoords='offset points')
    ax.axhline(0,color='grey',lw=1);ax.grid(alpha=.15)
    ax.set_xlabel('Rigid -> Rigid+D: reduction in posterior median distance (mm)')
    ax.set_ylabel('Rigid -> Rigid+D: change in full projected-support silhouette IoU')
    ax.set_title('Surface fit and projected silhouette can move in different directions\nBlue: test; red: dev. Reference is projected cloud support, not manual RGB GT.')
    fig.tight_layout();fig.savefig(out/'surface_vs_silhouette.png',dpi=160);plt.close(fig)


if __name__=='__main__':main()
