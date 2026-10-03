import json
from collections import Counter
from pathlib import Path
import subprocess

ROOT = Path(__file__).parent / 'metadata'
ROOT.mkdir(exist_ok=True)
REPO = 'mkaisereth/PCdareSoftware'
COMMIT = '35f7a1d9c1b24264708111a986ba89bdf17f1df1'
response = subprocess.run(['gh', 'api', f'repos/{REPO}/git/trees/{COMMIT}?recursive=1'],
                          check=True, capture_output=True, encoding='utf-8')
tree = json.loads(response.stdout)
(ROOT / 'pcdare_tree.json').write_text(json.dumps(tree, indent=2), encoding='utf-8')
files = [row for row in tree['tree'] if row['type'] == 'blob']
selected = [row for row in files if
            row['path'] in ('README.md', 'LICENSE', 'StartPCdareRegisterApp.m') or
            row['path'].startswith(('Asymmetry/', 'XrayRegistration/')) and row['path'].endswith('.m') or
            row['path'].lower().endswith(('.ply', '.json')) and row['path'].startswith(
                ('Asymmetry/Data/', 'Balgrist/', 'IIR/'))]
manifest = {'repository': REPO, 'commit': COMMIT,
            'purpose': 'Research back-surface and reference-line data; not prone RGB-D or acupoint ground truth',
            'selection': 'Back point clouds and associated published marker/line JSON; skip radiographs/DICOM',
            'license': 'CC BY-NC-SA 4.0 per repository README and LICENSE',
            'files': selected, 'total_bytes': sum(row['size'] for row in selected)}
(ROOT / 'PCDARE_SELECTION.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'repo_total_bytes': sum(row['size'] for row in files),
                  'repo_total_files': len(files), 'selected_bytes': manifest['total_bytes'],
                  'selected_files': len(selected),
                  'suffix_counts': dict(Counter(Path(row['path']).suffix for row in selected)),
                  'first_surface_files': [row['path'] for row in selected if row['path'].endswith('.ply')][:12],
                  'balgrist_files': [row['path'] for row in selected if row['path'].startswith('Balgrist/')][:14]}))
