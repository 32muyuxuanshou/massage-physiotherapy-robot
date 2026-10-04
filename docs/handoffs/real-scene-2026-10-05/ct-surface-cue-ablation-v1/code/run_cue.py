"""Finite input controls on the existing case split; no source rewriting."""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

BASE = Path('/raid5/xuhd/datasets/ct_anatomical_query_pilot_20261005')
OUT = Path('/raid5/xuhd/datasets/ct_surface_cue_ablation_20261005')
sys.path.insert(0, str(BASE / 'code'))
from model import AnatomicalQuery
from prepare_pilot import sha


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def mask_input(x, mode):
    x = x.clone()
    if mode != 'FULL_SURFACE':
        x[:, 0] = 0
    if mode == 'COORDS_ONLY':
        x[:, 1] = 0
    return x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', required=True)
    parser.add_argument('--mode', required=True)
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed); torch.backends.cudnn.benchmark = False
    rows = json.loads((BASE / 'CASE_MANIFEST.json').read_text())
    protocol = json.loads((OUT / 'PROTOCOL.json').read_text())
    data = {}
    for role in ['train', 'dev']:
        cohort = [r for r in rows if r['eligible'] and r['role'] == role]
        values = [dict(np.load(r['path'])) for r in cohort]
        data[role] = {k: torch.tensor(np.stack([v[k] for v in values]), device='cuda')
                      for k in ['input', 'target_uv', 'target_valid']}
        data[role]['input'] = mask_input(data[role]['input'], args.mode)
        data[role]['scale'] = torch.tensor([r['field_size_xz_mm'] for r in cohort], device='cuda')
    model = AnatomicalQuery(args.method).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001)
    folder = OUT / 'models' / (args.method + '_' + args.mode + '_seed' + str(args.seed))
    folder.mkdir(parents=True, exist_ok=True)
    best = float('inf'); history = []; start = time.monotonic()
    for epoch in range(1, 121):
        model.train(); order = torch.randperm(len(data['train']['input']), device='cuda')
        for batch in order.split(8):
            x = data['train']; pred = model(x['input'][batch]); valid = x['target_valid'][batch]
            loss = ((pred - x['target_uv'][batch]).square().sum(-1) * valid).sum() / valid.sum()
            optimizer.zero_grad(); loss.backward(); optimizer.step()
        if epoch % 10 == 0:
            model.eval()
            with torch.no_grad():
                x = data['dev']; pred = model(x['input'])
                error = torch.linalg.norm((pred - x['target_uv']) * x['scale'][:, None], dim=-1)
                score = float((error * x['target_valid']).sum() / x['target_valid'].sum())
            history.append(dict(epoch=epoch, dev_target_mean_xz_mm=score))
            if score < best:
                best = score
                torch.save(dict(state_dict=model.state_dict(), epoch=epoch, dev_score=score), folder / 'best.pt')
    write(folder / 'TRAINING.json', dict(method=args.method, mode=args.mode, seed=args.seed,
          history=history, seconds=time.monotonic()-start, checkpoint_sha256=sha(folder/'best.pt'),
          original_manifest_sha256=sha(BASE/'CASE_MANIFEST.json'), protocol_sha256=sha(OUT/'PROTOCOL.json'),
          source_model_py_sha256=sha(BASE/'code/model.py'), test_data_loaded=False))
    print(args.method, args.mode, args.seed, round(best, 3), flush=True)


if __name__ == '__main__':
    main()
