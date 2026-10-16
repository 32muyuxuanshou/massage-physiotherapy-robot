"""Selected A-only correspondences for audit; does not update any result."""
import json
import numpy as np
import torch
from common import W,G,load,tasks,key,dump
from projection import Projector


def main():
    torch.set_num_threads(1);p=Projector();rr=tasks()
    chosen=[next(t for t in rr if t['dataset']=='real' and t['seed']==11 and t['identity']==i) for i in ['p001195','p001196']]
    candidates=[t for t in rr if t['dataset']=='behave' and t['seed']==37]
    # A/Coarse geometry selection, independent of new B scores.
    def displacement(t):
        z=load(G/t['prediction']);return np.linalg.norm(z['coarse_camera'].reshape(3)-np.asarray(t['original_camera']))
    chosen.append(max(candidates,key=displacement));selection=[]
    out=W/'query_review';out.mkdir(exist_ok=True)
    for t in chosen:
        tag=key(t);a=load(W/'inputs'/(tag+'.npz'));z=load(W/'fits'/(tag+'.npz'));r=json.loads((W/'fits'/(tag+'.json')).read_text())
        rec={k:torch.from_numpy(a[k]) for k in ['depth','valid','rays']};rec['batch']={k:torch.from_numpy(a[v]) for k,v in [('cam_int','K'),('ori_img_size','size'),('affine_trans','affine')]}
        p.bind(rec,z['body_m'],z['coarse_camera_m']);arrays=dict(depth=a['depth'],valid=a['valid'])
        for stage,method in [('coarse','coarse'),('step1','proj_plane1'),('step3','proj_plane3')]:
            delta=np.asarray(r['methods'][method]['applied_delta_m']);s=p.sample(delta,256)
            for k,v in s.items():arrays[stage+'_'+k]=v
            arrays[stage+'_delta_m']=delta
            arrays[stage+'_raw_delta_m']=np.asarray(r['methods'][method]['raw_delta_m'])
            arrays[stage+'_fallback']=np.asarray(r['methods'][method]['fallback'])
        np.savez_compressed(out/(tag+'.npz'),**arrays);selection.append(dict(tag=tag,identity=t['identity'],dataset=t['dataset'],seed=t['seed']))
    dump(out/'SELECTION.json',dict(records=selection,selection='Two known identity first frames; BEHAVE seed37 maximum Coarse-vs-Official displacement, no new B-score selection',Camera_B_read=False))


if __name__=='__main__':main()
