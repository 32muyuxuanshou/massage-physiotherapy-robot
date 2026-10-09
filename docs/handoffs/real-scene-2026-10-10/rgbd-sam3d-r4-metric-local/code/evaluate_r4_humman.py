"""Same frozen Camera B points and evaluator; R4 native adapter substitution."""
import os
os.environ.setdefault('MOMENTUM_ENABLED','0')
import argparse
from pathlib import Path
import torch
from fusion_r4 import R4Adapter
import evaluate_r3_humman as old


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path,required=True);a=p.parse_args();torch.set_num_threads(2)
    old.RGBDBodyAdapter=R4Adapter
    old.evaluate(a.root,a.root/'datasets/cache/humman_development_v1',a.root/'datasets/heldout/humman_r3_k1_v1',a.out,a.checkpoint)
