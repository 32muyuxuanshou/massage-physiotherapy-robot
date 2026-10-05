"""Read only official ZIP directory and metadata before full transfer completes."""
import csv
import io
import json
import zipfile

import requests

from acquire_full_v3 import ROOT, URL, BYTES


class RemoteZip(io.RawIOBase):
    def __init__(self):
        self.pos = 0
        self.bytes_read = 0
        self.requests = 0

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else BYTES + offset
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = BYTES - self.pos
        n = min(n, BYTES - self.pos)
        if n == 0:
            return b''
        end = self.pos + n - 1
        with requests.get(URL, headers={'Range': f'bytes={self.pos}-{end}',
                                       'Accept-Encoding': 'identity'},
                          stream=True, timeout=(30, 180)) as response:
            response.raise_for_status()
            assert response.status_code == 206
            assert response.headers['Content-Range'] == f'bytes {self.pos}-{end}/{BYTES}'
            data = response.content
        assert len(data) == n
        self.pos += n
        self.bytes_read += n
        self.requests += 1
        return data


def main():
    source = RemoteZip()
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        metas = [n for n in names if n.endswith('meta.csv')]
        assert len(metas) == 1
        meta_bytes = archive.read(metas[0])
        rows = list(csv.DictReader(io.StringIO(meta_bytes.decode('utf-8-sig')), delimiter=';'))
        root = ROOT / 'archive_metadata'
        root.mkdir(parents=True, exist_ok=True)
        (root / 'meta.csv').write_bytes(meta_bytes)
        (root / 'archive_names.txt').write_text('\n'.join(names) + '\n')
        cases = sorted({n.rsplit('/ct.nii.gz', 1)[0].split('/')[-1]
                        for n in names if n.endswith('/ct.nii.gz')})
        split_counts = {}
        for row in rows:
            split = row.get('split', 'MISSING')
            split_counts[split] = split_counts.get(split, 0) + 1
        result = dict(status='METADATA_READ_ONLY', raw_files_downloaded=False,
                      official_url=URL, zip_entries=len(names), CT_cases=len(cases),
                      metadata_rows=len(rows), columns=list(rows[0]),
                      split_counts=split_counts, case_ids=cases,
                      segmentation_names=sorted({n.split('/')[-1] for n in names
                                                  if '/segmentations/' in n}),
                      range_bytes=source.bytes_read, range_requests=source.requests)
        (ROOT / 'ARCHIVE_INSPECTION.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k not in ['case_ids', 'segmentation_names']}, indent=2))


if __name__ == '__main__':
    main()
