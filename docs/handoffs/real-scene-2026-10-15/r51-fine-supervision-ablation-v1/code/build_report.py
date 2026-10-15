"""Readable, offline dataset-separated report; every seed and selection visible."""
import argparse,html,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'savefig.dpi':145})

ARMS=['Parent','E0','E1_half','E1_zero','E2_l2']
LABEL={'Parent':'原R5 Full Last初始化','E0':'E0：原监督继续训练','E1_half':'E1：Camera权重0.5','E1_zero':'E1：Camera权重0','E2_l2':'E2：仅增加L2步长正则'}
SEEDS=[11,23,37]
SELECTORS=['last','old_best','joint_best']
SLABEL={'last':'末轮：相同6轮预算','old_best':'原规则Best：Native顶点','joint_best':'联合规则Best：深度＋覆盖约束'}


def load(p):return json.loads(p.read_text(encoding='utf-8'))


def main(root):
    out=root/'reports';syn=load(out/'SYNTHETIC_RESULTS.json');real=load(out/'REAL_RESULTS.json')
    grad=load(out/'GRADIENT_LEDGER_ALL.json');train=load(out/'TRAINING_ALL.json');reference=load(out/'OFFICIAL_TXYZ_REFERENCE.json')
    identities=load(out/'PER_IDENTITY_LAST.json');reconcile=load(out/'AGGREGATION_RECONCILIATION.json')
    transfers=load(out/'CLASSIFICATION_TRANSFERS.json')['groups']
    def scell(arm,seed,selection):return next(r for r in syn if r['arm']==arm and r['seed']==seed and r['selection']==('parent' if arm=='Parent' else selection))
    def rcell(arm,seed,selection):return next(r for r in real if r['arm']==arm and r['seed']==seed and r['selection']==('parent' if arm=='Parent' else selection))
    def value(arm,seed,selection,dataset,field,role='VAL'):
        if dataset in ['native','scan']:return scell(arm,seed,selection)['domains'][dataset]['aggregate']['equal_mean'][field]
        group=next(g for g in rcell(arm,seed,selection)['groups'] if g['dataset']==dataset and (g['role']==role or dataset=='behave'))
        return group['metrics'][field]['equal_mean']
    def triple(arm,selection,dataset,field,role='VAL'):return np.array([value(arm,s,selection,dataset,field,role) for s in SEEDS])
    def cell(a,percent=False):
        a=np.asarray(a)*(100 if percent else 1);precision=2
        return f'<b>{a.mean():.{precision}f} ± {a.std(ddof=1):.{precision}f}</b><br><small>11: {a[0]:.{precision}f} · 23: {a[1]:.{precision}f} · 37: {a[2]:.{precision}f}</small>'
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    specifications=[('native','VAL','Native合成VAL：50身份／400帧',[('对应顶点L2 mm','vertex_camera_mm'),('Camera参数L2 mm','camera_mm'),('全mask轴向Z median mm','full_mask_median_mm'),('全mask轴向Z P95 mm*','full_mask_p95_mm'),('命中率 %','hit_rate'),('轮廓IoU','iou')]),
        ('scan','VAL','纹理扫描合成VAL：3身份／768视图',[('全mask轴向Z median mm','full_mask_median_mm'),('全mask轴向Z P95 mm*','full_mask_p95_mm'),('共同命中median mm','common_median_mm'),('共同命中P95 mm','common_p95_mm'),('命中率 %','hit_rate'),('轮廓IoU','iou')]),
        ('real','TRAIN','真实HuMMan TRAIN：18人／192帧',[('B点→三角面median mm','median_mm'),('B点→三角面P95 mm','p95_mm'),('≤50mm覆盖率 %','coverage_50mm')]),
        ('real','VAL','真实HuMMan VAL：4人／40帧',[('B点→三角面median mm','median_mm'),('B点→三角面P95 mm','p95_mm'),('≤50mm覆盖率 %','coverage_50mm')]),
        ('behave','test','真实BEHAVE：3人／270帧，已消费子集',[('K1/K2/K3表面median mm','median_mm'),('K1/K2/K3表面P95 mm','p95_mm'),('≤50mm覆盖率 %','coverage_50mm'),('拟合SMPL参考PVE mm','pve_mm')])]
    panels=[]
    for selection in SELECTORS:
        sections=[]
        for dataset,role,title,fields in specifications:
            rows=[]
            for arm in ARMS:
                rows.append([html.escape(LABEL[arm])]+[cell(triple(arm,selection,dataset,field,role),field in ['hit_rate','coverage_50mm']) for _,field in fields])
            if dataset in ['real','behave']:
                def baseline(field,seed):
                    r=next(r for r in reference if r['dataset']==dataset and r['seed']==seed and (r['role']==role or dataset=='behave'))
                    name=field if dataset=='real' or field=='pve_mm' else 'surface_'+field
                    return r['metrics'][name]['equal_mean']
                rows.append(['Official＋历史Txyz参考']+[cell([baseline(field,s) for s in SEEDS],field=='coverage_50mm') for _,field in fields])
            sections.append('<h3>'+title+'</h3>'+table(['方法']+[a for a,b in fields],rows))
        panels.append('<section class="panel" id="'+selection+'"'+(' hidden' if selection!='last' else '')+'><h2>'+SLABEL[selection]+'</h2>'+''.join(sections)+'</section>')
    # Four physically different Native measurements stay on separate axes.
    fig,axes=plt.subplots(1,4,figsize=(16,4.2),layout='constrained')
    for ax,(key,title) in zip(axes,[('vertex_camera_mm','对应顶点L2'),('camera_mm','Camera参数L2'),('full_mask_median_mm','全mask轴向Z median'),('orthogonal_mm','Fine正交分量（均值）')]):
        a=np.array([triple(arm,'last','native',key) for arm in ARMS]);x=np.arange(5)
        ax.bar(x,a.mean(1),yerr=a.std(1,ddof=1),capsize=3,color=['#a6b4c4','#4c769c','#279a8e','#d3a358','#a87f9b'])
        ax.set_xticks(x,['初始','E0','E1 .5','E1 0','E2'],rotation=20);ax.set_title(title);ax.set_ylabel('mm')
        for i,v in enumerate(a.mean(1)):ax.text(i,v+2,f'{v:.1f}',ha='center',fontsize=9)
        ax.set_ylim(0,float((a.mean(1)+a.std(1,ddof=1)).max())*1.28)
    fig.suptitle('相同末轮预算：表面／顶点改善与Camera参数退化可能同时发生；误差条为3 seed样本标准差')
    fig.savefig(out/'native_tradeoff.png');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
    for ax,seed in zip(axes,SEEDS):
        for arm in ['E0','E1_half','E2_l2']:
            rr=[r for r in grad if r['seed']==seed and r['arm']==arm]
            ax.plot([r['epoch'] for r in rr],[r['native']['last_layer']['camera_surface_cosine'] for r in rr],marker='o',label=arm)
        ax.axhline(0,color='black',lw=.8);ax.set(ylim=(-1.05,.15),title='seed '+str(seed),xlabel='续训epoch',ylabel='Camera / Surface 梯度余弦');ax.legend(fontsize=8)
    fig.suptitle('固定8张Native TRAIN探针、Fine最后层的批次梯度；负值表示局部更新方向相反')
    fig.savefig(out/'gradient_cosines.png');plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,7),layout='constrained')
    for j,seed in enumerate(SEEDS):
        for arm in ARMS[1:]:
            rr=next(r for r in train if r['arm']==arm and r['seed']==seed)['curves']
            axes[0,j].plot([r['epoch'] for r in rr],[r['train_loss'] for r in rr],marker='.',label=arm)
            vv=[r for r in rr if 'validation' in r]
            axes[1,j].plot([r['epoch'] for r in vv],[r['validation']['selection']['joint'] for r in vv],marker='o',label=arm)
        axes[0,j].set(title='seed '+str(seed),xlabel='epoch',ylabel='各自加权TRAIN loss');axes[0,j].legend(fontsize=8)
        axes[1,j].set(xlabel='epoch',ylabel='联合VAL分数（越低越好）');axes[1,j].axhline(1,color='black',lw=.8)
    fig.suptitle('有限续训曲线：各组loss定义不同，不横比loss高低；联合VAL使用同一预冻结公式')
    fig.savefig(out/'training_curves.png');plt.close(fig)
    idrows=[]
    for identity in sorted({r['identity'] for r in identities if r['dataset']=='real' and r['role']=='VAL'}):
        rr=[r for r in identities if r['dataset']=='real' and r['role']=='VAL' and r['identity']==identity]
        row=[identity]
        for arm in ARMS[1:]:
            subset=[r for r in rr if r['arm']==arm]
            row.append(' / '.join(f'{np.mean([r[k] for r in subset]):.3f}' for k in ['median_mm','p95_mm']))
        idrows.append(row)
    selection_rows=[]
    for seed in SEEDS:
        for arm in ARMS[1:]:
            r=next(r for r in train if r['arm']==arm and r['seed']==seed)['result']
            selection_rows.append([arm,str(seed),str(r['old_best_epoch']),str(r['joint_best_epoch']),'6'])
    transition_rows=[]
    for dataset,metric,role in [('native','camera_mm','VAL'),('real','median_mm','VAL'),('behave','pve_mm',None),('behave','surface_median_mm',None)]:
        for arm in ARMS[1:]:
            rr=[r for r in transfers if r['dataset']==dataset and r['metric']==metric and r['arm']==arm and r['selection']=='last' and (role is None or r['role']==role)]
            rr=sorted(rr,key=lambda r:r['seed']);transition_rows.append([dataset+'/'+metric,arm]+[' / '.join(str(r[k]) for r in rr) for k in ['old_worse','rescued','newly_worse','new_worse']])
    findings=[]
    for dataset,role,field,label in [('real','VAL','median_mm','HuMMan VAL median'),('real','VAL','p95_mm','HuMMan VAL P95'),('behave','test','median_mm','BEHAVE held-out median'),('behave','test','pve_mm','BEHAVE拟合参考PVE')]:
        for arm in ARMS[2:]:
            d=triple(arm,'last',dataset,field,role)-triple('E0','last',dataset,field,role)
            findings.append(f'{label}，{arm}相对同预算E0：平均变化{d.mean():+.3f} mm；seed11/23/37分别{d[0]:+.3f}/{d[1]:+.3f}/{d[2]:+.3f}，{sum(d<0)}/3 seed改善。')
    body='''<h1>R5.1：固定Coarse的Fine监督消融</h1><p class="lead">12组有限实验已完成。只改Camera监督或增加L2，不训练Body、不改Coarse、不增加模型结构，也不给新模型外挂Txyz。</p>
<div class="card"><b>读表先分清误差</b><p>Native是合成真值对应顶点／Camera参数误差；Scan是渲染表面对clean深度的轴向Z误差；HuMMan是独立B相机实测点到预测三角面；BEHAVE同时报独立三相机表面距离与拟合SMPL参考PVE。它们不能合成一个总分，也都不是穴位误差。</p><p>每格大字为3 seed均值±样本标准差，小字给出每个seed。默认显示相同6轮预算的末轮；两套Best完整保留，没有预注册“必须选末轮”或事后隐藏不利选择。</p></div>
<div class="card"><b>结论先说清楚</b><p>Camera权重2→0.5只有很小的真实收益：HuMMan VAL 14.246→14.202 mm（0.044 mm），BEHAVE独立表面19.682→19.640 mm（仅2/3 seed改善）。完全去掉Camera监督虽改善Native，却让真实HuMMan VAL三seed全部变差。简单L2也没有稳定收益，联合选模三seed都退回原父模型。</p><p>这轮不支持“删掉Camera监督就能解决问题”，也没有消灭Fine的负收益帧。不启动E1+E2组合或新长跑。保留原R5和权重0.5候选，不宣称超过Official+Txyz。</p></div>
<h2>1. 训练了什么，没训练什么</h2><p>从原Full Last的seed11/23/37分别继续训练，同seed四组初始化、数据顺序、Coarse输出及可见Query完全相同。只更新rgb_local、local、fine_head。不同seed的父模型不同，这是配对续训筛查，不是3次从头训练。</p><p>额外训练：Native原TRAIN按身份哈希取64人×8张=512张；Scan原TRAIN按asset×camera-group比例取768张（9身份）。原父模型此前见过完整Native400训练身份和完整Scan训练集。每组6轮，AdamW恒定lr=1e-4、weight decay=1e-4；每步Native16＋Scan24，microbatch4。每组7个epoch权重均保留，在0/2/4/6轮评价。没有声称已收敛或学习率最优。</p>
<p>E0 Camera权重2；E1_half为0.5（实际是E0权重的四分之一，代码名不代表减半）；E1_zero为0；E2保持E0并加简单公制步长L2。Native Z/轮廓权重0.2/0.2；Scan为1.0664188982/4.6202386224。L2 λ=0.5933867854，只由TRAIN 32 Native＋32 Scan在初始最后层梯度标定为10%，不是按真实B效果挑选，也没有假设10–15mm噪声阈值。</p>
<h2>2. 同预算末轮的Native取舍</h2><img src="native_tradeoff.png"><p>身体网格固定，所以顶点/表面分数变化来自平移。Camera参数误差下降与工作表面改善不能互相代替。正交是相对Coarse→GT平移方向而言，不是相对后背法线，不能直接叫背部切向滑动；图中为均值，不能与旧报告8–9mm的中位数混比。</p>
<h2>3. 全部数据集、全部seed与三种取权重方式</h2><nav>'''+''.join('<button onclick="pick(\''+s+'\')">'+SLABEL[s]+'</button>' for s in SELECTORS)+'</nav>'+''.join(panels)+'''
<p class="note">*全mask未命中像素按渲染Z=0计入。因此Native/Scan的full-mask P95可能有数米的漏覆盖惩罚，不能理解为已命中表面精度。共同命中必须连同命中率与IoU阅读。表中median/P95都是先逐帧计算，再按层级等权汇总，不是把所有点混在一起取分位数。HuMMan/BEHAVE先frame→sequence→identity；BEHAVE每帧先对三相机各自分位数取等权均值。Scan为frame→camera-group→asset→identity，各层等权。</p>
<p>Official＋Txyz是相同旧点集的历史强参考；HuMMan是共享Official缓存，三列复用配对参考，不冒充三次独立Official推理。BEHAVE保留原三seed参考差异。真实数据均已在历史分析中消费，不称全新泛化；封存Native/HuMMan TEST未读。BEHAVE物体遮挡、异常Depth及拟合参考偏差均保留，不能据此宣称裸背毫米精度或超过M³。</p>
<h2>4. 固定的选模规则与实际选到哪一轮</h2><p>旧规则：最小Native身份等权对应顶点误差。联合规则：Native与Scan的full-mask Z median分别除以同seed初值，两个比值等权平均；要求每个域的命中率和IoU均不低于初值1个百分点。可选epoch0，平分取早。epoch0意味着仍选原父模型。所有选模结果在打开新真实评价前冻结。</p>'''+table(['组','seed','旧Best epoch','联合Best epoch','Last epoch'],selection_rows)+'''
<img src="training_curves.png"><p>联合选模并非总能迁移：例如权重0.5、seed23旧规则选epoch4，HuMMan VAL median为14.939 mm；联合规则选epoch6，为15.056 mm。有限6轮不证明学习率最优，也不证明已收敛。</p>
<h2>5. 实测梯度账本</h2><img src="gradient_cosines.png"><p>这里测的是固定8张Native TRAIN探针批次、Fine最后层的加权Camera与Z＋轮廓梯度。E0的12个检查点均为负，支持这些探针处存在局部目标竞争；不证明所有训练样本、全部网络层或全部历史错误都由它造成。E1_zero的加权Camera梯度为0，余弦未定义，没有伪造为0相关。完整范数、Z/轮廓各项、Scan与L2均保留在账本。</p>
<h2>6. 救回旧坏帧，也检查新弄坏哪些帧</h2><p>以下三数字按seed11 /23 /37排列；同预算末轮对照。旧坏帧按原Coarse→Fine名单保留，“救回”指新误差不再高于同帧原Coarse；“新增坏”指原先未坏但现在高于Coarse。Native Camera与BEHAVE PVE标签不能冒充独立表面负收益。</p>'''+table(['数据／指标','组','旧坏','救回旧坏','新增坏','当前坏'],transition_rows)+'''
<h2>7. 真实开发集的逐项结论</h2><ul>'''+''.join('<li>'+html.escape(f)+'</li>' for f in findings)+'''</ul><p>判断稳定优势必须同时看P95、逐身份和选择规则，不能只选最好的seed或单个median。上述是已消费开发数据上的描述性对照；没有临床或解剖准确度结论。</p>
<h3>HuMMan VAL逐人：三seed平均，median / P95，单位mm</h3>'''+table(['身份','E0','Camera .5','Camera 0','L2'],idrows)+'''
<p>p001194与p001201的P95在权重0.5下仍恶化，不能只看四人平均。已知TRAIN失败身份p001195也没有被这一轮整体救回；每个身份、部位proxy与seed均见<a href="PER_IDENTITY_LAST.json">逐人表</a>和<a href="REGION_LAST.json">部位表</a>。</p>
<h3>为什么这里BEHAVE父模型是59.64 mm，旧报告却是61.06 mm？</h3><p>同一270帧按帧平均为61.0636 mm；按本轮冻结的frame→sequence→identity等权为59.6396 mm。旧报告也保存过两种口径；本轮逐帧复算相符，没有把权重变化算成模型提升。Official+Txyz分别为56.2400 /55.7337 mm。<a href="AGGREGATION_RECONCILIATION.json">完整对账</a>。</p>
<h2>8. 失败图与审计</h2><p>失败图单独列出相同B点集和同一坐标中的Mesh。没有用B对齐、优化、选择损失或checkpoint。完整RGB→Official Backbone/Decoder端到端耗时仍未测；本轮缓存训练速度不能替代完整系统速度。</p><div id="figures">'''
    for p in sorted(out.glob('failure_case_*.png')):body+='<img src="'+p.name+'">'
    body+='</div><p><a href="SYNTHETIC_RESULTS.json">合成分域分seed汇总</a> · <a href="REAL_RESULTS.json">真实汇总</a> · <a href="REAL_JOBS.json">全部真实逐帧结果</a> · <a href="CLASSIFICATION_TRANSFERS.csv">完整分类转移</a> · <a href="NATIVE_FRAME_RESULTS.csv">Native逐帧</a> · <a href="SCAN_FRAME_RESULTS.csv">Scan逐帧</a> · <a href="GRADIENT_LEDGER_ALL.json">梯度账本</a></p>'
    css='body{font:16px/1.75 "Microsoft YaHei",sans-serif;color:#22354d;background:#f5f8fb;margin:0}main{max-width:1500px;margin:auto;padding:28px}h1{font-size:30px}h2{margin-top:36px}h3{margin-top:25px}.lead{font-size:19px}.card{padding:15px 24px;background:#e5f1f2;border-left:5px solid #20818d}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:9px;border:1px solid #d4dee7;text-align:left}th{background:#e8edf4}small{font-size:11px;color:#53667a;white-space:nowrap}.scroll{overflow-x:auto}img{width:100%;margin:18px 0}nav{position:sticky;top:0;background:#f5f8fb;padding:12px 0;z-index:2}button{font:inherit;padding:9px;margin-right:10px;border:1px solid #c0d3df;border-radius:6px;background:white;cursor:pointer}.note{color:#854b31}@media print{.panel[hidden]{display:block}nav{display:none}}'
    script="function pick(id){document.querySelectorAll('.panel').forEach(e=>e.hidden=e.id!==id)}"
    (out/'R51_监督消融完整结果.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>R5.1监督消融完整结果</title><style>'+css+'</style><main>'+body+'</main><script>'+script+'</script></html>',encoding='utf-8')
    md='# R5.1有限监督消融结果\n\n12组均完成，原Body与Coarse固定。配对初始化和6轮数据顺序一致；两套选模在真实评价前冻结。\n\n'
    md+='同预算末轮，三seed均值：\n\n|组|Native顶点mm|Native Camera mm|Native Z median mm|Scan Z median mm|HuMMan VAL median/P95 mm|BEHAVE held-out median/P95 mm|BEHAVE拟合参考PVE mm|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for arm in ARMS:
        mean=lambda d,k,role='VAL':float(triple(arm,'last',d,k,role).mean())
        row=[LABEL[arm],f"{mean('native','vertex_camera_mm'):.3f}",f"{mean('native','camera_mm'):.3f}",f"{mean('native','full_mask_median_mm'):.3f}",f"{mean('scan','full_mask_median_mm'):.3f}",f"{mean('real','median_mm'):.3f} / {mean('real','p95_mm'):.3f}",f"{mean('behave','median_mm'):.3f} / {mean('behave','p95_mm'):.3f}",f"{mean('behave','pve_mm'):.3f}"]
        md+='|'+'|'.join(row)+'|\n'
    md+='\n'+ '\n\n'.join(findings)+'\n\n完整HTML给出每个seed和三种权重选择，不据单项开发指标宣布最终模型。以上误差口径不同，不合并。6轮有限续训不等于充分训练；未自动组合正则或追加训练。\n\n详细解释、逐人复核、历史61.06与本轮59.64对账和后续决策见[ANALYSIS.md](ANALYSIS.md)。\n'
    (out/'FINAL_REPORT.md').write_text(md,encoding='utf-8');print('REPORT_COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
