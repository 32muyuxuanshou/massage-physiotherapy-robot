"""Install verified PyPI packages locally, preserving the supplied base Torch."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys

REQUIRED = ['opencv-python-headless<5','scipy','timm','yacs','einops',
    'pytorch-lightning','hydra-core','roma','dill','pyrender','fvcore','pycocotools',
    'scikit-image','webdataset','loguru','optree','rich','pyrootutils',
    'huggingface_hub','py7zr','trimesh','joblib','pandas','tensorboard','wandb','pytest']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    before = {name: metadata.version(name) for name in ['torch','torchvision','numpy']}
    wheelhouse = args.root/'feature_cache/linux_wheels'
    command = [sys.executable,'-m','pip','install','--no-index','--no-build-isolation',
               '--find-links',str(wheelhouse),*REQUIRED]
    result = subprocess.run(command)
    record = dict(command=command, exit_code=result.returncode, base_before=before)
    (args.root/'runs/OFFLINE_INSTALL_R0.json').write_text(json.dumps(record,indent=2))
    result.check_returncode()
    after = {name: metadata.version(name) for name in before}
    assert before == after, 'BASE_TORCH_TORCHVISION_NUMPY_CHANGED'
    freeze = subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,check=True)
    (args.root/'runs/environment_freeze.txt').write_text(freeze.stdout)
    module = args.root/'project_snapshot/research/rgbd_sam3d_mhr'
    for script, output in [('check_fusion.py','FUSION_SERVER_CPU_CHECK.json'),
                           ('check_geometry.py','GEOMETRY_SERVER_CPU_CHECK.json')]:
        subprocess.run([sys.executable,str(module/script),'--out',str(args.root/'runs'/output)],check=True)
    # Imports only: does not instantiate/load the multi-GB native SAM/MHR model.
    import os
    os.environ['MOMENTUM_ENABLED'] = '0'
    sys.path.insert(0,str(args.root/'external/sam-3d-body'))
    import sam_3d_body
    record.update(status='R0_DEPENDENCIES_AND_IMPORT_PASS_NOT_FULL_MODEL',
        base_after=after, native_source_import=True, full_model_executed=False)
    (args.root/'runs/ENVIRONMENT_READY_R0.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({'status':record['status'],'base_unchanged':True}))


if __name__ == '__main__':
    main()
