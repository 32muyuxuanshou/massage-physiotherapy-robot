"""Add readable audit notes without editing frozen numerical results or renderer."""
import argparse,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    notes='''<div class="card warn"><h2>审计发现：先看分数能证明什么</h2>
<p><b>完整 270 帧已评价。R5 Full Last PVE 61.06 mm，Official+Txyz 56.24 mm。</b>R5 保留 Official 身体，改善位置；获益集中在 Sub04/Sub05，Sub03 仍有负收益。新模型没有加 Txyz。</p>
<p><b>Best 是 native 合成 VAL 选择的第 13/12/13 轮；Last 是第 50 轮。</b>两组完整报告，没有依据 BEHAVE 追选模型。差异与更多训练及混合阶段同时发生，尚不能单独归因。</p>
<p><b>原冻结 person-mask 支撑点含物体/遮挡与异常深度。</b>首个背包帧 K1 有 730/2048 点落在 rendered object mask 内；拟合人体参考对同点集的 P95 为 282.27 mm。Sub05 tablesmall/t0068 的 K3 有 160/2048 点离拟合人体超过500mm，参考 P95 为2828.65mm；原深度可到5.1m，拟合人体在1.7–2.2m。当前全部原分数和点保留，没有事后过滤。观测 P95 不能直接等同人体重建错误或裸背精度。</p>
<p><a href="../visualizations/vertex_viewer.html">全部1,620组三维对应顶点视图</a>　<a href="WORST_REFERENCE_SUPPORT_AUDIT.json">异常深度原像素与参考核查</a>　<a href="CHECKPOINT_EPOCHS.json">实际 checkpoint 轮次</a></p></div>'''
    source=root/'reports/BEHAVE_R5_最终对照.html';target=root/'reports/BEHAVE_R5_最终对照_审计版.html'
    text=source.read_text(encoding='utf-8').replace('<div class="card"><h2>这些数字是什么</h2>',notes+'<div class="card"><h2>这些数字是什么</h2>')
    text=text.replace('独立表面 median mm','观测支撑 median mm').replace('独立表面 P95 mm','观测支撑 P95 mm').replace('独立表面距离','独立相机观测支撑距离')
    target.write_text(text,encoding='utf-8')
    print('AUDITED_HTML_READY',target,flush=True)


if __name__=='__main__':main()
