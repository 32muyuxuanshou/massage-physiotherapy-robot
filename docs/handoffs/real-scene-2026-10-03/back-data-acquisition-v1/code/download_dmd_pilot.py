import hashlib
import json
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
import zipfile

from inspect_dmd_archive import RangeReader, ROOT, SOURCE

inventory = json.loads((ROOT / 'VERSION1_REMOTE_INVENTORY.json').read_text())
files = {row['name']: row for row in inventory['files']}
groups = defaultdict(list)
for name in files:
    path = PurePosixPath(name)
    if path.suffix.lower() not in ('.jpg', '.png'):
        continue
    annotation = str(path.with_suffix('.json'))
    if annotation in files:
        groups[str(path.parent)].append((name, annotation))

# An identity proxy only: directory grouping is not a verified subject ID.
selected = []
for group in sorted(groups):
    pairs = sorted(groups[group])
    indices = sorted({0, len(pairs) // 2, len(pairs) - 1})
    for index in indices:
        selected.append({'directory_proxy': group, 'image': pairs[index][0], 'annotation': pairs[index][1]})
selected = selected[:512]
folder = ROOT / 'historical_v1_quality_audit'
folder.mkdir(exist_ok=True)
(folder / 'SELECTION.json').write_text(json.dumps({
    'source': SOURCE, 'purpose': 'Quality audit and visual development; withdrawn labels are not medical ground truth',
    'selection': 'First/middle/last paired image in each directory, sorted directories, cap 512 pairs',
    'available_paired_images': sum(len(rows) for rows in groups.values()),
    'available_directory_proxies': len(groups), 'selected_pairs': len(selected), 'pairs': selected,
}, indent=2))

local = threading.local()


def fetch(item):
    if not hasattr(local, 'archive'):
        local.reader = RangeReader()
        local.archive = zipfile.ZipFile(local.reader)
    results = []
    for kind in ('image', 'annotation'):
        name = item[kind]
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = local.archive.read(name)  # zipfile verifies each selected entry's CRC.
        path.write_bytes(data)
        assert len(data) == files[name]['bytes']
        results.append({'kind': kind, 'name': name, 'path': str(path), 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest(), 'crc32_verified': True})
    return {'directory_proxy': item['directory_proxy'], 'files': results}


if __name__ == '__main__':
    print(json.dumps({'selected_pairs': len(selected), 'directory_proxies': len(groups),
                      'estimated_uncompressed_bytes': sum(files[item[kind]]['bytes']
                                                           for item in selected for kind in ('image', 'annotation'))}), flush=True)
    records = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = [pool.submit(fetch, item) for item in selected]
        for future in as_completed(pending):
            records.append(future.result())
            if len(records) % 16 == 0 or len(records) == len(selected):
                print(f'CRC_VERIFIED_PAIRS {len(records)}/{len(selected)}', flush=True)
    records.sort(key=lambda row: row['files'][0]['name'])
    report = {'status': 'DOWNLOADED_FOR_QUALITY_AUDIT_ONLY', 'source': SOURCE,
              'pair_count': len(records), 'directory_proxies': len({row['directory_proxy'] for row in records}),
              'bytes': sum(row['bytes'] for record in records for row in record['files']), 'records': records}
    (folder / 'DOWNLOAD_AUDIT.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != 'records'}), flush=True)
