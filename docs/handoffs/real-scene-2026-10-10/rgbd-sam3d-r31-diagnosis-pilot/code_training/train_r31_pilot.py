"""Matched small-data pilot, sharing unmodified R3 training and real evaluator."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json
from pathlib import Path
import torch
from fusion_r31 import R31Adapter
import train_r3_multiseed as old
import evaluate_r3_humman as real
from r3_common import load_official,read_cache,combine,cached_forward,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--mode',required=True);p.add_argument('--source-commit',required=True)
    p.add_argument('--qa-only',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    config=json.loads(a.config.read_text());pilot=config['pilot'];cfg=json.loads((Path(__file__).parent/'R3_SCALE_CONFIG_V1.json').read_text())
    cfg.update(batch_size=pilot['batch_size'])
    cache=a.root/'datasets/cache/native_scale_v2';rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
    ids=sorted({r['identity'] for r in rows if r['role']=='TRAIN'})[:pilot['train_identity_count']]
    subset=[r for r in rows if r['role']=='VAL' or (r['role']=='TRAIN' and r['identity'] in ids)]
    identity=dict(source_commit=a.source_commit,config_sha256=sha(a.config),config=config,
        training_identities=ids,cache_manifest_sha256=sha(cache/'CACHE_MANIFEST.json'),test_used=False,
        heldout_points_manifest_sha256=sha(a.root/'datasets/heldout/humman_r3_k1_v1/MANIFEST.json'),
        code_sha256={n:sha(Path(__file__).parent/n) for n in ['fusion_r31.py','train_r31_pilot.py','train_r3_multiseed.py','render_losses.py']})
    (a.out/'EXECUTION_IDENTITY.json').write_text(json.dumps(identity,indent=2))
    official,_=load_official(a.root)
    if a.qa_only:
        torch.manual_seed(pilot['seed']);adapter=R31Adapter(official,a.mode).cuda()
        rec=[read_cache(str(cache/subset[0]['cache_file']))];b,f,d,v,rays,*_=combine(rec)
        with torch.no_grad():o=cached_forward(adapter,b,f,d,v,rays)
        # Compare against a zero-gate Official adapter on the same cached tensors.
        adapter._hook.remove();ref=R31Adapter(official,'cross_attention').cuda()
        with torch.no_grad():r=cached_forward(ref,b,f,d,v,rays)
        ref._hook.remove();difference=float((o['pred_vertices']-r['pred_vertices']).abs().max())
        assert difference<2e-6,f'ZERO_INITIAL_NATIVE_MHR_MISMATCH {difference}'
        adapter=R31Adapter(official,a.mode).cuda()
        o=cached_forward(adapter,b,f,d,v,rays)
        loss=(o['pred_vertices'].square().mean()+o['pred_cam_t'].square().mean());loss.backward()
        grads=[p.grad for p in adapter.fusion.parameters() if p.requires_grad and p.grad is not None]
        assert grads and all(torch.isfinite(g).all() for g in grads)
        report=dict(status='PASS',zero_initial_vertex_max_abs_m=difference,finite_gradients=True,
            trainable_parameters=sum(p.numel() for p in adapter.fusion.parameters() if p.requires_grad),
            peak_memory_bytes=torch.cuda.max_memory_allocated(),mode=a.mode)
        (a.out/'STRUCTURAL_QA.json').write_text(json.dumps(report,indent=2));print(report,flush=True);return
    old.RGBDBodyAdapter=R31Adapter
    old.train_one(official,subset,cache,cfg,a.out/'run',a.mode,pilot['seed'],pilot['learning_rate'],pilot['epochs'],identity)
    del official;torch.cuda.empty_cache()
    real.RGBDBodyAdapter=R31Adapter
    real.evaluate(a.root,a.root/'datasets/cache/humman_development_v1',a.root/'datasets/heldout/humman_r3_k1_v1',
        a.out/'real',a.out/'run/best.pt')
    (a.out/'PILOT_COMPLETE.json').write_text(json.dumps(dict(status='COMPLETE',test_used=False)))


if __name__=='__main__':main()
