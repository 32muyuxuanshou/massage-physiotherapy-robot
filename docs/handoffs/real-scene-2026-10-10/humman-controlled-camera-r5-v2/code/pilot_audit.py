"""Independent CPU/GPU pilot comparison and runtime receipt."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import numpy as np

root=Path('/raid5/xuhd/rgbd_sam3d/r5_controlled_camera_v2')
keys=['depth_clean_m','depth_m','mask','K','R_world_to_camera','T_world_to_camera','normals_camera','surface_face_id']
checks=[]
for path in sorted((root/'pilot_cpu/samples').glob('*.npz')):
    cpu=np.load(path);gpu=np.load(root/'pilot_cuda/samples'/path.name)
    exact={k:bool(np.array_equal(cpu[k],gpu[k])) for k in keys}
    assert all(exact.values()),exact
    checks.append(dict(sample_id=path.stem,geometric_fields_exact=exact,
                       rgb_mean_abs_difference=float(np.abs(cpu['rgb'].astype(float)-gpu['rgb']).mean())))
assert len(checks)==64
g=lambda x:json.loads((root/x).read_text())
report=dict(status='PILOT_PASS',samples=64,CPU=g('pilot_cpu/GEOMETRY_QA.json'),
            CUDA=g('pilot_cuda/GEOMETRY_QA.json'),camera_factors=g('pilot_cuda/CAMERA_FACTOR_QA.json'),
            CPU_CUDA_geometry_exact=True,checks=checks,
            optix_status='REJECTED: repeated sequential-render segmentation fault',
            cuda_status='64 sequential renders and all geometry QA passed')
(root/'PILOT_QA.json').write_text(json.dumps(report,indent=2))
environment=dict(host='172.18.6.218',port=436,username='xuhd',platform=platform.platform(),
                 python=platform.python_version(),numpy=np.__version__,device='CUDA',
                 gpu_inventory=subprocess.check_output(['nvidia-smi','--query-gpu=index,name,memory.total,driver_version','--format=csv']).decode(),
                 blender='3.3.21 / e016c21db151',render_samples=16,cpu_threads_per_worker=4,
                 runtime_archive_sha256=hashlib.sha256((root/'runtime/blender-3.3.21-linux-x64.tar.xz').read_bytes()).hexdigest(),
                 HDRI_sha256=hashlib.sha256((root/'assets/studio_small_03_1k.hdr').read_bytes()).hexdigest(),
                 source_archive_sha256=hashlib.sha256(Path('/raid5/xuhd/rgbd_sam3d_backups/r5_textured_resynthesis_v1/source_direct_backup.tar.gz').read_bytes()).hexdigest(),
                 downloads_use_proxy=False,training_started=False,server_shutdown=False)
(root/'ENVIRONMENT.json').write_text(json.dumps(environment,indent=2))
print(json.dumps(dict(status='PILOT_PASS',CPU_CUDA_geometry_exact=True,samples=len(checks))),flush=True)
