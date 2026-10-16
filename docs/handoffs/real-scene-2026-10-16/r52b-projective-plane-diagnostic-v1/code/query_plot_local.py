"""A-depth projection evidence, not a clinical or correspondence-GT label."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':140})


def main(root):
    selected=json.loads((root/'query_review/SELECTION.json').read_text(encoding='utf-8'))['records']
    for i,r in enumerate(selected,1):
        with np.load(root/'query_review'/(r['tag']+'.npz')) as z:a={k:z[k] for k in z.files}
        depth=a['depth'].squeeze();valid=a['valid'].squeeze().astype(bool);h,w=depth.shape
        fig,axes=plt.subplots(2,3,figsize=(13,10),layout='constrained')
        lo,hi=np.quantile(depth[valid],[.02,.98])
        for col,(stage,title) in enumerate([('coarse','初始Coarse'),('step1','投影点面1步后'),('step3','投影点面3步后')]):
            q=a[stage+'_query'];p=a[stage+'_measured'];n=a[stage+'_normal'];obs=a[stage+'_observed'];grid=a[stage+'_grid'];delta=a[stage+'_delta_m']*1000
            fallback=bool(a[stage+'_fallback']);raw_norm=np.linalg.norm(a[stage+'_raw_delta_m'])*1000
            pixels=(grid+1)*np.array([w-1,h-1])/2;res=p-q;rn=np.einsum('ij,ij->i',n,res)*1000
            dist=np.linalg.norm(res,axis=1);keep=obs.copy()
            if obs.any():keep[obs]=dist[obs]<=np.quantile(dist[obs],.8)
            ax=axes[0,col];ax.imshow(np.ma.masked_where(~valid,depth),cmap='gray',vmin=lo,vmax=hi)
            ax.scatter(*pixels[obs].T,c=rn[obs],s=25,vmin=-50,vmax=50,cmap='coolwarm',edgecolors='black',linewidths=.3)
            ax.scatter(*pixels[obs&~keep].T,marker='x',c='#ffdf00',s=45,label='当前20%截断点')
            ax.set(xlim=(0,w),ylim=(h,0),title=title+f'｜可见{obs.sum()}，保留{keep.sum()}\nΔT=({delta[0]:.1f},{delta[1]:.1f},{delta[2]:.1f})mm\nraw范数{raw_norm:.1f}mm，超限回退：'+('是' if fallback else '否'),xlabel='缓存Depth u/px',ylabel='缓存Depth v/px');ax.legend(fontsize=8)
            ax=axes[1,col];bins=np.histogram_bin_edges(rn[obs],bins=24)
            ax.hist(rn[keep],bins=bins,color='#237c91',alpha=.8,label='保留点')
            ax.hist(rn[obs&~keep],bins=bins,color='#bb6633',alpha=.6,label='截断点')
            ax.axvline(0,color='black',ls='--');ax.set(xlabel='有符号点面残差mm（完整数值）',ylabel='点数',title='不把点少或残差小解释为对应正确');ax.legend()
        fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(-50,50),cmap='coolwarm'),ax=axes[0,:],label='有符号点面残差mm（蓝负/红正）',shrink=.7)
        fig.suptitle(r['tag']+'\nA-only采样审计：灰色为真实缓存深度，点色为预测法线方向残差（色限±50mm，直方图不截断）',fontsize=12)
        fig.savefig(root/'reports'/('query_%02d.png'%i));plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
