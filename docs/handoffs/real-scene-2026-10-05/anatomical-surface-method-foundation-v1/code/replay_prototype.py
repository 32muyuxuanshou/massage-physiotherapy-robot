"""Recompute normal-path losses from saved arrays and render all four train cases."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def smooth_l1(diff, beta):
    absolute = np.abs(diff)
    return float(np.where(absolute < beta, .5*diff*diff/beta, absolute-.5*beta).mean())


def main():
    receipt = json.loads((ROOT/'prototype_check/PROTOTYPE_CHECK.json').read_text())
    identity = json.loads((ROOT/'prototype_check/CASE_INPUT_IDENTITY.json').read_text())
    with np.load(ROOT/'prototype_check/normal_path_cache.npz') as data:
        surface = smooth_l1(data['predicted_surface_delta']-data['surface_delta'], .02)
        zero_correction_surface = smooth_l1(data['surface_delta'], .02)
        anatomy = smooth_l1((data['predicted_anatomical_coordinates']-data['anatomical_coordinates'])[data['anatomy_valid']], .05)
        assert abs(surface-receipt['final_components']['surface']) < 1e-6
        assert abs(anatomy-receipt['final_components']['anatomy']) < 1e-6
        figure_root = ROOT/'figures'; figure_root.mkdir(exist_ok=True)
        for i, record in enumerate(identity):
            origin = np.asarray(record['normalization_origin_mm']); scale=record['normalization_scale_mm']
            clean = (data['query'][i]+data['surface_delta'][i])*scale+origin
            predicted = (data['query'][i]+data['predicted_surface_delta'][i])*scale+origin
            noisy = data['query'][i]*scale+origin
            observed = data['observed'][i]*scale+origin
            valid = data['anatomy_valid'][i]
            fig, axes = plt.subplots(1, 3, figsize=(13, 5))
            axes[0].scatter(observed[:, 0], observed[:, 2], s=3, c='lightgray')
            axes[0].scatter(clean[valid, 0], clean[valid, 2], c=data['anatomical_coordinates'][i, valid, 0], vmin=-.3, vmax=1.3, s=13, cmap='viridis')
            axes[0].set_title('CT-derived interpolated level field')
            axes[1].scatter(observed[:, 0], observed[:, 2], s=3, c='lightgray')
            axes[1].scatter(predicted[valid, 0], predicted[valid, 2], c=data['predicted_anatomical_coordinates'][i, valid, 0], vmin=-.3, vmax=1.3, s=13, cmap='viridis')
            axes[1].set_title('Learned field: TRAIN ONLY')
            for ax in axes[:2]:
                ax.set_xlabel('RAS right / mm'); ax.set_ylabel('RAS superior / mm'); ax.set_aspect('equal')
            axes[2].hist(np.linalg.norm(noisy-clean, axis=1), bins=15, alpha=.5, label='10mm Gaussian query perturbation')
            axes[2].hist(np.linalg.norm(predicted-clean, axis=1), bins=15, alpha=.5, label='After 80 fit steps')
            axes[2].set_xlabel('Displacement to paired CT sample / mm');axes[2].legend(fontsize=7)
            axes[2].set_title('Synthetic perturbation; not sensor precision')
            fig.suptitle(record['subject']+' | Four-example normal-path verification, no test performance claim')
            fig.tight_layout();fig.savefig(figure_root/(record['subject']+'.png'),dpi=130);plt.close(fig)
    trace=receipt['trace']
    fig, ax=plt.subplots(figsize=(7,4))
    for key in ['surface','anatomy','total']:
        ax.plot([r['step'] for r in trace],[r[key] for r in trace],label=key)
    ax.set(xlabel='Update step',ylabel='Dimensionless loss',title='Four TRAIN examples: normal-path verification only');ax.legend()
    fig.tight_layout();fig.savefig(ROOT/'figures/train_only_trace.png',dpi=140);plt.close(fig)
    report=dict(status='PASS', cached_cases=len(identity), surface_loss=surface, anatomy_loss=anatomy,
                zero_correction_surface_loss=zero_correction_surface,
                surface_loss_beats_zero_correction=surface < zero_correction_surface,
                total_loss=surface+anatomy, component_tolerance=1e-6,
                CT_queries_used=4*256, held_out_scientific_eval=False)
    (ROOT/'prototype_check/CACHE_REPLAY.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
