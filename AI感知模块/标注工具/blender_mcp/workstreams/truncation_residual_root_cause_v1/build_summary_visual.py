from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont


SPLITS=("COMBINATION_HOLDOUT","SHAPE_HOLDOUT","POSE_HOLDOUT")
COLORS=("#2563EB","#059669","#D97706")


def f(size:int):
    for path in ("C:/Windows/Fonts/msyh.ttc","C:/Windows/Fonts/arial.ttf"):
        if Path(path).exists(): return ImageFont.truetype(path,size)
    return ImageFont.load_default()


def read(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8-sig"))


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--evidence",type=Path,required=True);args=parser.parse_args();root=args.evidence.resolve();(root/"visuals").mkdir(exist_ok=True)
    perfect=read(root/"gate_a2"/"perfect_heatmap_audit.json");hold=read(root/"decoder_evaluation"/"decoder_comparison.json");main=read(root/"main_test_decoder_evaluation"/"main_test_decoder_comparison.json")
    image=Image.new("RGB",(1600,1000),"#F8FAFC");d=ImageDraw.Draw(image);d.text((55,32),"截断残差根因：Heatmap 边界内缩偏差",fill="#0F172A",font=f(34));d.text((55,82),"完美标签自解码 + 冻结 V2 权重，不增数据、不重训",fill="#475569",font=f(20))
    d.rounded_rectangle((55,140,1545,300),radius=18,fill="#FFF7ED",outline="#EA580C",width=3);near=perfect["actual_nearest_edge_lt64"]
    d.text((85,165),"完美 Heatmap（距边缘 <64 px）",fill="#9A3412",font=f(25));d.text((85,210),f"431 个可见实例：平均纯向内偏差 {near['mean_inward_bias_px']:.2f} px，P95 {near['p95_expectation_error_px']:.2f} px",fill="#7C2D12",font=f(24));d.text((85,252),"结论：34–36 px 长尾可由标签截断 + 全局期望解码单独产生。",fill="#7C2D12",font=f(21))
    y=350;d.text((55,y),"旧 C2：2D P95（px）",fill="#0F172A",font=f(27));y+=55
    for split,color in zip(SPLITS,COLORS):
        old=main["splits"][split]["expectation"]["by_camera"]["C2_EDGE_CROP"]["p95"];new=main["splits"][split]["boundary_hybrid"]["by_camera"]["C2_EDGE_CROP"]["p95"]
        d.text((75,y),split.replace("_HOLDOUT",""),fill=color,font=f(21));d.rectangle((350,y+4,350+old*22,y+30),fill="#CBD5E1");d.rectangle((350,y+36,350+new*22,y+62),fill=color);d.text((1160,y+4),f"{old:.2f} → {new:.2f}",fill="#1E293B",font=f(20));y+=105
    x=900;y=350;d.text((x,y),"主测试 >30 mm 尾部",fill="#0F172A",font=f(27));y+=65
    for split,color in zip(SPLITS,COLORS):
        old=main["splits"][split]["expectation"]["tail_gt30mm_count"];new=main["splits"][split]["boundary_hybrid"]["tail_gt30mm_count"]
        d.rounded_rectangle((x,y,x+580,y+72),radius=12,fill="white",outline=color,width=3);d.text((x+18,y+14),split.replace("_HOLDOUT",""),fill=color,font=f(20));d.text((x+365,y+14),f"{old} → {new}",fill="#0F172A",font=f(25));y+=95
    d.rounded_rectangle((55,835,1545,950),radius=16,fill="#ECFDF5",outline="#059669",width=3);d.text((80,855),"边界混合解码：峰值在最外4个 Heatmap 单元时用 log-quadratic 外推，其余保持原全局期望。",fill="#065F46",font=f(22));d.text((80,900),"NORMAL_MAIN 精确不变；所有比较 3D invalid=0。候选仍需新 validation/untouched test 冻结后才能转为正式合同。",fill="#065F46",font=f(20))
    image.save(root/"visuals"/"root_cause_and_decoder_summary.png")


if __name__=="__main__":main()
