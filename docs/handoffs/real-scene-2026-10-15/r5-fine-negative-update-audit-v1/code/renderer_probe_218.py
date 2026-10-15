"""Verify the unchanged rasterizer on analytic camera-Z planes on GPU 218."""
import json
from pathlib import Path
import time
import torch
import numpy as np
from frozen_render_losses import MeshRenderer

work=Path('/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1')
start=time.monotonic();torch.set_num_threads(4)
faces=torch.tensor([[0,1,2]],device='cuda')
renderer=MeshRenderer(faces)
K=torch.tensor([[[500.,0,320.],[0,500.,240.],[0,0,1.]]],device='cuda')
vertices=torch.tensor([[[-1.,-1.,1.],[1.,-1.,3.],[0.,1.,2.]]],device='cuda')
depth,_=renderer(vertices,K)
tri=vertices[0].cpu().numpy();normal=np.cross(tri[1]-tri[0],tri[2]-tri[0])
checks=[]
for u,v in [(320,240),(330,240),(320,250),(310,230)]:
    ray=np.array([(u-320)/500,(v-240)/500,1.])
    true_z=float(np.dot(normal,tri[0])/np.dot(normal,ray))
    value=float(depth[0,v,u]);error=abs(true_z-value)
    assert error<1e-5,(u,v,true_z,value,error)
    checks.append(dict(pixel=[u,v],expected_z_m=true_z,rendered_z_m=value,error_m=error))
report=dict(status='PASS',torch=torch.__version__,cuda=torch.version.cuda,
    GPU=torch.cuda.get_device_name(),checks=checks,seconds=time.monotonic()-start)
(work/'RENDERER_GPU_QA.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
