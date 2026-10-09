"""Physical Z / perspective interpolation and gradient check before training."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from render_losses import MeshRenderer


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    faces=torch.tensor([[0,1,2],[0,2,3]],device='cuda')
    # Slanted plane Z=2+0.2X: analytic intersection tests perspective Z, not
    # affine interpolation of vertex depths in screen space.
    v=torch.tensor([[[-1.,-.7,1.8],[1.,-.7,2.2],[1.,.7,2.2],[-1.,.7,1.8]]],device='cuda',requires_grad=True)
    K=torch.tensor([[[100.,0,80.],[0,100.,60.],[0,0,1.]]],device='cuda')
    render=MeshRenderer(faces,120,160)
    d,s=render(v,K)
    yy,xx=torch.meshgrid(torch.arange(120,device='cuda'),torch.arange(160,device='cuda'),indexing='ij')
    # Explicit CV pixel-centre convention; rasterizer's half pixel is in projection.
    expected=2/(1-.2*(xx-80)/100)
    hit=d[0]>0
    error=float((d[0][hit]-expected[hit]).abs().max().detach())
    assert error<1e-5,'PERSPECTIVE_Z_INTERPOLATION_FAILED'
    (d.sum()+s.sum()).backward()
    gradient=float(v.grad.norm());assert gradient>0 and torch.isfinite(v.grad).all()
    fixture=np.load(args.fixture)
    vertices=torch.from_numpy(fixture['pred_vertices']+fixture['pred_cam_t'][:,None]).cuda()
    native=MeshRenderer(torch.from_numpy(fixture['faces']))
    # Existing R1 fixture used raw pyrender viewport intrinsics; convert only
    # the known pixel-centre convention, not a fit to predicted geometry.
    fixture_K=fixture['K'].copy();fixture_K[:2,2]-=.5
    with torch.no_grad():rendered,sil=native(vertices,torch.from_numpy(fixture_K[None]).cuda())
    target=torch.from_numpy(fixture['depth_m'][None]).cuda()
    common=(rendered>0)&(target>0)
    residual=(rendered[common]-target[common]).abs()
    median=float(residual.median());p95=float(torch.quantile(residual,.95))
    # Cross-renderer edge rasterization differs; report coverage and P95 as well.
    assert median<.002,'NATIVE_RENDER_CAMERA_CONTRACT_FAILED'
    report=dict(status='PASS',analytic_plane_max_error_m=error,gradient_norm=gradient,
        native_pyrender_common_median_mm=median*1000,native_pyrender_common_p95_mm=p95*1000,
        native_hit_rate=float(common.sum()/(target>0).sum()),
        camera_contract='metre camera-Z; OpenCV y down; pyrender IntrinsicsCamera projection; no distortion',
        pixel_center_contract='CV integer pixel centres; +0.5 in viewport projection; R1 viewport K converted by -0.5.',
        synthesis_depth_source='Native MHR geometry rendered by this perspective renderer; pyrender RGB uses +0.5 viewport principal point.')
    args.out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
