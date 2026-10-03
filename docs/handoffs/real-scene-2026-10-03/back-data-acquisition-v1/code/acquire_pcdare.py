import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--selection', required=True)
    args = parser.parse_args()
    root = Path(args.root)
    selection = json.loads(Path(args.selection).read_text())
    target = root / 'pcdare_35f7a1d9'
    if not target.exists():
        subprocess.run(['git', 'clone', '--depth', '1', '--no-checkout',
                        f"https://github.com/{selection['repository']}.git", str(target)], check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()
    assert commit == selection['commit'], (commit, selection['commit'])
    patterns = ''.join('/' + row['path'] + '\n' for row in selection['files'])
    subprocess.run(['git', 'config', 'core.sparseCheckout', 'true'], cwd=target, check=True)
    (target / '.git/info/sparse-checkout').write_text(patterns)
    subprocess.run(['git', 'read-tree', '-mu', 'HEAD'], cwd=target, check=True)
    results = []
    for row in selection['files']:
        path = target / row['path']
        data = path.read_bytes()
        blob_sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert len(data) == row['size'] and blob_sha == row['sha'], path
        results.append({'path': row['path'], 'bytes': len(data), 'git_blob_sha1': blob_sha,
                        'sha256': hashlib.sha256(data).hexdigest()})
    report = {'status': 'DOWNLOAD_AND_BLOB_IDENTITY_PASS', 'repository': selection['repository'],
              'commit': commit, 'root': str(target), 'file_count': len(results),
              'total_bytes': sum(row['bytes'] for row in results), 'files': results}
    (root / 'PCDARE_DOWNLOAD_AUDIT.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}), flush=True)


if __name__ == '__main__':
    main()
