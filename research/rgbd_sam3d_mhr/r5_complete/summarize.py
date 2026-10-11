"""Three dataset tables, all seeds and checkpoints; no combined score."""
import argparse,csv,json
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from report_diagnostics import write_diagnostics

def csv_write(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(rows)

def main(a):
    r=a.root;out=r/'summary';out.mkdir(exist_ok=True);tables={d:[] for d in ['native','scan','real']};convergence=[]
    for cell in sorted((r/'evaluation').iterdir()):
        if not cell.is_dir():continue
        meta=dict(mode='Official',seed=0,checkpoint='fixed') if cell.name=='official' else dict(mode=cell.name.rsplit('_s',1)[0],seed=int(cell.name.rsplit('_s',1)[1].split('_')[0]),checkpoint=cell.name.rsplit('_',1)[1])
        for domain in ['native','scan','real']:
            file=cell/('real_B' if domain=='real' else domain)/'RESULTS.json'
            if not file.exists():continue
            data=json.loads(file.read_text())
            if domain=='native':tables[domain].append(dict(meta,**data['aggregated']['identity_equal_mean']))
            elif domain=='scan':tables[domain].append(dict(meta,**data['aggregated']['identity_equal']))
            else:
                for role,values in data['aggregated'].items():
                    method=meta['mode']+('+Txyz' if role.endswith('_Txyz') else '')
                    tables[domain].append(dict(meta,mode=method,role=role.split('_')[0],**values['identity_equal_mean']))
    stats=[]
    for domain,rows in tables.items():
        csv_write(out/(domain.upper()+'_ALL_SEEDS.csv'),rows);grouped=defaultdict(list)
        for row in rows:grouped[row['mode'],row['checkpoint'],row.get('role','VAL')].append(row)
        for key,values in grouped.items():
            numeric=[k for k,v in values[0].items() if isinstance(v,(int,float)) and k!='seed']
            stats.append(dict(dataset=domain,mode=key[0],checkpoint=key[1],role=key[2],seeds=[v['seed'] for v in values],
                seed_count=len(values),mean={k:float(np.mean([v[k] for v in values])) for k in numeric},
                std={k:float(np.std([v[k] for v in values],ddof=1)) if len(values)>1 else 0. for k in numeric}))
    for cell in sorted((r/'formal').glob('*')):
        curves=json.loads((cell/'CURVES.json').read_text());assert len(curves)==50
        previous=np.mean([v['val']['vertex_camera_mm'] for v in curves[-10:-5]])
        last=np.mean([v['val']['vertex_camera_mm'] for v in curves[-5:]])
        convergence.append(dict(cell=cell.name,epochs=50,last5_vs_previous5_percent=float((last-previous)/previous*100),
            native_total_exposures=sum(v['native_samples'] for v in curves),scan_total_exposures=sum(v['scan_samples'] for v in curves),
            training_seconds=sum(v['seconds'] for v in curves),best_epoch=min(curves,key=lambda v:v['val']['vertex_camera_mm'])['epoch']))
    assert len(convergence)==21
    csv_write(out/'CONVERGENCE.csv',convergence);(out/'SEED_MEAN_STD.json').write_text(json.dumps(stats,indent=2))
    fig,axes=plt.subplots(2,2,figsize=(14,9));methods=sorted({c['cell'].rsplit('_s',1)[0] for c in convergence})
    for mode in methods:
        for seed in [11,23,37]:
            curve=json.loads((r/'formal'/f'{mode}_s{seed}'/'CURVES.json').read_text());x=[v['epoch'] for v in curve]
            for axis,key in zip(axes.ravel(),['vertex_camera_mm','camera_mm','vertex_body_mm','vertex_translation_removed_mm']):
                axis.plot(x,[v['val'][key] for v in curve],label=f'{mode} s{seed}',alpha=.65);axis.set_title(key);axis.set_xlabel('Epoch');axis.set_ylabel('mm')
    axes[0,0].legend(fontsize=6,ncol=2);fig.tight_layout();fig.savefig(out/'TRAINING_CURVES.png',dpi=170);plt.close(fig)
    lines=['# 完整 R5 公平对照结果','', '新模型全部使用raw输出；Official＋Txyz是独立固定基线。native TEST未读取。','',
        '## 误差是什么意思','',
        '- native：原生MHR对应顶点的L2均值，以及Camera和去平移误差。','- scan：clean可见表面轴向Z、命中率、轮廓；没有原生MHR root真值。',
        '- real：固定Camera B的2048点到预测三角面的精确最近距离；A输入，B不拟合。不证明穴位或解剖对应精度。','',
        '## 各数据集分别看','', '|数据/人群|模型|checkpoint|seed数|主要误差均值±标准差(mm)|','|---|---|---|---:|---:|']
    for row in stats:
        key='vertex_camera_mm' if row['dataset']=='native' else 'full_mask_median_mm' if row['dataset']=='scan' else 'median_mm'
        lines.append(f"|{row['dataset']} {row['role']}|{row['mode']}|{row['checkpoint']}|{row['seed_count']}|{row['mean'][key]:.3f} ± {row['std'][key]:.3f}|")
    lines+=['','## 训练是否充分','', '每组正式训练50轮：30轮native＋20轮native/scan混合；每mixed轮完整遍历2304扫描样本。最佳checkpoint只按native VAL选择。',
        '50轮是本轮固定预算，不自动等于收敛。CONVERGENCE.csv给出末五轮变化；学习率是5轮native筛选在1e-4/3e-4中选出，不宣称全局最优。',
        '', '## 怎样判断结果','', '先比较三个seed的真实VAL raw结果、P95及逐身份变化，再与Official＋Txyz比较；只在合成上更好不能宣布部署可用。',
        'fine与coarse对比、失败分布、Depth干预在对应逐帧JSON中保留。对真实44帧的Depth干预主要报告输出响应，不能以响应或梯度非零宣称几何更准。',
        '','全量best/last预测、逐帧结果和checkpoint在私有执行目录；公开表与图在summary。']
    lines+=['']+write_diagnostics(r,out,csv_write)
    (r/'FINAL_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    (r/'SUMMARIZE_COMPLETE.json').write_text(json.dumps(dict(status='PASS',formal_runs=21,tables={k:len(v) for k,v in tables.items()},TEST_read=False),indent=2))
    print('SUMMARY_COMPLETE',len(stats),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
