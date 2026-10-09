"""CPU module verification. This is NOT a full SAM/MHR training result."""
import argparse
import json
from pathlib import Path
import torch
from fusion import SpatialDepthFusion


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--full-grid', action='store_true', help='Use the actual 512x384 / 1280x32x24 fusion contract')
    args = p.parse_args()
    torch.set_num_threads(1)
    torch.manual_seed(42)
    h,w,hidden,heads = (32,24,256,8) if args.full_grid else (4,3,64,4)
    report = {'scope': 'FUSION_MODULE_ONLY_NOT_NATIVE_MHR_R1',
              'rgb_feature_shape':[1,1280,h,w], 'depth_shape':[1,1,h*16,w*16], 'methods': {}}
    for mode in ['cross_attention', 'residual']:
        model = SpatialDepthFusion(rgb_channels=1280, hidden=hidden, heads=heads, mode=mode)
        rgb = torch.randn(1, 1280, h, w)
        depth = torch.rand(1, 1, h*16, w*16)*.3+1.5
        valid = torch.ones_like(depth, dtype=torch.bool)
        rays = torch.randn(1, 2, h*16, w*16)*.1
        assert torch.equal(model(rgb, depth, valid, rays), rgb)
        before = {k: v.detach().clone() for k, v in model.state_dict().items()}
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        gradients = []
        for step in range(3):
            opt.zero_grad()
            loss = (model(rgb, depth, valid, rays) - .9*rgb).square().mean()
            loss.backward()
            gradients.append({k: float(v.grad.norm()) if v.grad is not None else None
                              for k,v in model.named_parameters()})
            opt.step()
        out = model(rgb, depth, valid, rays)
        changed_depth = model(rgb, depth+.2, valid, rays)
        absent = model(rgb, depth, torch.zeros_like(valid), rays)
        assert torch.equal(absent, rgb)
        assert not torch.equal(out, changed_depth)
        assert gradients[-1]['depth_encoder.0.weight'] > 0
        report['methods'][mode] = dict(initial_rgb_equivalence=True,
            missing_depth_equivalence=True, depth_changed_output=True,
            depth_change_rms=float((out-changed_depth).square().mean().sqrt().detach()),
            gradient_steps=gradients,
            updated_parameters=[k for k,v in model.state_dict().items() if not torch.equal(v, before[k])],
            note='Zero gate intentionally gives zero encoder gradients on step 0; verified nonzero later.')
    report['status'] = 'PASS'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps({'status':report['status'],'scope':report['scope']}))


if __name__ == '__main__':
    main()
