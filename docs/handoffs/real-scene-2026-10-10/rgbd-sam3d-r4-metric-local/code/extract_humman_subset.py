"""Select only the frozen 44 sequences and Kinect 000/001; no model inference."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    root = args.root
    split = json.loads((root/'project_snapshot/research/rgbd_sam3d_mhr/INITIAL_IDENTITY_SPLIT_V1.json').read_text())
    sequences = sorted(split['sequence_roles'])
    binary = root/'external/7zip/7zz'
    jobs = [('point_kinect_color_part_02.7z','kinect_color'),
            ('point_kinect_depth_part_11.7z','kinect_depth'),
            ('point_kinect_mask.7z','kinect_mask')]
    records = []
    for archive, modality in jobs:
        targets = root/'datasets/manifests'/f'{modality}_targets.txt'
        paths = [f'{seq}/{modality}/{cam}'+('.mp4' if modality == 'kinect_color' else '/*')
                 for seq in sequences for cam in ['kinect_000','kinect_001']]
        targets.write_text('\n'.join(paths)+'\n')
        start = time.monotonic()
        command = [str(binary),'x',str(root/'datasets/raw'/archive),f'-i@{targets}',
                   f'-o{root}/datasets/processed','-y','-mmt=8','-bsp0']
        print('EXTRACT', archive, flush=True)
        subprocess.run(command, check=True)
        records.append(dict(archive=archive, include_file=str(targets),
                            seconds=time.monotonic()-start, return_code=0))
    report = dict(status='EXTRACTED_FRAME_QA_PENDING', sequences=len(sequences),
                  subjects=sum(len(g) for g in split['groups'].values()), cameras=['kinect_000','kinect_001'], jobs=records)
    (root/'runs/HUMMAN_EXTRACTION_R1.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
