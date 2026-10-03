import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((root / 'source_metadata/dmd_bak_metadata.json').read_text())
    print(json.dumps({key: metadata.get(key) for key in
                      ('ref', 'title', 'currentVersionNumber', 'totalBytes', 'licenseName', 'description')},
                     ensure_ascii=False), flush=True)
    version = metadata['currentVersionNumber']
    url = f'https://www.kaggle.com/api/v1/datasets/download/chunzheye/dmd-bak?datasetVersionNumber={version}'
    folder = root / 'dmd_bak'
    folder.mkdir(exist_ok=True)
    archive = folder / f'dmd-bak-v{version}.zip'
    part = archive.with_suffix('.zip.part')
    with requests.get(url, stream=True, timeout=(20, 90)) as response:
        response.raise_for_status()
        size = 0
        sha = hashlib.sha256()
        with part.open('wb') as out:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    out.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)
    if not zipfile.is_zipfile(part):
        raise RuntimeError(f'NOT_A_ZIP: HTTP payload at {part}, {size} bytes')
    part.replace(archive)
    with zipfile.ZipFile(archive) as package:
        members = [{'name': info.filename, 'bytes': info.file_size} for info in package.infolist()]
        text_files = {}
        for info in package.infolist():
            if info.file_size < 10000 and info.filename.lower().endswith(('.txt', '.md')):
                text_files[info.filename] = package.read(info).decode('utf-8', errors='replace')
    result = {'time_utc': datetime.now(timezone.utc).isoformat(), 'source': url,
              'metadata_version': version, 'path': str(archive), 'bytes': size,
              'sha256': sha.hexdigest(), 'members': members, 'small_text_files': text_files,
              'actual_image_count': sum(row['name'].lower().endswith(('.jpg', '.png', '.jpeg')) for row in members)}
    (folder / 'DOWNLOAD_CONTENT_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
