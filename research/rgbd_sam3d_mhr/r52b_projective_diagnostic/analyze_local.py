"""Descriptive evidence, all prescribed arms retained; no B-driven model selection."""
import argparse,json
from pathlib import Path
import numpy as np


def main(root):
    out=root/'reports';cells=json.loads((out/'RESULTS.json').read_text(encoding='utf-8'))
    frames=json.loads((out/'FRAME_RESULTS.json').read_text(encoding='utf-8'))
    pairs=json.loads((out/'PAIRED_CONTRASTS.json').read_text(encoding='utf-8'))
    def mean(m,d,r,k):return float(np.mean([c['metrics'][k]['equal_mean'] for c in cells if (c['method'],c['dataset'],c['role'])==(m,d,r)]))
    bh=next(c['role'] for c in cells if c['dataset']=='behave')
    cohorts=[('native','VAL','Native VAL','vertex_camera_mm'),('real','TRAIN','HuMMan TRAIN','median_mm'),('real','VAL','HuMMan VAL','median_mm'),('behave',bh,'BEHAVE','median_mm')]
    lines=['# R5.2b：分析账本','',
        '这是固定Body的零训练平移诊断，不能把新增分支称为新的单前向网络。三seed是原父模型不同起点；真实域都已作为开发证据使用。',
        '', '## 1. 主对照：同样重投影3步，中位数换成点面LS','',
        '逐帧→序列→身份等权后再对三个seed求均值。负变化表示改善。每帧/每seed数值完整保留，未剔除任何失败。','']
    conclusion=json.loads((out/'CONCLUSION.json').read_text(encoding='utf-8'))
    lines[2:2]=['## 裁决',conclusion['verdict'],'']+['- '+s for s in conclusion['bullets']]+['','下一步：'+conclusion['next_step'],'']
    for d,r,title,k in cohorts:
        a=mean('proj_med3',d,r,k);b=mean('proj_plane3',d,r,k)
        rr=[p for p in pairs if (p['contrast'],p['dataset'],p['role'])==('PRIMARY_median_to_plane3',d,r)]
        line=f'- {title}：{a:.3f} → {b:.3f} mm，变化{b-a:+.3f} mm；改善帧数11/23/37：'+ '/'.join(str(p['improved_frames']) for p in rr)+'，退化帧数：'+ '/'.join(str(p['worsened_frames']) for p in rr)+'。'
        if d!='native':line+=f" P95：{mean('proj_med3',d,r,'p95_mm'):.3f} → {mean('proj_plane3',d,r,'p95_mm'):.3f} mm。"
        lines.append(line)
    lines+=['','## 2. 不能只看一个最好分数','', '|方法|HuMMan TRAIN median/P95|HuMMan VAL median/P95|BEHAVE median/P95|','|---|---|---|---|']
    cfg=json.loads((root/'EXPERIMENT.json').read_text(encoding='utf-8'))
    for m in cfg['methods']:
        values=[f"{mean(m,d,r,'median_mm'):.3f}/{mean(m,d,r,'p95_mm'):.3f}" for d,r in [('real','TRAIN'),('real','VAL'),('behave',bh)]]
        lines.append('|'+m+'|'+'|'.join(values)+'|')
    lines+=['','## 3. 鲁棒权重、方向衰减与密度','',
        '下面均为预先固定的单变量对照；Huber不是看到B尾部后调出来的权重。原点面LS已经去除20%最大欧氏残差，新增Huber是对保留的法向拟合误差进行再加权。', '']
    for contrast in ['GATE_only','HUBER_after_trim','REMOVE_trim','HUBER_without_trim','DENSITY256_to_1024','DENSITY1024_to_4096']:
        lines.append('**'+contrast+'**')
        for d,r,title,k in cohorts:
            pp=[p for p in pairs if (p['contrast'],p['dataset'],p['role'])==(contrast,d,r)]
            lines.append('- '+title+'：Δmedian/顶点 '+f"{np.mean([p['aggregate_delta_mm'] for p in pp]):+.3f} mm"+(f"；ΔP95 {np.mean([p['p95_delta_mm'] for p in pp]):+.3f} mm" if d!='native' else '')+'。')
    index={(f['dataset'],f['seed'],f['key'],f['method']):f for f in frames}
    details=[]
    for f in frames:
        if f['dataset']=='native':continue
        if f['method'] not in ['proj_plane3','proj_trim_huber3','proj_4096_plane3']:continue
        fine=index[f['dataset'],f['seed'],f['key'],'fine'];off=index[f['dataset'],f['seed'],f['key'],'official_hist6']
        details.append(dict(dataset=f['dataset'],role=f['role'],seed=f['seed'],key=f['key'],identity=f['identity'],method=f['method'],
            delta_median_vs_fine_mm=f['median_mm']-fine['median_mm'],delta_p95_vs_fine_mm=f['p95_mm']-fine['p95_mm'],
            delta_median_vs_official_txyz_mm=f['median_mm']-off['median_mm'],delta_p95_vs_official_txyz_mm=f['p95_mm']-off['p95_mm']))
    (out/'SYSTEM_FRAME_CHANGES.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    lines+=['','## 已知失败身份：median改善也可能伴随P95恶化','',
        '|身份|原Fine median/P95|投影点面3步|1024候选3步|旧密集NN点面6步|Official+Txyz|','|---|---|---|---|---|---|']
    for identity in ['p001195','p001196']:
        values=[]
        for m in ['fine','proj_plane3','proj_1024_plane3','hist_plane6','official_hist6']:
            rr=[c for c in cells if c['dataset']=='real' and c['method']==m and identity in c['metrics']['median_mm']['per_identity']]
            a=np.mean([c['metrics']['median_mm']['per_identity'][identity]['mean'] for c in rr]);b=np.mean([c['metrics']['p95_mm']['per_identity'][identity]['mean'] for c in rr])
            values.append(f'{a:.3f}/{b:.3f}')
        lines.append('|'+identity+'|'+'|'.join(values)+'|')
    lines+=['','p001195的Coarse定位仍有价值，但投影点面没有超过旧密集点面；p001196的median下降时P95仍可能升高。不能把这两种改善都解释为真正的Camera参数更准。',
        '', '## 4. 这些数字能说明什么，不能说明什么','',
        '1. 同配置配对可以说明换求解算子、步数、权重或采样预算对该实验结果的影响；不能仅由B分数证明某个对应一定落在正确解剖位置。',
        '2. 多步路径每次重新计算对应和可见性，后续输入会因前一步更新变化。结果差异不只是某个静态残差上的线性叠加。',
        '3. 256/1024/4096是嵌套候选预算，实际可见数和法线谱见QUERY_DIAGNOSTICS.json。点更多不等于信息更可靠，也不自动补足平面切向约束。',
        '4. 这里的点面法线来自预测Mesh，可能包含人体形状误差。可见性阈值检查Mesh自遮挡，不等于识别人前面的场景物体。Huber20mm是预注册工程尺度，不是传感器噪声真值。权重小也不能直接解释为识别了衣物或物体。',
        '5. 真实域B是固定点到三角面距离；BEHAVE拟合参考PVE是支持证据。更低表面距离不能证明真实Camera根节点、Pose/Shape解剖对应或穴位更准。',
        '6. 原密集NN点面参考使用历史A5000点；投影分支使用原缓存Depth。两者同时改变了点源和匹配方式，不能把其差别全归于LS。',
        '7. 全部失败、超限回退及P95退化保留。所谓“精确上限”和“全域绝对赢家”均不成立。负收益转移表中Native按vertex_camera_mm分类，真实域按median_mm分类；不要与旧Native Camera负收益名单混用。',
        '8. 本轮没有重新计时完整RGB-D→Mesh，也未新增RGB轮廓IoU评价；离线缓存求解耗时不能冒充端到端推理时延。', '',
        '## 5. 下一步限制','',
        '本轮不自动启动逐点置信度网络。只有跨seed、逐身份、尾部和实际任务收益共同支持，才考虑另立受控训练；还必须说明权重监督来源、退化处理与经典鲁棒基线。单独把经典LS换成可微层不是已成立的论文创新。',
        '', '文献：[KinectFusion, ISMAR2011](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ismar2011.pdf)明确采用投影关联和点面ICP。本轮只做translation，不能宣称等价于完整6DoF KinectFusion。']
    (out/'ANALYSIS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
