import argparse,json,time
import numpy as np
import torch
from core import WORK,G,FineOnly,load_parent,evaluate
from train218 import selected_rows
from frozen_render_losses import MeshRenderer


def main(seed):
    torch.set_num_threads(2);start=time.monotonic();faces=torch.from_numpy(np.load(G/'assets/faces.npy')).cuda()
    renderer=MeshRenderer(faces);model=FineOnly(load_parent(seed,renderer));rows=selected_rows(seed)
    result={d:evaluate(model,renderer,[r for r in rows if r['domain']==d and r['role']=='VAL'],seed) for d in ['native','scan']}
    result['seconds']=time.monotonic()-start
    (WORK/('BASELINE_s%d.json'%seed)).write_text(json.dumps(result,indent=2))
    print('BASELINE_COMPLETE',seed,result['seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);main(p.parse_args().seed)
