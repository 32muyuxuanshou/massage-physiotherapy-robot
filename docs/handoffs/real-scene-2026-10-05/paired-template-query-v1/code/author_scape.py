"""Official DiffusionNet full-geometry reference on the independent SCAPE template space."""
import sys,time
from pathlib import Path
import numpy as np
import torch
from scipy.spatial import cKDTree
sys.path.insert(0,'/raid5/xuhd/datasets/registered_human_correspondence_20261005/code')
from author_baseline import AUTHOR,diffusion_net,FunctionalMapCorrespondenceWithDiffusionNetFeatures
from experiment import ROOT,read,write,sha
from inspect_data import load_off
from paired_experiment import OUT,SCAPE_ROT


def main():
    torch.set_num_threads(4);start=time.monotonic();checkpoint=AUTHOR/'experiments/functional_correspondence/pretrained_models/faust_hks.pth'
    m=FunctionalMapCorrespondenceWithDiffusionNetFeatures(input_features='hks').cuda();m.load_state_dict(torch.load(checkpoint,weights_only=True));m.eval()
    cache=ROOT/'author_operator_cache';source={r['name']:r for r in read(ROOT/'DATA_INVENTORY.json')['meshes'] if r['dataset']=='scape'}
    predroot=OUT/'author_scape_predictions';predroot.mkdir(exist_ok=True)
    def shape(name):
        r=source[name];assert sha(Path(r['mesh_path']))==r['mesh_sha256'];v,f=load_off(Path(r['mesh_path']));v=v@SCAPE_ROT.T
        v=torch.tensor(v,dtype=torch.float32);f=torch.tensor(f,dtype=torch.int64);v=diffusion_net.geometry.normalize_positions(v,faces=f,scale_method='area')
        frames,mass,L,ev,evec,gx,gy=diffusion_net.geometry.get_operators(v,f,k_eig=128,op_cache_dir=str(cache));hks=diffusion_net.geometry.compute_hks_autoscale(ev,evec,16)
        return [x.cuda() for x in [v,f,frames,mass,L,ev,evec,gx,gy,hks,torch.empty(0,dtype=torch.int64)]]
    template=shape('mesh000');t=dict(np.load(OUT/'scape_template.npz'));query=t['query_local_ids'];canonical=t['canonical_xyz']
    cases=[r for r in read(OUT/'CASE_MANIFEST.json') if r['dataset']=='scape'];rows=[]
    for name in sorted({r['name'] for r in cases}):
        other=shape(name)
        with torch.no_grad():C,_,_=m(template,other)
        mapped=cKDTree((template[6][:,:30]@C[0].T).cpu().numpy()).query(other[6][:,:30].cpu().numpy())[1];qall=template[0].cpu().numpy()[mapped]
        np.savez_compressed(predroot/(name+'.npz'),predicted_template_xyz=qall,template_vertex_idx=mapped)
        for r in [r for r in cases if r['name']==name]:
            with np.load(r['path']) as z:q=qall[z['source_vertex_idx']];ids=z['local_reference_idx'];surface=z['true_surface_xyz']
            visible=query[np.isin(query,ids)];chosen=cKDTree(q).query(canonical[visible])[1]
            qe=np.linalg.norm(canonical[ids[chosen]]-canonical[visible],axis=1)*100;true=np.array([np.flatnonzero(ids==j)[0] for j in visible]);se=np.linalg.norm(surface[chosen]-surface[true],axis=1)*100
            rows.append(dict(dataset='scape',name=name,condition=r['condition'],input_seed=r['seed'],mode='DIFFUSIONNET_FULL_CONTEXT',
                visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),visible_surface_query_median_percent=float(np.median(se)),
                query_visible_fraction=len(visible)/len(query),prediction_path=str(predroot/(name+'.npz')),prediction_sha256=sha(predroot/(name+'.npz'))))
        print('AUTHOR_SCAPE_SOURCE',name,round(time.monotonic()-start,2),flush=True)
    aggregate=[];per_source=[];metrics=['visible_query_median_percent','visible_query_p95_percent','visible_surface_query_median_percent','query_visible_fraction']
    for name in sorted({r['name'] for r in rows}):
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            g=[r for r in rows if (r['name'],r['condition'])==(name,condition)];per_source.append(dict(name=name,condition=condition,**{k:float(np.mean([r[k] for r in g])) for k in metrics}))
    for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
        g=[r for r in per_source if r['condition']==condition];aggregate.append(dict(condition=condition,sources=len(g),**{k:float(np.median([r[k] for r in g])) for k in metrics}))
    write(OUT/'AUTHOR_SCAPE_RESULTS.json',dict(status='COMPLETE',checkpoint_sha256=sha(checkpoint),author_commit='b1019b049597711d10259ce28250f7dfc4335a2b',
        same_input=False,full_geometry=True,author_training='80 FAUST meshes; no SCAPE retraining',metric_unit='percent respective sqrt-area, NOT mm',
        aggregate=aggregate,per_source=per_source,raw_evaluation=rows,seconds=time.monotonic()-start))
    print('AUTHOR_SCAPE_COMPLETE',round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':main()
