"""Acquire the author's 102-case exploration subset; do not train on it here."""
import hashlib
import json
import time
from pathlib import Path

import requests


ROOT = Path('/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005')
RECORD = 'https://zenodo.org/api/records/10047263'


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    record = requests.get(RECORD, timeout=30)
    record.raise_for_status()
    metadata = record.json()
    (ROOT / 'ZENODO_RECORD.json').write_text(json.dumps(metadata, indent=2))
    entry = metadata['files'][0]
    dest = ROOT / entry['key']
    start = time.monotonic()
    digest = hashlib.md5()
    count = 0
    with requests.get(entry['links']['self'], stream=True, timeout=(30, 90)) as response:
        response.raise_for_status()
        with dest.open('wb') as out:
            for block in response.iter_content(1024 * 1024):
                out.write(block)
                digest.update(block)
                count += len(block)
                if count % (128 * 1024 * 1024) == 0:
                    print(f'{count / 1e9:.2f} GB / {entry["size"] / 1e9:.2f} GB; {time.monotonic() - start:.1f} s', flush=True)
    actual = 'md5:' + digest.hexdigest()
    assert count == entry['size'] and actual == entry['checksum']
    result = dict(status='PASS', record=RECORD, filename=dest.name,
                  bytes=count, checksum=actual, author_checksum=entry['checksum'],
                  license=metadata['metadata'].get('license'), seconds=time.monotonic() - start,
                  use='SOURCE_QUALIFICATION_ONLY_NO_MODEL_TRAINING')
    (ROOT / 'DOWNLOAD_RESULT.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
