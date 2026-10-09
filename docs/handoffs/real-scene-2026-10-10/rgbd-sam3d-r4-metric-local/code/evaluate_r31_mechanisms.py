"""Predefined candidate mechanisms on the SAME frozen real Camera B pointsets."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json
from pathlib import Path
import torch
from fusion_r31 import R31Adapter
import evaluate_r3_humman as real
from r3_common import sha


def main():
    torch.set_num_threads(2)
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--pilot',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    conditions=[('geometry_attention','no_3d_attention_bias'),('geometry_attention','no_global_metric_context'),
        ('mhr_refinement','no_local_correspondence'),('mhr_refinement','translation_only')]
    report=dict(records=[],test_used=False,interpretation='inference interventions on fixed checkpoints; no B fitting, retraining or checkpoint selection',
        inference_code_sha256=sha(Path(__file__).parent/'fusion_r31.py'))
    for mode,condition in conditions:
        def configured(official,mode):
            model=R31Adapter(official,mode)
            if condition=='no_3d_attention_bias':model.fusion.disable_geometry_bias=True
            elif condition=='no_global_metric_context':model.fusion.disable_metric_context=True
            elif condition=='no_local_correspondence':model.fusion.disable_correspondence=True
            elif condition=='translation_only':model.fusion.translation_only=True
            return model
        real.RGBDBodyAdapter=configured;out=a.out/(mode+'_'+condition)
        checkpoint=a.pilot/mode/'run/best.pt'
        real.evaluate(a.root,a.root/'datasets/cache/humman_development_v1',a.root/'datasets/heldout/humman_r3_k1_v1',out,checkpoint)
        z=json.loads((out/'HUMMAN_RESULTS.json').read_text())
        report['records'].append(dict(mode=mode,condition=condition,checkpoint_sha256=sha(checkpoint),
            results={r:d['identity_equal_mean'] for r,d in z['results'].items()}))
        (a.out/'REAL_MECHANISM_ABLATIONS.json').write_text(json.dumps(report,indent=2))
        print('REAL_MECHANISM_COMPLETE',mode,condition,flush=True)
    (a.out/'ALL_MECHANISMS_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',conditions=conditions,test_used=False)))


if __name__=='__main__':main()
