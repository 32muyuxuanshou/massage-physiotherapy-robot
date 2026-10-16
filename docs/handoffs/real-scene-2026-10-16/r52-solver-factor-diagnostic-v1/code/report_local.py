"""Readable cohort-separated figures and report from completed diagnostics."""
import argparse,html,json
from pathlib import Path
import numpy as np

LABEL={
 'official_hist6':'参考：Official＋历史Txyz', 'coarse':'参考：Full内部Coarse','fine':'参考：原Full Last Fine',
 'hist_med1':'Coarse＋密集历史算子1步','hist_med2':'Coarse＋密集历史算子2步','hist_med3':'Coarse＋密集历史算子3步','hist_med6':'Coarse＋密集历史算子6步',
 'all256_o2m_med6':'256全部／观测→Mesh／中位数6步','vis256_o2m_med6':'256可见／观测→Mesh／中位数6步','vis256_m2o_med6':'256可见／Mesh→观测／中位数6步',
 'hist_mean6':'密集／截断均值6步','hist_plane6':'密集／点面LS6步','hist_plane_gate6':'密集／点面LS＋方向衰减6步',
 'proj_vis_med1':'原Fine射线对应／中位数1步','proj_lattice_vis_med1':'实际所采像素XYZ／中位数1步',
 'lattice_nn_vis_med1':'同Depth格点NN／中位数1步','lattice_nn_vis_mean1':'同Depth格点NN／均值1步','lattice_nn_vis_plane1':'同Depth格点NN／点面LS1步'}


