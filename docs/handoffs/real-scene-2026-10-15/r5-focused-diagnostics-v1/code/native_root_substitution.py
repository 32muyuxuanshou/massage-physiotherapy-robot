"""Native-VAL root-parameter substitution using only the existing MHR CPU asset.

Not SAM3D inference or training. Body/shape/scale/hand/face remain Official's.
Only native global Euler indices 3:6 change to the sample's true root rotation.
"""
import hashlib
import json
from pathlib import Path
import resource
import tarfile
import time
import numpy as np
import torch

BASE=Path('/root/autodl-tmp/rgbd_sam3d')
OUT=BASE/'evaluations/r5_focused_diagnostics_v1'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def run():
    torch.set_num_threads(1)
    manifest=json.loads((OUT/'geometry/MANIFEST.json').read_text())
    tasks=[t for t in manifest['tasks'] if t['dataset']=='native' and t['seed']==11]
    assert len(tasks)==400 and all(t['role']=='VAL' for t in tasks)
    asset=BASE/'checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt'
    model=torch.jit.load(str(asset),map_location='cpu')
    directory=OUT/'native_root_substitution';directory.mkdir(exist_ok=True)
    records=[];start=time.monotonic()
    with torch.no_grad():
        for i,t in enumerate(tasks):
            path=Path(t['original_record']['prediction_file'])
            assert sha(path)==t['original_record']['prediction_sha256']
            with np.load(path) as z:
                shape=torch.from_numpy(z['shape']);face=torch.from_numpy(z['face'])
                params=torch.from_numpy(z['mhr_model_params']);body=z['pred_vertices'].reshape(-1,3)
                with np.load(OUT/'geometry'/t['truth']) as gt:rotation=gt['global_rot'].copy()
                reproduced,_=model(shape,params,face)
                reproduced=reproduced.numpy().reshape(-1,3)/100*np.array([1,-1,-1],np.float32)
                error=float(np.max(np.abs(reproduced-body)))
                assert error<1e-5,(t['key'],error)
                changed=params.clone();changed[:,3:6]=torch.from_numpy(rotation)
                assert torch.equal(changed[:,:3],params[:,:3]) and torch.equal(changed[:,6:],params[:,6:])
                v,_=model(shape,changed,face)
                v=v.numpy().reshape(-1,3)/100*np.array([1,-1,-1],np.float32)
                target=directory/(t['key']+'.npz')
                np.savez_compressed(target,vertices_true_root_m=v,
                    original_camera_m=z['original_camera'].reshape(3),
                    original_global_rot=z['global_rot'],true_global_rot=rotation)
                records.append(dict(key=t['key'],identity=t['identity'],role=t['role'],
                    source_sha256=sha(path),reproduction_max_abs_m=error,
                    output=target.name,output_sha256=sha(target)))
            if i%50==0:print('ROOT_SUBSTITUTION',i,400,flush=True)
    result=dict(status='COMPLETE',records=records,asset_sha256=sha(asset),code_sha256=sha(Path(__file__)),
        preserved='Official MHR params except global Euler indices 3:6; shape and face unchanged',
        renderer_used=False,SAM3D_forward=False,training=False,sealed_TEST_read=False,
        seconds=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (directory/'MANIFEST.json').write_text(json.dumps(result,indent=2))
    archive=OUT/'NATIVE_ROOT_SUBSTITUTION.tar'
    with tarfile.open(archive,'w') as tar:tar.add(directory,arcname='native_root_substitution')
    receipt=dict(status='PASS',path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive))
    (OUT/'NATIVE_ROOT_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print('ROOT_COMPLETE',json.dumps(receipt),flush=True)


if __name__=='__main__':run()
