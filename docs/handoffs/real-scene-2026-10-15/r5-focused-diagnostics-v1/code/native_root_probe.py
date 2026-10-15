"""CPU-only native MHR re-decoding probe; does not load SAM3D or its backbone."""
import json
from pathlib import Path
import resource
import time
import numpy as np
import torch

BASE = Path('/root/autodl-tmp/rgbd_sam3d')
OUT = BASE/'evaluations/r5_focused_diagnostics_v1'
torch.set_num_threads(1)
start=time.monotonic()
model=torch.jit.load(str(BASE/'checkpoints/official/sam-3d-body-vith/assets/mhr_model.pt'),map_location='cpu')
print('MHR_CPU_LOADED',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
p=np.load(BASE/'runs/r5_complete_comparison_v1/evaluation/full_s11_last/native/predictions/mhr3_0400_p0_c0.npz')
with torch.no_grad():
    v,_=model(torch.from_numpy(p['shape']),torch.from_numpy(p['mhr_model_params']),torch.from_numpy(p['face']))
v=v.numpy()/100*np.array([1,-1,-1],dtype=np.float32)
error=float(np.max(np.abs(v-p['pred_vertices'])))
assert error<1e-5,error
report=dict(status='PASS',reproduction_max_abs_m=error,
            peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            seconds=time.monotonic()-start,cuda_used=False,SAM3D_forward=False)
(OUT/'MHR_CPU_PROBE.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