def main(root):
    out=root/'reports';cells=json.loads((out/'RESULTS.json').read_text());pairs=json.loads((out/'PAIRED_CONTRASTS.json').read_text());cfg=json.loads((root/'EXPERIMENT.json').read_text())
    def read(method,dataset,role,field):
        rr=sorted([r for r in cells if r['method']==method and r['dataset']==dataset and r['role']==role],key=lambda r:r['seed'])
        return np.array([r['fallback'] if field=='fallback' else r['metrics'][field]['equal_mean'] for r in rr])
    def fmt(a):return f'<b>{a.mean():.3f} ± {a.std(ddof=1):.3f}</b><br><small>11/23/37：'+ ' / '.join(f'{v:.3f}' for v in a)+'</small>'
    def table(headers,rows):return '<div class="scroll"><table><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in r)+'</tr>' for r in rows)+'</table></div>'
    cohorts=[('native','VAL','Native合成VAL：50身份400帧',['vertex_camera_mm','camera_mm','vertex_p95_mm']),('real','TRAIN','HuMMan真实开发TRAIN：18人192帧',['median_mm','p95_mm','coverage_50mm']),('real','VAL','HuMMan真实开发VAL：4人40帧',['median_mm','p95_mm','coverage_50mm']),('behave',next(r['role'] for r in cells if r['dataset']=='behave'),'BEHAVE已消费子集：3人90序列270帧',['median_mm','p95_mm','coverage_50mm','pve_mm'])]
    native=lambda m,k:read(m,'native','VAL',k).mean()
    real=lambda m,k:read(m,'real','VAL',k).mean()
    bhrole=cohorts[-1][1];beh=lambda m,k:read(m,'behave',bhrole,k).mean()
    intro=f'''<h1>R5.2：零训练求解器对照</h1><p class="lead">同一Full Last的Body、Coarse与历史输入；三个seed，2706个人物帧状态，18种方法，48708条方法评价。没有训练新网络。</p>
    <div class="card"><b>本轮判断：不支持“Fine换成3D NN就能稳赢”。</b><p>完整历史Txyz接在Coarse后，HuMMan改善，BEHAVE反而退化。同Depth的一步控制里，3D NN在四组数据、全部三个seed均比投影对应差。点面LS在HuMMan VAL median略超旧基线，但P95和跨域结果尚不稳定；它是候选，不是胜出的新模型。</p><p><a href="ANALYSIS.md">逐项解释、失败人物与下一步判断</a>。本轮结束，不追加训练。</p></div>
    <div class="card"><b>首先回答：显式几何求解能否补上差距？</b><p>HuMMan VAL：原Fine {real('fine','median_mm'):.3f} → Coarse＋历史Txyz6步 {real('hist_med6','median_mm'):.3f} mm；Official＋Txyz为{real('official_hist6','median_mm'):.3f} mm。</p>
    <p>BEHAVE独立表面：原Fine {beh('fine','median_mm'):.3f} → Coarse＋历史Txyz6步 {beh('hist_med6','median_mm'):.3f} mm；Official＋Txyz为{beh('official_hist6','median_mm'):.3f} mm。必须连同下面P95、每seed和fallback一起判断。</p></div>
    <p>这是一轮诊断后处理对照，不把新分支改称单前向R5主模型，也不据此证明真实根节点、解剖或穴位更准。新增几何方法的177.888mm限制相对于各自起点：Coarse方法fallback回Coarse。原Fine参考保持原样，不额外套历史步长限制。</p>'''
    sections=[]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':140})
    fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
    for col,(dataset,role,title,fields) in enumerate(cohorts):
        for row,field in enumerate([fields[0],fields[1]]):
            ax=axes[row,col]
            values=np.array([read('hist_med%d'%n,dataset,role,field) for n in [1,2,3,6]])
            for j,s in enumerate([11,23,37]):ax.plot([1,2,3,6],values[:,j],marker='o',label='seed'+str(s))
            for method,color,lab in [('fine','#34495e','原Fine均值'),('official_hist6','#9b5d42','Official+Txyz均值')]:ax.axhline(read(method,dataset,role,field).mean(),ls='--',color=color,label=lab)
            ax.set(xlabel='相同密集对应的迭代步数',ylabel=field+' /mm',xticks=[1,2,3,6],title=title if row==0 else '各seed与两个固定参考');ax.legend(fontsize=7)
    fig.suptitle('只改变步数：密集16384 Anchor、观测→Mesh、截断逐轴中位数；所有点与限制固定')
    fig.savefig(out/'iterations.png');plt.close(fig)
    md='# R5.2：零训练求解器对照\n\n18方法×3seed，Native400＋HuMMan192/40＋BEHAVE270。固定Body，变化全部来自平移。\n\n'
    for dataset,role,title,fields in cohorts:
        headers=['方法']+[{'vertex_camera_mm':'对应顶点均值mm','camera_mm':'Camera L2 mm','vertex_p95_mm':'对应顶点P95 mm','median_mm':'独立表面median mm','p95_mm':'独立表面P95 mm','coverage_50mm':'≤50mm覆盖率%','pve_mm':'拟合参考PVE mm'}[f] for f in fields]+['fallback（11/23/37）']
        rows=[]
        md+='## '+title+'\n\n|方法|'+'|'.join(headers[1:])+'|\n|'+'---|'*len(headers)+'\n'
        for method in cfg['methods']:
            a=[read(method,dataset,role,f)*(100 if f=='coverage_50mm' else 1) for f in fields];fb=read(method,dataset,role,'fallback')
            fallback_text='不适用' if method in ['coarse','fine'] else ' / '.join(str(int(v)) for v in fb)
            rows.append([html.escape(LABEL[method])]+[fmt(v) for v in a]+[fallback_text])
            md+='|'+LABEL[method]+'|'+'|'.join(f'{v.mean():.3f} ± {v.std(ddof=1):.3f}' for v in a)+'|'+fallback_text+'|\n'
        sections.append('<h2>'+title+'</h2>'+table(headers,rows))
    contrast_rows=[]
    for c in pairs:
        if c['seed']!=11:continue
        rr=sorted([r for r in pairs if all(r[k]==c[k] for k in ['contrast','dataset','role'])],key=lambda r:r['seed'])
        contrast_rows.append([c['contrast'],c['dataset']+'/'+c['role'],fmt(np.array([r['aggregate_delta_mm'] for r in rr])),' / '.join(str(r['improved_frames']) for r in rr),' / '.join(str(r['worsened_frames']) for r in rr)])
    body=intro+'<h2>同一密集算法，只改变步数</h2><img src="iterations.png">'+''.join(sections)+'''<h2>怎么读这些误差</h2><p>Native是有GT的对应顶点距离和Camera参数误差；真实域是原固定独立传感器点→预测三角面，单向可见表面评价。BEHAVE PVE只相对拟合SMPL参考。不将不同域、不同指标混成总分。</p>
    <p>先每帧median/P95，再frame→sequence→identity等权；BEHAVE先三相机统计等权。表中的P95不是把全体点合并后的总体P95。三seed是原父模型的三个Coarse起点，不是本轮三次训练。</p>
    <h2>逐因子配对：after减before，负值表示误差更小</h2>'''+table(['对比','数据','Δ mm均值±SD及每seed','改善帧数11/23/37','退化帧数11/23/37'],contrast_rows)+'''
    <h2>解释边界</h2><p>密集系列均使用历史A5000点。格点对应系列使用同一缓存Depth的全部有效XYZ，在相同初始可见Query和一步更新下比较投影关联与3D NN；另保留原Fine将采样Z放到Query射线上的版本，用来分开像素射线赋值差异。</p>
    <p>点面LS是独立算子，SVD rcond固定1e-6；旧方向衰减作为另一变量。小特征值表示该点面系统约束弱，更多点或NN本身并不保证切向真实对应。可见子集固定于初始Coarse，不在迭代中按B好坏改变。</p>
    <p>投影残差直接取中位数只是这里预先定义的一种更新，不代表最优投影求解或该信息的上限。256个点作为NN目标会同时降低离散Mesh的表面近似质量，不能把它全部解释成Fine只观察了多少点。单变量改变后，后续对应关系也会随迭代路径变化；本轮不能证明唯一病因。</p>
    <p>Native的Official＋Txyz是按冻结noisy格点新建立的诊断基线；真实HuMMan/BEHAVE的历史点集与旧基线已复现。不能把Native的新增基线说成历史结果复现。</p>
    <p>一个旧BEHAVE seed23的严格Query重放边界不一致已保留并标记；密集主对照不依赖该可见mask。HuMMan/BEHAVE已是消费过的开发证据，不据最佳分数挑新主模型。Native/HuMMan封存TEST未读。</p>
    <h2>实际检查与完整记录</h2><p>先导复现旧Official＋Txyz的raw/applied translation、fallback及独立指标，再生成全量A-only平移，之后打开B评价。全部失败与P95退化保留。完整记录可以从固定Body＋各方法camera重建Mesh，无需重新拟合。</p>
    <p><a href="RESULTS.json">分域、逐seed、逐人汇总</a> · <a href="ALL_FRAMES.csv">48708条逐帧表</a> · <a href="PAIRED_CONTRASTS.json">配对对照</a> · <a href="KNOWN_FAILURES.json">原fallback与已知失败身份</a> · <a href="REGION_RESULTS.json">部位proxy</a></p>'''
    for p in sorted(out.glob('failure_*.png')):body+='<img src="'+p.name+'">'
    css='body{font:15px/1.75 "Microsoft YaHei",sans-serif;background:#f4f7fa;color:#23364b;margin:0}main{max-width:1550px;margin:auto;padding:30px}h1{font-size:30px}h2{margin-top:36px}.lead{font-size:19px}.card{background:#dfedf1;padding:16px 24px;border-left:5px solid #20788d}.scroll{overflow-x:auto}table{border-collapse:collapse;background:white;width:100%}th,td{border:1px solid #cfdae3;padding:8px;text-align:left}th{background:#e4ebf2;white-space:nowrap}small{font-size:11px;white-space:nowrap;color:#607184}img{width:100%;margin:20px 0}'
    (out/'R52_零训练求解器对照.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>R5.2零训练对照</title><style>'+css+'</style><main>'+body+'</main></html>',encoding='utf-8')
    md+='\n## 限制\n\n本轮是几何后处理诊断，不是新网络。全部数值先逐帧再层级等权，不等于合并点的分位数。没有用B拟合或挑参数；不自动追加训练，不能证明解剖/穴位、真实Camera GT或论文创新性。完整逐人/每seed/P95和失败见HTML/JSON/CSV。\n'
    (out/'FINAL_REPORT.md').write_text(md,encoding='utf-8');print('REPORT_COMPLETE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
