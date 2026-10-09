"""New G3 actual batch16 throughput for 1/2/3 independent GPU workers."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,json,subprocess,sys,time
from pathlib import Path
import numpy as np
import torch
from fusion_r4 import R4Adapter
from r3_common import load_official,read_cache,combine,cached_forward
from render_losses import MeshRenderer,loss_components


def worker(root,out):
    torch.set_num_threads(2);torch.manual_seed(11)
    cache=root/'datasets/cache/native_scale_v2';rows=json.loads((cache/'CACHE_MANIFEST.json').read_text())['records']
    rows=[r for r in rows if r['role']=='TRAIN'][:16]
    b,f,d,v,rays,gt,target,mask,K=combine([read_cache(str(cache/r['cache_file'])) for r in rows])
    official,_=load_official(root);model=R4Adapter(official,'g3').cuda();params=list(model.fusion.parameters())
    optimizer=torch.optim.AdamW(params,lr=3e-4);renderer=MeshRenderer(official.head_pose.faces)
    cfg=json.loads(Path(__file__).with_name('R3_SCALE_CONFIG_V1.json').read_text());times=[]
    for i in range(16):
        torch.cuda.synchronize();start=time.monotonic();optimizer.zero_grad(set_to_none=True)
        o=cached_forward(model,b,f,d,v,rays);comp=loss_components(o,gt,target,mask,K,renderer)
        loss=sum(cfg['loss_weights'][k]*x for k,x in comp.items());assert torch.isfinite(loss)
        loss.backward();torch.nn.utils.clip_grad_norm_(params,1);optimizer.step();torch.cuda.synchronize();times.append(time.monotonic()-start)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(dict(batch_size=16,steps=16,
        steady_seconds_per_batch=float(np.mean(times[4:])),peak_memory_bytes=torch.cuda.max_memory_allocated()),indent=2));model.remove_hooks()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--worker',action='store_true');a=p.parse_args()
    if a.worker:worker(a.root,a.out)
    else:
        a.out.mkdir(parents=True,exist_ok=True);results=[]
        for n in [1,2,3]:
            jobs=[]
            for i in range(n):
                path=a.out/f'c{n}_worker{i}.json';log=(a.out/f'c{n}_worker{i}.log').open('w')
                jobs.append(subprocess.Popen([sys.executable,'-u',__file__,'--root',str(a.root),'--out',str(path),'--worker'],stdout=log,stderr=subprocess.STDOUT))
            assert all(j.wait()==0 for j in jobs)
            rows=[json.loads((a.out/f'c{n}_worker{i}.json').read_text()) for i in range(n)]
            results.append(dict(concurrent=n,workers=rows,images_per_second=sum(16/x['steady_seconds_per_batch'] for x in rows),
                peak_memory_sum_bytes=sum(x['peak_memory_bytes'] for x in rows)))
            print('CONCURRENCY',json.dumps(results[-1]),flush=True)
        chosen=max(results,key=lambda x:x['images_per_second'])['concurrent']
        (a.out/'CONCURRENCY_QA.json').write_text(json.dumps(dict(status='PASS',results=results,selected_concurrent=chosen,
            rule='highest measured aggregate warmed batch16 images/s among 1/2/3 new G3 workers'),indent=2))
