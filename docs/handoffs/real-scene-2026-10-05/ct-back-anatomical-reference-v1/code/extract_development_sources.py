"""Read two preselected author-train cases while archive acquisition continues."""
import hashlib
import json
import time
import zipfile

from download_ct_subset import ROOT
from inspect_archive import HTTPArchive


def main():
    entry = json.loads((ROOT / 'ZENODO_RECORD.json').read_text())['files'][0]
    archive = HTTPArchive(entry['links']['self'], entry['size'])
    members = json.loads((ROOT / 'ZIP_MEMBERS.json').read_text())
    receipt = []
    with zipfile.ZipFile(archive) as z:
        for subject in ['s0011', 's0250']:
            start = time.monotonic()
            rows = [x for x in members if x['name'].startswith(subject + '/') and x['size']]
            a = min(x['header_offset'] for x in rows)
            b = max(x['header_offset'] + x['compressed'] + 512 for x in rows)
            archive.segments = [(a, archive._range(a, min(b, entry['size'])))]
            for row in rows:
                name = row['name']
                if name.endswith('/ct.nii.gz') or any(k in name for k in ['vertebrae_', 'scapula_', 'hip_', 'sacrum']):
                    value = z.read(name)  # ZipFile verifies the author's entry CRC.
                    dest = ROOT / 'raw' / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(value)
                    receipt.append(dict(name=name, bytes=len(value), sha256=hashlib.sha256(value).hexdigest(), crc=row['crc']))
            print(subject, 'extracted', round(time.monotonic() - start, 2), 'seconds', flush=True)
    (ROOT / 'DEVELOPMENT_SOURCE_RECEIPT.json').write_text(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
