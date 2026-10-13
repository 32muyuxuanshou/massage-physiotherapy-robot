"""Self-contained Chinese HTML; all cells stay separate, no outcome selection."""
import argparse
import json
from pathlib import Path
from collections import defaultdict
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    root = a.root.resolve()
    result = json.loads((root/'reports/AGGREGATED.json').read_text())
    records = []
    for file in sorted((root/'evaluation').glob('*/RESULTS.json')):
        records.extend(json.loads(file.read_text())['records'])
    names = ['official', 'official_txyz', 'rgb_only', 'g1', 'coarse', 'full']
    seeds = [11, 23, 37]
    def cell(mode, seed, ck):
        if mode == 'official': return f'official_s{seed}'
        if mode == 'official_txyz': return f'official_s{seed}_txyz'
        return f'{mode}_s{seed}_{ck}'
    tables = {}
    for ck in ['best', 'last']:
        tables[ck] = []
        for mode in names:
            rows = [result['cells'][cell(mode, s, ck)] for s in seeds]
            fields = {}
            for field in ['pve_absolute_mm', 'pve_centroid_centered_mm', 'pa_pve_similarity_mm',
                          'surface_median_mm', 'surface_p95_mm', 'surface_coverage_50mm']:
                aggregate = 'sequence_then_subject_equal_mean' if field.startswith('surface_') else 'frame_equal_mean'
                values = [r[aggregate][field] for r in rows]
                fields[field] = dict(mean=float(np.mean(values)), std=float(np.std(values, ddof=1)), values=values)
            tables[ck].append(dict(mode=mode, metrics=fields))
    lookup = {(r['cell'], r['sequence'], r['frame']): r for r in records}
    paired = {}
    for ck in ['best', 'last']:
        paired[ck] = []
        for mode in names:
            for seed in seeds:
                current = [r for r in records if r['cell'] == cell(mode, seed, ck)]
                deltas = []
                for r in current:
                    ref = lookup[f'official_s{seed}_txyz', r['sequence'], r['frame']]
                    deltas.append(r['frame_surface_camera_equal_mean']['p95_mm']-ref['frame_surface_camera_equal_mean']['p95_mm'])
                worst = sorted(zip(current, deltas), key=lambda x: x[1], reverse=True)[:10]
                paired[ck].append(dict(mode=mode, seed=seed, frames=len(current),
                    p95_worse_than_official_txyz=sum(d > 0 for d in deltas),
                    worst=[dict(sequence=r['sequence'], frame=r['frame'], subject=r['subject'],
                                delta_p95_mm=d, pve=r['pve'], surface=r['frame_surface_camera_equal_mean']) for r, d in worst]))
    translation = {str(seed): [r['txyz'] for r in records if r['cell'] == f'official_s{seed}_txyz'] for seed in seeds}
    translation_summary = {seed: dict(fallback=sum(r['fallback'] for r in rows), total=len(rows),
        raw_norm_median_mm=float(np.median([np.linalg.norm(r['raw_m'])*1000 for r in rows])),
        applied_norm_median_mm=float(np.median([np.linalg.norm(r['applied_m'])*1000 for r in rows]))) for seed, rows in translation.items()}
    payload = dict(result=result, tables=tables, paired=paired, translations=translation_summary,
                   frames=next(iter(result['cells'].values()))['frames'])
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>BEHAVE · R5 冻结对照</title>
<style>body{font:16px/1.65 system-ui,sans-serif;color:#172b42;background:#eef2f6;margin:0}main{max-width:1360px;margin:auto;padding:32px}h1{font-size:32px}h2{margin-top:30px}.card{background:white;padding:22px;margin:18px 0;border-radius:14px;box-shadow:0 2px 10px #0012}.tag{padding:7px 12px;background:#dde9f7;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;text-align:right;border-bottom:1px solid #e1e7ee}th:first-child,td:first-child{text-align:left}th{background:#f5f8fc}.small{font-size:14px;color:#536378}.warn{border-left:5px solid #db8615}.good{color:#087454}.bad{color:#b73333}button{font:inherit;padding:8px 18px;cursor:pointer;margin:0 8px 10px 0;border:1px solid #9bacbf;border-radius:8px;background:white}button.active{background:#184b80;color:white}summary{cursor:pointer}a{color:#1c639d}.scroll{overflow:auto}svg{max-width:100%}.barlabel{font:14px sans-serif}</style>
<main><h1>BEHAVE 上，R5 能否真的找到人体的位置？</h1>
<p class="tag" id="cohort"></p>
<div class="card warn"><b>先读这句话：</b>本页只报告 BEHAVE 固定子集；不与 HuMMan 或合成数据混成一个分数。拟合 SMPL 参考用于对应顶点评价，三台独立深度相机用于表面评价。两者含义不同，均不是穴位精度。</div>
<div class="card"><h2>这些数字是什么</h2>
<p><b>PVE：</b>把 MHR 用固定官方映射转换到 6,890 个 SMPL 顶点，与拟合参考的相应顶点逐个算三维距离；每帧取平均，再对全部帧取平均。保留实际相机位置，不先对齐。</p>
<p><b>去质心 PVE：</b>移除整体平移后看身体差异；不是去骨盆误差。<b>PA-PVE：</b>允许旋转、平移、缩放对齐的诊断，不能代表机器人实际定位精度。</p>
<p><b>独立表面距离：</b>K1/K2/K3 各 2,048 个固定实测点，到预测 Mesh 最近三角面的距离。先算各相机 median/P95，再按 camera → frame → sequence → subject 等权平均。这里的平均 P95 不是把所有点混合后的全局 P95。</p>
<p>模型输入和 Txyz 只用 K0。新模型展示原始输出；只有 Official 加历史 Txyz。R5 Coarse/Full 保留 Official 的全部身体参数，理论上只能改善位置。</p></div>
<div class="card"><h2>模型与 checkpoint 分开看</h2><button id="best" class="active" onclick="render('best')">Best</button><button id="last" onclick="render('last')">第 50 轮 Last</button>
<p class="small">Best 沿用既有训练阶段选定的 checkpoint，没有用 BEHAVE 结果再选。± 为三个 seed（11/23/37）的样本标准差。</p>
<div class="scroll" id="table"></div><div id="chart"></div><p id="analysis"></p></div>
<div class="card"><h2>每个 seed，每个人</h2><p class="small">以下表面指标与上表同口径。更低才更好。三个人历史上已被研究过；不能称全新泛化人物。</p><div class="scroll" id="subjects"></div></div>
<div class="card"><h2>负面结果与 Txyz 回退</h2><div id="translation"></div><p class="small">下面保留每个模型/seed 相比同 seed Official+Txyz 的 P95 恶化数，以及差值最大的 10 帧；选择只用于找失败，不影响评价或 checkpoint。</p><div id="failures"></div></div>
<div class="card"><h2>看图和复查</h2><p><a href="../visualizations/index.html">全部帧 · 三 seed · Best/Last 可视化索引（私有）</a>　<a href="AGGREGATED.json">完整汇总 JSON</a>　<a href="PER_FRAME.csv">逐帧表</a></p><p>蓝色是最终缓存 Mesh 的透视渲染。下三排是 K1/K2/K3 的原始传感器点残差，色值截断 150 mm 仅为显示；数值没有截断。图像不会重新拟合 Mesh。</p></div>
<div class="card warn"><h2>结论的边界</h2><p>270 帧来自官方 TEST 的 90 个 Date03 序列、三个身份，每序列固定三个时间点；不是完整 TEST。和历史 45 帧重合 25 帧。TEST 标签没有用于拟合、选 checkpoint 或改参数，但身份已经被历史分析使用。</p><p>M³ 论文报告 BEHAVE PVE 为 93.1 mm（AMASS 训练）和 70.9 mm（另在 BEHAVE TRAIN 微调）。作者对齐、采样、相机与汇总细节尚未完全核实，本页不得据此宣称同协议超越。</p><p>MHR→SMPL 是固定近似对应；BEHAVE person_fit 是拟合参考，不是直接测到的皮肤。表面贴合改善也不自动证明解剖对应、Pose/Shape 真值或穴位位置改善。</p></div></main>
<script>const D=__DATA__;
const labels={official:'Official',official_txyz:'Official + Txyz',rgb_only:'RGB-only',g1:'G1',coarse:'R5 Coarse',full:'R5 Full'};
const fs=['pve_absolute_mm','pve_centroid_centered_mm','pa_pve_similarity_mm','surface_median_mm','surface_p95_mm','surface_coverage_50mm'];
const titles=['PVE mm','去质心 PVE mm','PA-PVE mm','独立表面 median mm','独立表面 P95 mm','≤50 mm 覆盖率'];
const fmt=(x,f)=>((f.includes('coverage')?100:1)*x).toFixed(2)+(f.includes('coverage')?'%':'');
const cell=(m,s,c)=>m==='official'?`official_s${s}`:m==='official_txyz'?`official_s${s}_txyz`:`${m}_s${s}_${c}`;
document.getElementById('cohort').textContent=`BEHAVE | ${D.frames} 固定帧 | ${Object.keys(D.result.cells).length} 模型/种子/checkpoint 组合 | 单位：mm | 不训练`;
function render(ck){document.getElementById('best').classList.toggle('active',ck==='best');document.getElementById('last').classList.toggle('active',ck==='last');
const rows=D.tables[ck];document.getElementById('table').innerHTML='<table><tr><th>模型</th>'+titles.map(t=>`<th>${t}</th>`).join('')+'</tr>'+rows.map(r=>'<tr><td>'+labels[r.mode]+'</td>'+fs.map(f=>`<td>${fmt(r.metrics[f].mean,f)} ± ${fmt(r.metrics[f].std,f)}</td>`).join('')+'</tr>').join('')+'</table>';
let max=Math.max(...rows.map(r=>r.metrics.pve_absolute_mm.mean));document.getElementById('chart').innerHTML='<svg width="900" height="250">'+rows.map((r,i)=>{let y=20+i*38,w=620*r.metrics.pve_absolute_mm.mean/max;return `<text x="0" y="${y+16}" class="barlabel">${labels[r.mode]}</text><rect x="180" y="${y}" width="${w}" height="23" fill="${r.mode==='full'?'#288478':'#447bb5'}"/><text x="${190+w}" y="${y+16}" class="barlabel">${r.metrics.pve_absolute_mm.mean.toFixed(1)} mm</text>`}).join('')+'</svg>';
const off=rows.find(r=>r.mode==='official'),tx=rows.find(r=>r.mode==='official_txyz'),full=rows.find(r=>r.mode==='full');const diff=full.metrics.surface_median_mm.mean-tx.metrics.surface_median_mm.mean;
document.getElementById('analysis').innerHTML=`<b>读数：</b>${ck.toUpperCase()} 的 R5 Full 表面 median 为 ${full.metrics.surface_median_mm.mean.toFixed(2)} mm，Official+Txyz 为 ${tx.metrics.surface_median_mm.mean.toFixed(2)} mm，差 ${diff.toFixed(2)} mm（负数表示 R5 更低）。去质心 PVE 与 Official 相同，说明 R5 的变化来自位置，不是把人体形状改好。是否稳定，还要一起看下面三个 seed、每个人和 P95。`;
let subjects='';for(const r of rows)for(const s of [11,23,37]){let v=D.result.cells[cell(r.mode,s,ck)];for(const [id,m] of Object.entries(v.per_subject))subjects+=`<tr><td>${labels[r.mode]}</td><td>${s}</td><td>${id}</td><td>${m.pve_absolute_mm.toFixed(2)}</td><td>${m.pve_centroid_centered_mm.toFixed(2)}</td><td>${m.surface_median_mm.toFixed(2)}</td><td>${m.surface_p95_mm.toFixed(2)}</td></tr>`;}
document.getElementById('subjects').innerHTML='<table><tr><th>模型</th><th>seed</th><th>人物</th><th>PVE（序列等权）</th><th>去质心</th><th>表面 median</th><th>表面 P95</th></tr>'+subjects+'</table>';
document.getElementById('translation').innerHTML='<p>'+Object.entries(D.translations).map(([s,v])=>`Official seed ${s}：${v.fallback}/${v.total} 帧回退；raw 平移范数中位 ${v.raw_norm_median_mm.toFixed(1)} mm，实际应用 ${v.applied_norm_median_mm.toFixed(1)} mm`).join('<br>')+'</p>';
document.getElementById('failures').innerHTML=D.paired[ck].map(r=>`<details><summary>${labels[r.mode]} · seed ${r.seed}：${r.p95_worse_than_official_txyz}/${r.frames} 帧 P95 高于 Official+Txyz</summary><table><tr><th>帧</th><th>人物</th><th>P95 差 mm</th><th>表面 median</th><th>PVE</th></tr>${r.worst.map(x=>`<tr><td>${x.sequence}/${x.frame}</td><td>${x.subject}</td><td class="${x.delta_p95_mm>0?'bad':'good'}">${x.delta_p95_mm.toFixed(2)}</td><td>${x.surface.median_mm.toFixed(2)}</td><td>${x.pve.pve_absolute_mm.toFixed(2)}</td></tr>`).join('')}</table></details>`).join('');}
render('best');</script></html>'''
    report = root/'reports/BEHAVE_R5_最终对照.html'
    report.write_text(html.replace('__DATA__', json.dumps(payload, ensure_ascii=False)), encoding='utf-8')
    (root/'reports/READABLE_ANALYSIS.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    visual = root/'visualizations'
    visual.mkdir(exist_ok=True)
    v = json.loads((visual/'VISUALIZATION_MANIFEST.json').read_text()) if (visual/'VISUALIZATION_MANIFEST.json').exists() else {'records': []}
    index = '<!doctype html><meta charset="utf-8"><title>全部缓存 Mesh 可视化</title><h1>全部帧，不挑好看的</h1><p>seed / Best-Last 独立展示。蓝色为预测，热图为独立传感器表面距离。</p><ul>'
    index += ''.join(f'<li><a href="{r["file"]}">{r["subject"]} · {r["sequence"]}/{r["frame"]} · s{r["seed"]} · {r["checkpoint"]}</a></li>' for r in v['records'])
    (visual/'index.html').write_text(index+'</ul>', encoding='utf-8')
    print('HTML_READY', report, flush=True)


if __name__ == '__main__':
    main()
