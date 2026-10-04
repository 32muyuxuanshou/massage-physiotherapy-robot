"""All frozen input controls, all seeds, all original eligible cases."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch

from run_cue import BASE, OUT, AnatomicalQuery, mask_input, sha, write
from evaluate_pilot import surface_position


def main():
    torch.set_num_threads(2)
    rows = [r for r in json.loads((BASE/'CASE_MANIFEST.json').read_text()) if r['eligible']]
    old = json.loads((BASE/'PER_CASE_RESULTS.json').read_text())
    methods = ['GLOBAL_REGRESSION', 'ORDERED_QUERY']; modes = ['FULL_SURFACE', 'MASK_COORDS', 'COORDS_ONLY']
    models = {}; receipts = []
    for method in methods:
        for mode in modes[1:]:
            for seed in [0, 1, 2]:
                path = OUT/'models'/(method+'_'+mode+'_seed'+str(seed))/'best.pt'
                model = AnatomicalQuery(method).cuda()
                model.load_state_dict(torch.load(path, map_location='cuda', weights_only=False)['state_dict'])
                models[method, mode, seed] = model.eval()
                receipts.append(dict(method=method, mode=mode, seed=seed, path=str(path), sha256=sha(path)))
    results = []; replay = []
    for row in rows:
        assert sha(Path(row['path'])) == row['input_sha256']
        data = dict(np.load(row['path'])); valid = data['target_valid'].astype(bool)
        scale = np.diff(data['xz_bounds_mm'].reshape(2, 2), axis=1).ravel()
        x = torch.tensor(data['input'][None], device='cuda')
        predictions = {}
        for method in methods:
            for mode in modes:
                for seed in [0, 1, 2]:
                    if mode == 'FULL_SURFACE':
                        source = next(r for r in old if (r['subject'], r['method'], r['seed']) == (row['subject'], method, seed))
                        assert sha(Path(source['path'])) == source['cache_sha256']
                        uv = np.load(source['path'])['pred_uv']; source_sha = source['cache_sha256']
                    else:
                        with torch.no_grad():
                            uv = models[method, mode, seed](mask_input(x, mode))[0].cpu().numpy()
                        source_sha = None
                    error = np.linalg.norm((uv-data['target_uv'])*scale, axis=1)
                    hit = np.array([surface_position(p, data) is not None for p in uv])
                    name = row['subject']+'_'+method+'_'+mode+'_seed'+str(seed)+'.npz'
                    path = OUT/'predictions'/row['role']/name; path.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(path, pred_uv=uv, target_uv=data['target_uv'], target_valid=valid, xz_error_mm=error, surface_hit=hit)
                    saved = dict(np.load(path))
                    assert np.allclose(np.linalg.norm((saved['pred_uv']-saved['target_uv'])*scale, axis=1), saved['xz_error_mm'], rtol=0, atol=1e-6)
                    replay.append(dict(path=str(path), sha256=sha(path), status='PASS'))
                    results.append(dict(subject=row['subject'], role=row['role'], method=method, mode=mode, seed=seed,
                         path=str(path), sha256=sha(path), input_sha256=row['input_sha256'], reused_full_prediction_sha256=source_sha,
                         mean_xz_mm=float(error[valid].mean()), valid_targets=int(valid.sum()), valid_hits=int((hit&valid).sum())))
                    predictions[method, mode, seed] = uv
        fig, axes = plt.subplots(1, 2, figsize=(10, 7))
        colors = dict(FULL_SURFACE='orange', MASK_COORDS='cyan', COORDS_ONLY='magenta')
        h, w = data['surface_valid'].shape
        for ax, method in zip(axes, methods):
            ax.imshow(np.ma.masked_where(~data['surface_valid'], data['surface_height_mm']), cmap='gray')
            target = data['target_uv']*np.array([w-1, h-1]); ax.scatter(target[valid, 0], target[valid, 1], c='red', s=35, label='CT proxy')
            for mode in modes:
                for seed in [0, 1, 2]:
                    pred = predictions[method, mode, seed]*np.array([w-1, h-1])
                    ax.scatter(pred[valid, 0], pred[valid, 1], c=colors[mode], s=10, alpha=.65, label=mode if seed==0 else None)
            ax.set_title(method); ax.legend(fontsize=7)
        fig.suptitle(row['subject']+' / '+row['role']+' | input-cue controls, not medical precision')
        fig.tight_layout(); (OUT/'figures').mkdir(exist_ok=True); fig.savefig(OUT/'figures'/(row['subject']+'.png'), dpi=130); plt.close(fig)
    summary = {}
    for role in ['train', 'dev', 'test', 'author_val_supporting']:
        summary[role] = {}
        for method in methods:
            summary[role][method] = {}
            for mode in modes:
                rr = [r for r in results if (r['role'], r['method'], r['mode']) == (role, method, mode)]
                ids = sorted(set(r['subject'] for r in rr))
                scores = {s: float(np.median([r['mean_xz_mm'] for r in rr if r['subject']==s])) for s in ids}
                summary[role][method][mode] = dict(cases=len(ids), case_equal_mean_xz_mm=float(np.mean(list(scores.values()))),
                    per_case=scores, per_seed={str(seed): float(np.mean([r['mean_xz_mm'] for r in rr if r['seed']==seed])) for seed in [0, 1, 2]},
                    surface_hit_fraction=sum(r['valid_hits'] for r in rr)/sum(r['valid_targets'] for r in rr))
    write(OUT/'PER_CASE_RESULTS.json', results)
    write(OUT/'RESULTS.json', summary)
    write(OUT/'MODEL_RECEIPTS.json', receipts)
    write(OUT/'CACHE_REPLAY.json', dict(status='PASS', actual_predictions=len(replay), actual_inputs=len(rows), records=replay))
    print(json.dumps(summary['test'], indent=2), flush=True)


if __name__ == '__main__':
    main()
