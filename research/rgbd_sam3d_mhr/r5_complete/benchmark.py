"""Actual batch-size throughput; no checkpoint/real-B selection."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0');os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import argparse,gc,json,time
from pathlib import Path
import torch
from data import rows,batch
from engine import Engine,loss

def main(a):
    torch.set_num_threads(2);paths=json.loads(a.paths.read_text());cfg=json.loads(a.config.read_text())
    records=[r for r in rows(paths['native_cache'],'native') if r['role']=='TRAIN'][:16]
    report={}
    for mode in ['cross_attention','g1','full']:
        engine=Engine(mode,paths);engine.train();values=[]
        for size in [2,8,16]:
            x=batch(records[:size]);torch.cuda.reset_peak_memory_stats();times=[]
            for step in range(12):
                engine.zero_grad(set_to_none=True);torch.cuda.synchronize();start=time.monotonic()
                o,tr=engine(x);objective,_=loss(engine,o,tr,x,cfg,{})
                objective.backward();torch.cuda.synchronize()
                if step>=2:times.append(time.monotonic()-start)
            values.append(dict(batch=size,seconds=sum(times)/len(times),samples_per_second=size/(sum(times)/len(times)),peak_memory_bytes=torch.cuda.max_memory_allocated()))
            print('BENCHMARK',mode,json.dumps(values[-1]),flush=True)
        report[mode]=values;engine.close();del engine,x,o,tr,objective;gc.collect();torch.cuda.empty_cache()
    a.out.write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['paths','config','out']:p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
