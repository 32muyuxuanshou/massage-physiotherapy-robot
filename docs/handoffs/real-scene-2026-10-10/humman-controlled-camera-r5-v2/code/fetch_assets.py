"""Fetch only preregistered HuMMan-Recon OBJ/MTL/texture members on the server."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import requests
from remotezip import RemoteZip


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--download-url', help='Optional direct mirror URL; immutable source revision must be unchanged')
    a = p.parse_args()
    plan = json.loads(a.plan.read_text(encoding='utf8'))
    a.out.mkdir(parents=True, exist_ok=True)
    receipt = dict(source_url=plan['source_url'], assets=[], started_unix=time.time())
    # Explicit direct HTTP: do not inherit environment or Windows proxy settings.
    session = requests.Session()
    session.trust_env = False
    receipt['http_proxy_policy'] = 'DIRECT; requests trust_env=False'
    url = a.download_url or plan['source_url']
    assert plan['source_revision'] in url
    receipt['download_url'] = url
    with RemoteZip(url, session=session, timeout=30) as archive:
        for asset in plan['assets']:
            records = []
            for name in asset['members']:
                target = a.out / name
                target.parent.mkdir(parents=True, exist_ok=True)
                info = archive.getinfo(name)
                if not target.exists() or target.stat().st_size != info.file_size:
                    target.write_bytes(archive.read(name))
                assert target.stat().st_size == info.file_size
                records.append(dict(member=name, bytes=info.file_size,
                                    sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
            receipt['assets'].append(dict(asset_id=asset['asset_id'], files=records))
            (a.out / 'DOWNLOAD_RECEIPT.json').write_text(json.dumps(receipt, indent=2))
            print('FETCHED', asset['asset_id'], len(receipt['assets']), flush=True)
    receipt['completed_unix'] = time.time()
    (a.out / 'DOWNLOAD_RECEIPT.json').write_text(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
