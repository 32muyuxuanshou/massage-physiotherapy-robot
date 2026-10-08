"""Reopen the actual original cache files; separate from self-contained point replay."""
import json, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]


def main():
    manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for row in manifest['rows']:
        p = REPO / row['path']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256'], p
    result = dict(status='PASS', source_files_reopened=len(manifest['rows']),
        historical_hash_checks=manifest['historical_hash_checks'], changed_sources=[], server_used=False)
    (ROOT / 'POST_EXECUTION_SOURCE_INTEGRITY.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__': main()
