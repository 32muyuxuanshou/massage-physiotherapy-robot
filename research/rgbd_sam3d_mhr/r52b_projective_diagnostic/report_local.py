"""Cohort-separated readable tables and predeclared paired changes."""
import argparse,html,json
from pathlib import Path
import numpy as np
LABEL={
 'official_hist6':'Official＋历史Txyz（旧参考）','coarse':'同Full内部Coarse','fine':'原Full Last Fine','hist_plane6':'Coarse＋密集NN点面6步（旧参考）',
 'proj_vis_med1':'投影／截断中位数1步','proj_med2':'投影／截断中位数2步','proj_med3':'投影／截断中位数3步','proj_med6':'投影／截断中位数6步',
 'proj_plane1':'投影／截断点面1步','proj_plane2':'投影／截断点面2步','proj_plane3':'投影／截断点面3步','proj_plane6':'投影／截断点面6步',
 'proj_gate3':'截断点面3步＋方向衰减','proj_trim_huber3':'截断点面3步＋Huber','proj_plain3':'无截断点面3步','proj_huber3':'无截断点面3步＋Huber',
 'proj_1024_plane3':'1024候选／截断点面3步','proj_4096_plane3':'4096候选／截断点面3步'}


def main(root):
    out=root/'reports';cells=json.loads((out/'RESULTS.json').read_text(encoding='utf-8'));pairs=json.loads((out/'PAIRED_CONTRASTS.json').read_text(encoding='utf-8'))
    cfg=json.loads((root/'EXPERIMENT.json').read_text(encoding='utf-8'))
    def get(m,d,r,k):
        a=sorted([c for c in cells if (c['method'],c['dataset'],c['role'])==(m,d,r)],key=lambda c:c['seed'])
        return np.array([c['fallback'] if k=='fallback' else c['metrics'][k]['equal_mean'] for c in a])
    def fmt(a):return '<b>%.3f ± %.3f</b><br><small>11/23/37：%s</small>'%(a.mean(),a.std(ddof=1),' / '.join('%.3f'%v for v in a))
    def table(head,rows):return '<div class="scroll"><table><tr>'+''.join('<th>'+h+'</th>' for h in head)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table></div>'
    bh=next(c['role'] for c in cells if c['dataset']=='behave')
    cohorts=[('native','VAL','Native合成VAL：50身份400帧',['vertex_camera_mm','camera_mm','vertex_p95_mm']),
        ('real','TRAIN','HuMMan真实开发TRAIN：18人192帧',['median_mm','p95_mm','coverage_50mm']),
        ('real','VAL','HuMMan真实开发VAL：4人40帧',['median_mm','p95_mm','coverage_50mm']),
        ('behave',bh,'BEHAVE已消费子集：3人90序列270帧',['median_mm','p95_mm','coverage_50mm','pve_mm'])]
    names={'vertex_camera_mm':'对应顶点均值mm','camera_mm':'Camera参数L2 mm','vertex_p95_mm':'顶点P95 mm','median_mm':'独立表面median mm','p95_mm':'独立表面P95 mm','coverage_50mm':'≤50mm覆盖率%','pve_mm':'拟合参考PVE mm'}
    body='<h1>R5.2b：投影点面求解补充验证</h1><p class="lead">18方法 × 3个父模型seed；2706帧状态，48708条评价。零训练，只改平移，Body保持Official原样。</p>'
    conclusion=json.loads((out/'CONCLUSION.json').read_text(encoding='utf-8'))
    body+='<div class="card"><b>'+html.escape(conclusion['verdict'])+'</b><ol>'+''.join('<li>'+html.escape(s)+'</li>' for s in conclusion['bullets'])+'</ol><p><b>下一步：</b>'+html.escape(conclusion['next_step'])+'</p><p>见<a href="ANALYSIS.md">完整逐项分析</a>。这不是新的单前向模型。</p></div>'
    body+='<nav>'+''.join('<a href="#cohort%d">%s</a>　'%(i,t[2].split('：')[0]) for i,t in enumerate(cohorts))+'</nav>'
    body+='<p>256/1024/4096是可见性筛选前候选数。每步重新投影和光栅化；相同A深度/有效mask、原相机合同，B不参与拟合。三seed反映既有父模型起点差异，不是本轮重新训练。</p>'
    md='# R5.2b：零训练投影点面验证\n\n每个方法仅改变translation，保留所有帧。完整分析见ANALYSIS.md。\n\n'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':140})
    fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
    for col,(d,r,title,fields) in enumerate(cohorts):
        headers=['方法']+[names[k] for k in fields]+['fallback 11/23/37'];rows=[]
        md+='## '+title+'\n\n|'+'|'.join(headers)+'|\n|'+'---|'*len(headers)+'\n'
        for m in cfg['methods']:
            aa=[get(m,d,r,k)*(100 if k=='coverage_50mm' else 1) for k in fields]
            fb='不适用' if m in ['coarse','fine'] else ' / '.join(str(int(v)) for v in get(m,d,r,'fallback'))
            rows.append([LABEL[m]]+[fmt(a) for a in aa]+[fb])
            md+='|'+LABEL[m]+'|'+'|'.join('%.3f ± %.3f'%(a.mean(),a.std(ddof=1)) for a in aa)+'|'+fb+'|\n'
        body+='<h2 id="cohort%d">'%col+title+'</h2>'+table(headers,rows)
        for row,field in enumerate(fields[:2]):
            ax=axes[row,col]
            for prefix,color in [('proj_plane','#156f88'),('proj_med','#bf6b2c')]:
                a=np.array([get('proj_vis_med1' if prefix=='proj_med' and n==1 else prefix+str(n),d,r,field) for n in [1,2,3,6]])
                ax.errorbar([1,2,3,6],a.mean(1),yerr=a.std(1,ddof=1),marker='o',color=color,label='点面LS' if prefix=='proj_plane' else '逐轴中位数')
            for m,color in [('fine','#46576b'),('official_hist6','#9c426a')]:ax.axhline(get(m,d,r,field).mean(),ls='--',color=color,label=LABEL[m])
            ax.set(title=title if row==0 else names[field],xticks=[1,2,3,6],xlabel='重投影步数',ylabel=names[field]);ax.legend(fontsize=7)
    fig.savefig(out/'iterations.png');plt.close(fig)
    body+='<h2>多步是否持续改善</h2><img src="iterations.png">'
    pp=[]
    for p in pairs:
        if p['seed']!=11:continue
        rr=sorted([a for a in pairs if (a['contrast'],a['dataset'],a['role'])==(p['contrast'],p['dataset'],p['role'])],key=lambda a:a['seed'])
        pp.append([p['contrast'],p['dataset']+'/'+p['role'],fmt(np.array([a['aggregate_delta_mm'] for a in rr])),' / '.join(str(a['improved_frames']) for a in rr),' / '.join(str(a['worsened_frames']) for a in rr)])
    body+='<h2>配对变化：后者减前者，负值表示误差降低</h2>'+table(['对比','数据','Δmm 均值±SD/逐seed','改善帧11/23/37','退化帧11/23/37'],pp)
    body+='''<h2>误差怎么算</h2><p>Native：相同顶点编号的三维距离均值、顶点P95和Camera参数L2。真实数据：固定独立相机点→预测Mesh三角面的精确最短距离。BEHAVE的PVE只是相对作者拟合SMPL参考，不是绝对皮肤或解剖真值。</p>
    <p>先算每帧median/P95，再frame→sequence→identity等权；BEHAVE先三台相机等权。表中P95不是所有点合并后的总体P95。不同域的数值不互相混合。</p>
    <h2>边界与可复查证据</h2><p>Huber固定20mm、3次IRLS；方向衰减单列。单步每轴50mm、总修正177.888mm，超限回原Coarse。原Fine参考不额外套该上限。记录raw/applied/fallback及每步可见anchor编号、法线谱、残差、权重；保存原A输入和最终网格重建参数。</p>
    <p>这是已消费开发集上的机制探索，不是精确上限，也不是临床或穴位精度证明。投影点面ICP是经典方法；法向投影不保证对应正确。封存Native/HuMMan TEST未读。一个历史BEHAVE seed23可见性边界帧保留，不删除。</p>
    <p><a href="RESULTS.json">逐seed/逐身份</a> · <a href="ALL_FRAMES.csv">完整逐帧表</a> · <a href="PAIRED_CONTRASTS.json">配对对照</a> · <a href="QUERY_DIAGNOSTICS.json">实际可见数与法线谱</a> · <a href="NEGATIVE_UPDATE_TRANSFERS.csv">负收益转移</a> · <a href="KNOWN_FAILURES.json">已知失败身份</a></p>'''
    body+='<h2>A端实际对应与残差</h2>'
    for p in sorted(out.glob('query_*.png')):body+='<img src="'+p.name+'">'
    body+='<h2>独立B端表面与失败例</h2>'
    for p in sorted(out.glob('failure_*.png')):body+='<img src="'+p.name+'">'
    css='body{font:15px/1.7 Microsoft YaHei,sans-serif;color:#24374b;background:#f3f6fa;margin:0}main{max-width:1550px;margin:auto;padding:30px}h1{font-size:30px}h2{margin-top:40px;scroll-margin-top:70px}nav{position:sticky;top:0;background:#e4edf4;padding:12px;z-index:1}.lead{font-size:19px}.card{background:#dcecf1;padding:20px;border-left:5px solid #21798a}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #cbd6df;padding:8px}th{background:#e2eaf1;white-space:nowrap}small{font-size:11px;white-space:nowrap;color:#5e7182}img{max-width:100%;margin:20px 0}'
    (out/'R52B_投影点面验证.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>R5.2b投影点面验证</title><style>'+css+'</style><main>'+body+'</main></html>',encoding='utf-8')
    (out/'FINAL_REPORT.md').write_text(md+'\n\n完整解释与限制见ANALYSIS.md/HTML。\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
