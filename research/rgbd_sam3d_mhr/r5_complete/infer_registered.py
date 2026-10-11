"""Raw registered RGB-D inference for all seven models; no caches or Txyz needed.

Input: RGB uint8, registered axial depth_m, K, XYXY bbox, person mask.
Depth and RGB must already share their physical pixel geometry.
"""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,copy,json,time
from pathlib import Path
import numpy as np
import torch
from engine import Engine
from evaluate import BODY_KEYS
from fusion import RGBDBodyAdapter
from fusion_r4 import R4Adapter
from geometry import crop_registered_depth
from r3_common import load_official,sha


def run(a):
    torch.set_num_threads(2);paths=json.loads(a.paths.read_text())
    state=torch.load(a.checkpoint,map_location='cpu',weights_only=False)
    mode=state['identity']['mode'];official,estimator=load_official(Path(paths['official_root']))
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to
    raw=np.load(a.input);rgb,depth,K,bbox,mask=[raw[k] for k in ['rgb','depth_m','K','bbox','mask']]
    start=time.monotonic()
    b=prepare_batch(rgb,estimator.transform,bbox[None],masks=mask.astype(np.uint8)[None],cam_int=torch.from_numpy(K[None]).float())
    b={k:v for k,v in b.items() if torch.is_tensor(v)}
    d,valid,rays=crop_registered_depth(torch.from_numpy((depth*mask)[None,None]),b)
    bg=recursive_to(copy.deepcopy(b),'cuda');captured=[];body_exact=None
    with torch.no_grad():
        if mode in ['rgb_only','residual','cross_attention','g1']:
            adapter=R4Adapter(official,'g1') if mode=='g1' else RGBDBodyAdapter(official,mode)
            adapter.fusion.load_state_dict(state['model']);adapter.cuda().eval()
            output=adapter(bg,d.cuda(),valid.cuda(),rays.cuda());trace={}
            adapter.remove_hooks() if mode=='g1' else adapter._hook.remove()
        else:
            hook=official.backbone.register_forward_hook(lambda m,i,o:captured.append(o[-1] if isinstance(o,tuple) else o))
            official._initialize_batch(bg);reference=official.forward_step(bg,decoder_type='body')['mhr'];hook.remove()
            engine=Engine(mode,paths);engine.load_checkpoint_state(state['model']);engine.eval()
            x=dict(batch=recursive_to(b,'cuda'),feature=captured[-1],depth=d.cuda(),valid=valid.cuda(),rays=rays.cuda(),official=reference)
            output,trace=engine(x)
            body_exact=all(torch.equal(output[k],reference[k]) for k in BODY_KEYS);assert body_exact
    torch.cuda.synchronize();seconds=time.monotonic()-start
    body=output['pred_vertices'][0].float().cpu().numpy();camera=output['pred_cam_t'][0].float().cpu().numpy()
    arrays={k:output[k].detach().cpu().numpy() for k in BODY_KEYS+['pred_cam_t']}
    arrays.update(vertices_camera_A=body+camera,K=K,faces=official.head_pose.faces.detach().cpu().numpy())
    a.out.mkdir(parents=True,exist_ok=True);np.savez_compressed(a.out/'prediction.npz',**arrays)
    result=dict(status='RAW_RGBD_INFERENCE_COMPLETE',mode=mode,input_sha256=sha(a.input),checkpoint_sha256=sha(a.checkpoint),
        cached_features_used=False,Txyz=False,SAM_forward_count=1,Body_exact_equal_to_same_forward_Official=body_exact,
        timing_scope='first inference after Official load; includes adapter/head initialization, excludes model load and optional separate cache QA; not steady-state speed',
        optional_QA_cached_decoder_forward_count=int(bool(a.compare_cache) and mode in ['rgb_only','residual','cross_attention','g1']),
        seconds_including_prepare_backbone_body_camera=seconds,camera_xyz_m=camera.tolist())
    if a.compare_cache:
        from data import batch
        cached=batch([dict(path=str(a.compare_cache))]);reference_engine=Engine(mode,paths)
        reference_engine.load_checkpoint_state(state['model']);reference_engine.eval()
        with torch.no_grad():cached_output,_=reference_engine(cached)
        differences={k:float((output[k].float()-cached_output[k].float()).abs().max()) for k in ['pred_vertices','pred_cam_t','body_pose','shape','scale']}
        assert max(differences.values())<2e-5,('RAW_CACHE_PIPELINE_DIFFERENCE',differences)
        result['raw_vs_cache_max_abs']=differences;reference_engine.close()
    (a.out/'RESULTS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['paths','checkpoint','input','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--compare-cache',type=Path);run(p.parse_args())
