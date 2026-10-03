"""Export completed cached results and figures. No inference or fitting."""
import shutil,zipfile,datetime
from pathlib import Path
from common import ROOT,BASE,OLD,METHODS,read,write,sha,token

def copy(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)

def archive(folder,path):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(folder).as_posix())

def main():
    public=ROOT/'export_public';private=ROOT/'export_private'
    public.mkdir(exist_ok=True);private.mkdir(exist_ok=True)
    cfg=read(ROOT/'c_pressure_normal/EXECUTION_CONTRACT.json')
    for name in ['EXECUTION_LEDGER.json','EXECUTION_ENVIRONMENT.json','IMPLEMENTATION_CORRECTION_AUDIT.json','C_NORMAL_SOLVER_CHECK.json']:
        copy(ROOT/name,public/name)
    for p in (ROOT/'code').glob('*.py'):copy(p,public/'code'/p.name)
    for p in (ROOT/'a_atlas').glob('*.json'):copy(p,public/'results/a_atlas'/p.name)
    copy(ROOT/'a_atlas/CANONICAL_OLD_NEW.png',public/'figures/CANONICAL_OLD_NEW.png')
    for p in (ROOT/'b_qualification').glob('*.json'):copy(p,public/'results/b_qualification'/p.name)
    for p in (ROOT/'b_qualification/draft_default_source').glob('*.json'):copy(p,public/'results/b_qualification/draft_default_source'/p.name)
    for p in (ROOT/'c_pressure_normal').glob('*'):
        if p.is_file() and p.suffix in ('.json','.csv'):copy(p,public/'results/c_pressure_normal'/p.name)
    for p in (ROOT/'c_pressure_normal/ledger').glob('*.json'):copy(p,public/'results/c_pressure_normal/ledger'/p.name)
    for p in (ROOT/'c_pressure_normal/public_visuals').glob('*'):copy(p,public/'figures'/p.name)
    for subject in cfg['subjects']:
        copy(ROOT/'c_pressure_normal/evaluation'/subject/'results.json',public/'results/c_pressure_normal/evaluation'/subject/'results.json')
        for seed in cfg['seeds']:
            copy(ROOT/'c_pressure_normal/inputs'/subject/f'split_{seed}.npz',public/'indices'/subject/f'split_{seed}.npz')
            for method in METHODS:
                name=token(method)
                copy(ROOT/'c_pressure_normal/meshes'/subject/f'seed_{seed}'/(name+'.json'),public/'cache_metadata'/subject/f'seed_{seed}'/(name+'.json'))
                copy(ROOT/'c_pressure_normal/evaluation'/subject/f'seed_{seed}'/(name+'_metrics.npz'),public/'per_point_metrics'/subject/f'seed_{seed}'/(name+'_metrics.npz'))
            copy(ROOT/'c_pressure_normal/visualizations'/subject/f'seed_{seed}/comparison.jpg',private/'pressurepose'/f'{subject}_seed{seed}.jpg')
    for p in (ROOT/'b_qualification/private_images').glob('*.jpg'):copy(p,private/'behave'/p.name)
    for p in (BASE/'delivery/code').glob('*.py'):copy(p,public/'frozen_baseline_code'/p.name)
    for name in ['EXPERIMENT_CONTRACT.json','POSTERIOR_FACE_MASK.json','POSTERIOR_RGB_ROI.json']:
        copy(BASE/'delivery'/name,public/'frozen_baseline_code'/name)
    for name in ['run_cached_point_diagnostics.py','behave_v2_io.py']:
        copy(OLD/'code'/name,public/'frozen_audit_code'/name)
    official=Path('/raid5/xuhd/behave_rgbd_mesh_v1/behave-dataset/data/kinect_transform.py')
    copy(official,public/'reference_code/kinect_transform.py')
    copy(ROOT/'c_pressure_normal_attempt1/code_snapshot/normal_d.py',public/'retained_attempt1_code/normal_d.py')
    copy(ROOT/'c_pressure_normal_attempt1/code_snapshot/test_normal_d.py',public/'retained_attempt1_code/test_normal_d.py')
    assets=[]
    for p in sorted((ROOT/'c_pressure_normal').rglob('*')):
        if p.is_file():assets.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
    write(public/'SERVER_OUTPUT_MANIFEST.json',dict(status='COMPLETE',rows=assets,model_loaded=False))
    visuals=[]
    for folder,dataset in [(ROOT/'c_pressure_normal/visualizations','PressurePose cached RGB comparisons'),(ROOT/'b_qualification/private_images','BEHAVE original-data qualification')]:
        files=sorted(folder.glob('*/seed_*/comparison.jpg')) if dataset.startswith('PressurePose') else sorted(folder.glob('*.jpg'))
        for p in files:visuals.append(dict(dataset=dataset,path=str(p),sha256=sha(p)))
    write(public/'SERVER_PRIVATE_VISUAL_MANIFEST.json',dict(rows=visuals,public_rgb_redistribution=False))
    write(public/'PUBLIC_DATA_BOUNDARY.json',dict(raw_rgb_in_git=False,raw_depth_in_git=False,pointcloud_coordinates_in_git=False,
        weights_or_native_mhr_assets_in_git=False,final_mesh_arrays='server only; 240 NPZ',
        indices='60 exact original spatial split NPZ',per_point_metrics='240 distance/ray/index NPZ; no sensor coordinates',
        neutral_probe_coordinates='derived predictions; not measured acupoint truth',
        official_reference_source=dict(path=str(official),sha256=sha(official)),
        actual_fitting_source_freeze=str(ROOT/'c_pressure_normal/RUNTIME_SOURCE_FREEZE.json'),
        export_captured_server_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    archive(public,ROOT/'delivery_public.zip');archive(private,ROOT/'delivery_private.zip')
    print('EXPORTED',len(assets),len(visuals),'public_MB',(ROOT/'delivery_public.zip').stat().st_size/1e6,
        'private_MB',(ROOT/'delivery_private.zip').stat().st_size/1e6,flush=True)

if __name__=='__main__':main()
