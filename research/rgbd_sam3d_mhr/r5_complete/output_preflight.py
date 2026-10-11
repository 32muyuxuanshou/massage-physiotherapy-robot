"""Actual-cache output QA and preview, independent of formal model ranking."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json,sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image,ImageDraw
from data import rows,batch,read,augment_depth
from engine import Engine
from evaluate import BODY_KEYS
from fusion import SpatialDepthFusion
from fusion_r4 import R4Fusion
from visualize import overlay,panel
import nvdiffrast.torch as dr


def main(a):
    torch.set_num_threads(2);r=a.root;paths=json.loads((r/'PATHS.json').read_text())
    records=[v for v in rows(paths['native_cache'],'native') if v['role']=='VAL'][:2]
    x=batch(records);report={}
    # G0 wraps the same SpatialDepthFusion. Check non-zero output weights too.
    torch.manual_seed(7)
    cross=SpatialDepthFusion(x['feature'].shape[1],mode='cross_attention').cuda().eval()
    g0=R4Fusion(x['feature'].shape[1],'g0').cuda().eval()
    with torch.no_grad():
        torch.nn.init.normal_(cross.output_projection.weight,std=.001)
        cross.gate.fill_(.2)
        g0.spatial.load_state_dict(cross.state_dict())
        aa=cross(x['feature'].float(),x['depth'].float(),x['valid'],x['rays'].float())
        bb=g0(x['feature'].float(),x['depth'].float(),x['valid'],x['rays'].float())
    assert torch.equal(aa,bb)
    report['G0_cross_attention_equivalence']=dict(status='PASS',max_abs=float((aa-bb).abs().max()),nonzero_output_weights=True)
    del cross,g0,aa,bb
    rgb_only=SpatialDepthFusion(x['feature'].shape[1],mode='rgb_only').cuda().eval()
    with torch.no_grad():
        rgb_only.gate.fill_(.2)
        args=(x['feature'].float(),x['depth'].float(),x['valid'],x['rays'].float())
        aa=rgb_only(*args)
        bb=rgb_only(args[0],torch.zeros_like(args[1]),torch.zeros_like(args[2]),torch.randn_like(args[3]))
    assert torch.equal(aa,bb)
    report['RGB_only_fusion_Depth_independence']=dict(status='PASS',max_abs=0.,nonzero_gate=True)
    del rgb_only,aa,bb
    raw=read(records[0]['path']);d,v=augment_depth(raw,11,1)
    assert torch.equal(raw['rays'],x['rays'][0:1].cpu()) and torch.equal(raw['batch']['cam_int'],x['batch']['cam_int'][0:1].cpu())
    assert int(v.sum())<=int(raw['valid'].sum()) and torch.all(d[~v]==0)
    report['sampling_geometry']=dict(status='PASS',valid_original=int(raw['valid'].sum()),valid_augmented=int(v.sum()),K_rays_unchanged=True)
    engine=Engine('full',paths);state=torch.load(r/'screen/full_s7_lr3e-04/best.pt',map_location='cpu',weights_only=False)
    engine.load_checkpoint_state(state['model']);engine.eval();ctx=dr.RasterizeCudaContext()
    faces=engine.renderer.faces.cpu().numpy();canvas=Image.new('RGB',(1280,430),'white');draw=ImageDraw.Draw(canvas)
    row=records[0];z=np.load(Path(paths['official_root'])/'datasets/synthetic/native_scale_v2'/row['file']);rgb=z['rgb'];K=z['K']
    with torch.no_grad():o,tr=engine(x)
    assert all(torch.equal(o[k],x['official'][k]) for k in BODY_KEYS)
    specimens=[('RGB',rgb),('Native GT',overlay(rgb,(x['truth']['pred_vertices']+x['truth']['pred_cam_t'][:,None])[0].cpu().numpy(),faces,K,ctx)),
        ('Official',overlay(rgb,(x['official']['pred_vertices']+x['official']['pred_cam_t'][:,None])[0].cpu().numpy(),faces,K,ctx)),
        ('R5 screen seed7 epoch5: QA only',overlay(rgb,(o['pred_vertices']+o['pred_cam_t'][:,None])[0].cpu().numpy(),faces,K,ctx))]
    for i,(name,image) in enumerate(specimens):
        draw.text((i*320+5,12),name,fill='black');canvas.paste(panel(image,(0,0,rgb.shape[1],rgb.shape[0])),(i*320,48))
    out=r/'code_qa';out.mkdir(exist_ok=True);canvas.save(out/'QA_PERSPECTIVE_PREVIEW.jpg',quality=94)
    report['actual_cached_mesh_preview']=dict(status='PASS',sample=row['cache_file'],Body_exact=True,scientific_ranking=False)
    report.update(status='PASS',TEST_read=False)
    (out/'OUTPUT_PREFLIGHT.json').write_text(json.dumps(report,indent=2));engine.close();print('OUTPUT_PREFLIGHT_PASS',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
