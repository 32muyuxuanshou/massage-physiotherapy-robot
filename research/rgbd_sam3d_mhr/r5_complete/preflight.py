"""Main-path GPU check for the seven actual architectures, plus plane QA."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,gc,json,time
from pathlib import Path
import numpy as np
import torch
from data import rows,batch
from engine import Engine,loss,native_values
from model import directional_filter,sampled_geometry
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'r5_camera_only'))
from scan_render import renderer_qa


def main(a):
    torch.set_num_threads(2);paths=json.loads(a.paths.read_text());cfg=json.loads(a.config.read_text())
    records=[r for r in rows(paths['native_cache'],'native') if r['role']=='TRAIN'][:2]
    x=batch(records);report={}
    report['perspective_renderer_QA']=renderer_qa()
    normals=torch.tensor([[[0.,0.,1.]]*32],device='cuda');v=torch.ones(1,32,dtype=torch.bool,device='cuda')
    correction,eigen=directional_filter(torch.tensor([[1.,2.,3.]],device='cuda'),normals,v)
    assert correction[0,:2].abs().max()==0 and correction[0,2]>2.9
    report['plane_directional_QA']=dict(status='PASS',correction=correction.tolist(),eigenvalues=eigen.tolist())
    curved=torch.eye(3,device='cuda')[None].repeat(1,12,1)
    cv=torch.ones(1,36,dtype=torch.bool,device='cuda')
    filtered,ce=directional_filter(torch.tensor([[1.,2.,3.]],device='cuda'),curved,cv)
    assert (filtered/torch.tensor([[1.,2.,3.]],device='cuda')>.96).all()
    report['curved_directional_QA']=dict(status='PASS',raw=[1.,2.,3.],filtered=filtered.tolist(),eigenvalues=ce.tolist())
    p,m=sampled_geometry(x['depth'],x['valid'],x['rays'])
    assert p.shape==(2,2048,8) and m.any(1).all()
    for mode in cfg['methods']:
        torch.manual_seed(11);torch.cuda.reset_peak_memory_stats();start=time.monotonic()
        engine=Engine(mode,paths);engine.eval()
        with torch.no_grad():
            o,tr=engine(x);reference=engine.official_reference(x)
        names=['pred_vertices','pred_cam_t','global_rot','body_pose','shape','scale']
        diffs={k:float((o[k].float()-reference[k].float()).abs().max()) for k in names}
        roundoff={k:float((reference[k].float()-x['official'][k].float()).abs().max()) for k in names}
        assert max(diffs.values())<2e-6,('ZERO_INITIALIZATION_MISMATCH',mode,diffs)
        engine.train();optimizer=torch.optim.AdamW(engine.trainable(),lr=3e-4)
        for step in range(2):
            optimizer.zero_grad(set_to_none=True);o,tr=engine(x)
            objective,components=loss(engine,o,tr,x,cfg,{})
            assert torch.isfinite(objective);objective.backward()
            norm=float(torch.nn.utils.clip_grad_norm_(engine.trainable(),1))
            assert norm>0 and np.isfinite(norm)
            if mode=='full':
                fine_gradient=float(engine.model.fine_head[-1].weight.grad.norm())
                assert fine_gradient>0 and np.isfinite(fine_gradient),'FINE_HEAD_NO_GEOMETRY_GRADIENT'
            optimizer.step()
        with torch.no_grad():o,tr=engine(x)
        fixed_body=mode in ['pooled_mlp','coarse','full']
        if fixed_body:
            assert all(torch.equal(o[k],x['official'][k]) for k in ['pred_vertices','body_pose','shape','scale','global_rot','hand'])
            absent=dict(x,depth=torch.zeros_like(x['depth']),valid=torch.zeros_like(x['valid']))
            missing,_=engine(absent);assert torch.equal(missing['pred_cam_t'],x['official']['pred_cam_t'].float())
        report[mode]=dict(status='PASS',zero_init_max_abs=diffs,same_batch_Official_vs_historical_cache=roundoff,gradient_norm=norm,
            body_exact_equal=fixed_body,camera_moved_m=float((o['pred_cam_t']-x['official']['pred_cam_t']).norm(dim=1).mean()),
            visible_queries=tr.get('visible_queries',torch.zeros(2)).tolist(),
            trainable_parameters=sum(p.numel() for p in engine.trainable()),
            peak_memory_bytes=torch.cuda.max_memory_allocated(),seconds=time.monotonic()-start)
        if mode=='full':
            report[mode]['fine_head_gradient_norm']=fine_gradient
            report[mode]['raw_vs_directional_fine_m']={k:tr[k].tolist() for k in ['fine_raw_delta','fine_delta']}
        print('PREFLIGHT_MODE',mode,json.dumps(report[mode]),flush=True)
        engine.close();del engine,optimizer,o,tr;gc.collect();torch.cuda.empty_cache()
    report.update(status='PASS',test_read=False,camera_B_read=False)
    a.out.write_text(json.dumps(report,indent=2));print('PREFLIGHT_ALL_PASS',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['paths','config','out']:p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
