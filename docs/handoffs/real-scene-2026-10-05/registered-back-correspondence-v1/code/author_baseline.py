"""Official frozen DiffusionNet functional map, with explicitly stronger full context."""
import argparse,sys,time,hashlib,json
from pathlib import Path
import numpy as np
import scipy
import torch
from scipy.spatial import cKDTree
ROOT=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
AUTHOR=ROOT/'author_diffusion_net'
sys.path.insert(0,str(ROOT/'author_deps'))
sys.path.insert(0,str(AUTHOR/'src'))
sys.path.insert(0,str(AUTHOR/'experiments/functional_correspondence'))
import diffusion_net
from fmaps_model import FunctionalMapCorrespondenceWithDiffusionNetFeatures
from inspect_data import load_off


def write(p,obj):p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    start=time.monotonic();torch.set_num_threads(4);checkpoint=AUTHOR/'experiments/functional_correspondence/pretrained_models/faust_hks.pth'
    model=FunctionalMapCorrespondenceWithDiffusionNetFeatures(input_features='hks').cuda();model.load_state_dict(torch.load(checkpoint,weights_only=True));model.eval()
    cache=ROOT/'author_operator_cache';cache.mkdir(exist_ok=True)
    output=ROOT/'author_predictions';output.mkdir(exist_ok=True)
    source={r['name']:r for r in read(ROOT/'DATA_INVENTORY.json')['meshes'] if r['dataset']=='faust'}
    def shape(name):
        row=source[name];v,f=load_off(Path(row['mesh_path']));v=torch.tensor(v,dtype=torch.float32);f=torch.tensor(f,dtype=torch.int64)
        v=diffusion_net.geometry.normalize_positions(v,faces=f,scale_method='area')
        frames,mass,L,evals,evecs,gx,gy=diffusion_net.geometry.get_operators(v,f,k_eig=128,op_cache_dir=str(cache))
        hks=diffusion_net.geometry.compute_hks_autoscale(evals,evecs,16)
        # Author forward never reads vts; append an empty placeholder, not GT correspondences.
        return [x.cuda() for x in [v,f,frames,mass,L,evals,evecs,gx,gy,hks,torch.empty(0,dtype=torch.int64)]]
    template=shape('tr_reg_000');rows=[]
    with np.load(ROOT/'TEMPLATE.npz') as z:canonical=z['canonical_xyz'];query=z['query_local_ids']
    cases=[r for r in read(ROOT/'CASE_MANIFEST.json') if r['role']=='test']
    for name in sorted({r['name'] for r in cases}):
        other=shape(name)
        with torch.no_grad():C,_,_=model(template,other)
        spectral_template=(template[6][:,:30]@C[0].T).cpu().numpy()
        mapped=cKDTree(spectral_template).query(other[6][:,:30].cpu().numpy())[1]
        predicted=template[0].cpu().numpy()[mapped]
        np.savez_compressed(output/(name+'.npz'),predicted_template_xyz=predicted,predicted_template_vertex_idx=mapped)
        for r in [r for r in cases if r['name']==name]:
            with np.load(r['path']) as z:q=predicted[z['source_vertex_idx']];gt=z['canonical_gt'];ids=z['local_reference_idx'];surface=z['true_surface_xyz']
            error=np.linalg.norm(q-gt,axis=1)*100;visible=np.isin(query,ids);iq=query[visible]
            true_idx=np.array([np.flatnonzero(ids==j)[0] for j in iq]);chosen=cKDTree(q).query(canonical[iq])[1]
            qe=np.linalg.norm(canonical[ids[chosen]]-canonical[iq],axis=1)*100
            se=np.linalg.norm(surface[chosen]-surface[true_idx],axis=1)*100
            rows.append(dict(name=name,condition=r['condition'],input_seed=r['seed'],mode='AUTHOR_DIFFUSIONNET_HKS_FULL_CONTEXT',
                canonical_median_percent=float(np.median(error)),canonical_p95_percent=float(np.quantile(error,.95)),
                visible_query_median_percent=float(np.median(qe)),visible_query_p95_percent=float(np.quantile(qe,.95)),
                visible_surface_query_median_percent=float(np.median(se)),query_visible_fraction=float(visible.mean()),
                source_prediction_path=str(output/(name+'.npz')),source_prediction_sha256=sha(output/(name+'.npz'))))
        print('AUTHOR_SOURCE',name,round(time.monotonic()-start,2),flush=True)
    metrics=[k for k in rows[0] if k.endswith('_percent') or k=='query_visible_fraction'];per_source=[];aggregate=[]
    for name in sorted({r['name'] for r in rows}):
        for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
            group=[r for r in rows if (r['name'],r['condition'])==(name,condition)]
            per_source.append(dict(name=name,condition=condition,**{k:float(np.mean([r[k] for r in group])) for k in metrics}))
    for condition in ['FULL','PARTIAL_BAND','NOISY_PARTIAL']:
        group=[r for r in per_source if r['condition']==condition];aggregate.append(dict(condition=condition,sources=len(group),**{k:float(np.median([r[k] for r in group])) for k in metrics}))
    write(ROOT/'AUTHOR_BASELINE_RESULTS.json',dict(status='COMPLETE',checkpoint_path=str(checkpoint),checkpoint_sha256=sha(checkpoint),
        author_commit='b1019b049597711d10259ce28250f7dfc4335a2b',method='Original author functional-map and extraction; no GT input to model',
        same_input_as_primary=False,complete_unperturbed_geometry=True,author_training_sources=80,our_training_sources=60,
        metric_unit='percent template sqrt-area; NOT mm/geodesic',seconds=time.monotonic()-start,aggregate=aggregate,per_source=per_source,raw_evaluation=rows))
    print('AUTHOR_COMPLETE',len(rows),round(time.monotonic()-start,2),flush=True)


if __name__=='__main__':main()
