"""Export finished evidence without rerunning any fit or model."""
import datetime,shutil,zipfile
import numpy as np
from common import ROOT,BASE,PREV,CASES,METHODS,read,write,sha

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)

def main():
    assert read(ROOT/'EXECUTION_LEDGER.json')['status']=='COMPLETE'
    public=ROOT/'export_public';public.mkdir(exist_ok=True)
    for p in ROOT.glob('*.json'):copy(p,public/p.name)
    copy(ROOT/'PROTOCOL.md',public/'PROTOCOL.md')
    for p in (ROOT/'code').glob('*.py'):copy(p,public/'code'/p.name)
    for p in (BASE/'delivery/code').glob('*.py'):copy(p,public/'frozen_baseline_code'/p.name)
    copy(PREV/'code/normal_d.py',public/'frozen_normal_code/normal_d.py')
    for p in ROOT.glob('*.csv'):copy(p,public/p.name)
    for p in (ROOT/'figures').glob('*'):copy(p,public/'figures'/p.name)
    copy(ROOT/'planar_witness.npz',public/'analytical_fixture/planar_witness.npz')
    cfg=read(ROOT/'CONTRACT.json')
    for subject in cfg['subjects']:
        copy(ROOT/'ledger'/(subject+'.json'),public/'ledger'/(subject+'.json'))
        for k in [0,1,2]:
            z=np.load(ROOT/'reference'/subject/f'K{k}.npz')
            fields=['R_world_to_camera','camera_center_world_m','K','optimization_idx','posterior_eval_idx']
            selected=np.unique(np.r_[z['optimization_idx'],z['posterior_eval_idx']])
            dest=public/'observation_indices'/subject/f'K{k}.npz';dest.parent.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(dest,**{name:z[name] for name in fields},source_point_idx=selected,
                **{name:z[name][selected] for name in ['pixel_flat_index','face_id','barycentric']})
        for case in CASES:
            source=ROOT/'runs'/subject/case;dest=public/'results'/subject/case
            for name in ['results.json','ledger.json']:copy(source/name,dest/name)
            for m in METHODS:
                copy(source/(m+'_probes.npz'),dest/(m+'_probes.npz'))
                for k in [1,2]:copy(source/f'{m}_K{k}_metrics.npz',dest/f'{m}_K{k}_metrics.npz')
    files=[]
    for folder in ['reference','runs','ledger','figures']:
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file():files.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
    write(public/'SERVER_OUTPUT_MANIFEST.json',dict(status='COMPLETE',rows=files))
    write(public/'PUBLIC_DATA_BOUNDARY.json',dict(raw_patient_RGB=False,raw_sensor_depth=False,weights=False,
        reference_and_final_human_geometry_arrays='server only: 20 references, 60 virtual observations, 240 final mesh NPZ',
        indices='60 virtual observation index/face/bary/camera NPZ; source_point_idx maps selected rows to original observation ordinal; no pointcloud coordinates',
        metrics='480 per-point NPZ and 240 engineering probe NPZ',
        analytical_fixture='simple procedural plane; no patient or native body-model asset',
        cache_coordinates='world meters, final vertices already transformed; do not apply stored rigid_R/t again',
        initial_cache_transform='INITIAL retains injected error; rigid_R/t stored as shared fit metadata, not an additional INITIAL transform',
        model_loaded=False,export_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    target=ROOT/'delivery_public.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(public.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(public).as_posix())
    print('EXPORT_COMPLETE',len(files),'MB',target.stat().st_size/1e6,flush=True)

if __name__=='__main__':main()
