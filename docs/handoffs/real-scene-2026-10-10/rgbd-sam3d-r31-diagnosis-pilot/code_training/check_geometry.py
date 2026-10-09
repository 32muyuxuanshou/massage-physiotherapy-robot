"""Analytic positive-path check of the SAME affine RGB/metric Depth crop."""
import argparse
import json
from pathlib import Path
import torch
from geometry import crop_registered_depth


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    torch.set_num_threads(1)
    v, u = torch.meshgrid(torch.arange(512), torch.arange(512), indexing='ij')
    z = (2 + u * .001 + v * .0001).float()[None, None]
    K = torch.tensor([[[800., 0, 255.], [0, 900., 254.], [0, 0, 1.]]])
    batch = dict(img=torch.zeros(1, 2, 3, 512, 512), cam_int=K,
        affine_trans=torch.tensor([[[[1., 0, 0], [0, 1, 0]],
                                    [[1., 0, 10], [0, 1, 0]]]]))
    cropped, valid, rays = crop_registered_depth(z, batch)
    expected = torch.cat((z[:, :, :, 64:448], z[:, :, :, 54:438]), 0)
    assert torch.equal(cropped, expected)
    assert valid.all()
    expected_x = torch.stack(((u[:, 64:448]-255)/800,
                              (u[:, 54:438]-255)/800)).float()
    expected_y = ((v[:, 64:448]-254)/900).float().expand(2, -1, -1)
    assert torch.allclose(rays[:, 0], expected_x, atol=1e-6)
    assert torch.allclose(rays[:, 1], expected_y, atol=1e-6)
    batch['affine_trans'][0, 0, 0, 2] = 1000
    outside, outside_valid, _ = crop_registered_depth(z, batch)
    assert not outside_valid[0].any() and not outside[0].any()
    report = dict(status='PASS', scope='ANALYTIC_REGISTERED_DEPTH_CROP_ONLY',
        depth_unit='metre', crop_hw=list(cropped.shape[-2:]),
        persons_same_original_image=2, exact_metric_depth=True,
        camera_rays_max_abs_error=float((rays[:, 0]-expected_x).abs().max()),
        original_K_preserved=True, out_of_image_missing_depth=True,
        note='Does not prove HuMMan raw Depth->RGB registration or native SAM/MHR execution.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
