"""Inspect author ZIP64 directory before the complete download finishes."""
import io
import json
import zipfile
from pathlib import Path

import requests

from download_ct_subset import ROOT


class HTTPArchive(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.session = requests.Session()
        self.segments = []
        self.tail_start = max(0, size - 4 * 1024 * 1024)
        self.tail = self._range(self.tail_start, size)

    def _range(self, start, end):
        response = self.session.get(self.url, headers={'Range': f'bytes={start}-{end - 1}'}, timeout=90)
        assert response.status_code == 206
        assert response.headers['Content-Range'].startswith(f'bytes {start}-{end - 1}/')
        return response.content

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def tell(self):
        return self.pos

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.pos + size)
        segment = next(((a, b) for a, b in self.segments if a <= self.pos and end <= a + len(b)), None)
        if segment:
            a, b = segment
            value = b[self.pos - a:end - a]
        elif self.pos >= self.tail_start:
            value = self.tail[self.pos - self.tail_start:end - self.tail_start]
        else:
            value = self._range(self.pos, end)
        self.pos = end
        return value


def main():
    metadata = json.loads((ROOT / 'ZENODO_RECORD.json').read_text())
    entry = metadata['files'][0]
    with zipfile.ZipFile(HTTPArchive(entry['links']['self'], entry['size'])) as z:
        members = [dict(name=x.filename, size=x.file_size, compressed=x.compress_size,
                        header_offset=x.header_offset, crc=x.CRC) for x in z.infolist()]
        (ROOT / 'ZIP_MEMBERS.json').write_text(json.dumps(members, indent=2))
        print('members', len(members), flush=True)
        print(json.dumps(members[:12], indent=2), flush=True)
        misc = [x['name'] for x in members if not x['name'].endswith(('.nii.gz', '/'))]
        print('metadata_members', misc, flush=True)
        for name in misc:
            if name.endswith(('.csv', '.json', '.md', '.txt')):
                text = z.read(name).decode('utf-8')
                dest = ROOT / 'archive_metadata' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text)
                print(name, text[:1700], flush=True)


if __name__ == '__main__':
    main()
