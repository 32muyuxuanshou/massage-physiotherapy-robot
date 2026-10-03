import io
import json
from collections import Counter
from pathlib import Path
import zipfile
import requests

ROOT = Path('/raid5/xuhd/datasets/back_prone_acquisition_20261003/dmd_bak')
SOURCE = 'https://www.kaggle.com/api/v1/datasets/download/chunzheye/dmd-bak?datasetVersionNumber=1'


class RangeReader(io.RawIOBase):
    def __init__(self):
        self.session = requests.Session()
        with self.session.get(SOURCE, headers={'Range': 'bytes=0-0'}, stream=True, timeout=(15, 45)) as response:
            if response.status_code != 206:
                raise RuntimeError(f'RANGE_NOT_SUPPORTED: {response.status_code}')
            self.size = int(response.headers['Content-Range'].split('/')[-1])
            self.url = response.url
            response.content
        self.position = 0
        self.downloaded = 1

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = (0 if whence == 0 else self.position if whence == 1 else self.size) + offset
        return self.position

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        if size == 0:
            return b''
        end = self.position + size - 1
        with self.session.get(self.url, headers={'Range': f'bytes={self.position}-{end}'},
                              stream=True, timeout=(15, 45)) as response:
            if response.status_code != 206:
                raise RuntimeError(f'RANGE_RESPONSE_INVALID: {response.status_code}')
            data = response.content
        assert len(data) == size, (len(data), size)
        self.position += size
        self.downloaded += size
        return data


if __name__ == '__main__':
    ROOT.mkdir(exist_ok=True)
    reader = RangeReader()
    with zipfile.ZipFile(reader) as archive:
        files = [{'name': row.filename, 'bytes': row.file_size,
                  'compressed_bytes': row.compress_size, 'crc32': row.CRC} for row in archive.infolist()]
        result = {'source': SOURCE, 'requested_version': 1, 'archive_bytes': reader.size,
                  'status': 'HISTORICAL_VERSION_WITHDRAWN_FOR_QUALITY_REVIEW',
                  'use': 'Archive inspection only; not accepted clinical/acupoint ground truth',
                  'suffix_counts': dict(Counter(Path(row['name']).suffix.lower() for row in files)), 'files': files}
        (ROOT / 'VERSION1_REMOTE_INVENTORY.json').write_text(json.dumps(result, indent=2))
        json_names = [row['name'] for row in files if row['name'].endswith('.json')]
        if json_names:
            name = json_names[0]
            data = archive.read(name)
            annotation = json.loads(data)
            # Do not print embedded image data.
            sample = {key: value for key, value in annotation.items() if key != 'imageData'}
            (ROOT / 'ANNOTATION_SAMPLE.json').write_text(json.dumps(sample, ensure_ascii=False, indent=2))
            result['first_annotation'] = {'name': name, 'keys': list(annotation),
                'imagePath': annotation.get('imagePath'), 'imageWidth': annotation.get('imageWidth'),
                'imageHeight': annotation.get('imageHeight'),
                'labels': dict(Counter(row['label'] for row in annotation.get('shapes', []))),
                'has_embedded_image': bool(annotation.get('imageData'))}
        result['network_bytes_read'] = reader.downloaded
        print(json.dumps({key: value for key, value in result.items() if key != 'files'}, ensure_ascii=False), flush=True)
        print(json.dumps({'first_files': files[:12], 'first_json_names': json_names[:10]}, ensure_ascii=False), flush=True)
