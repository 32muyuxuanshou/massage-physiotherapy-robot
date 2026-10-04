"""Record this finite pilot's actual inputs, code, protocol and execution environment."""
import hashlib
import json
import platform
from datetime import datetime, timezone

import torch

from prepare_pilot import OUT, sha, write


def main():
    manifest = json.loads((OUT / 'CASE_MANIFEST.json').read_text())
    inputs = [r for r in manifest if r['eligible']]
    write(OUT / 'EXECUTION_FREEZE.json', dict(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=sha(OUT / 'PROTOCOL.json'),
        manifest_sha256=sha(OUT / 'CASE_MANIFEST.json'),
        code_sha256={p.name: sha(p) for p in sorted((OUT / 'code').glob('*')) if p.is_file()},
        input_sha256={r['subject']: r['input_sha256'] for r in inputs},
        environment=dict(python=platform.python_version(), torch=torch.__version__, cuda=torch.version.cuda),
        scope='CT-source pilot; no SAM rerun, no medical ground truth',
    ))
    print('EXECUTION_FROZEN', len(inputs), flush=True)


if __name__ == '__main__':
    main()
