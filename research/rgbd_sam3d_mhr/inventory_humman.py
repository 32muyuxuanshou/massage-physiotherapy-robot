"""Stream 7z file metadata; no image pixels or model outputs are opened."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess


def catalog(binary, archive):
    records = defaultdict(lambda: defaultdict(lambda: {'files':0, 'bytes':0}))
    record = {}
    p = subprocess.Popen([str(binary), 'l', '-slt', str(archive)],
                         stdout=subprocess.PIPE, text=True)
    def consume(row):
        name = row.get('Path', '')
        match = re.search(r'(p\d+_a\d+)/(kinect_color|kinect_depth|kinect_mask)/(kinect_\d+)', name)
        if match and row.get('Folder') != '+':
            seq, modality, camera = match.groups()
            camera = camera.removesuffix('.mp4')
            item = records[seq][camera]
            item['files'] += 1
            item['bytes'] += int(row.get('Size', '0'))
    for line in p.stdout:
        line = line.rstrip('\n')
        if not line:
            consume(record); record = {}
        elif ' = ' in line:
            key, value = line.split(' = ', 1); record[key] = value
    consume(record)
    assert p.wait() == 0, archive.name
    return {k: dict(v) for k,v in records.items()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sevenzip', type=Path, required=True)
    p.add_argument('--raw', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    depth = catalog(args.sevenzip, args.raw/'point_kinect_depth_part_11.7z')
    color = catalog(args.sevenzip, args.raw/'point_kinect_color_part_02.7z')
    common = {s: sorted(set(depth[s]) & set(color[s])) for s in sorted(set(depth)&set(color))}
    common = {s:c for s,c in common.items() if len(c) >= 2}
    pair_counts = {}
    for a,b in [('kinect_000','kinect_001'),('kinect_008','kinect_009')]:
        seqs = [s for s,c in common.items() if a in c and b in c]
        pair_counts[a+'+'+b] = dict(sequences=len(seqs),
            subjects=len({s.split('_')[0] for s in seqs}),
            selected_uncompressed_bytes=sum(depth[s][c]['bytes']+color[s][c]['bytes']
                                            for s in seqs for c in [a,b]))
    report = dict(status='RGB_DEPTH_CATALOG_ONLY_MASK_AND_FRAME_QA_PENDING',
        depth_sequences=len(depth), color_sequences=len(color),
        common_two_camera_sequences=len(common),
        common_subjects=sorted({s.split('_')[0] for s in common}),
        pair_counts=pair_counts, sequence_cameras=common,
        note='Archive names only. No pixels inspected, no final identity split, no frame sync/Mask QA yet.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['sequence_cameras','common_subjects']}))


if __name__ == '__main__':
    main()
