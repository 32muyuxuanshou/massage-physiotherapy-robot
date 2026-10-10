"""Finalize only verified existing data after the documented float32 QA repair."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

root=Path('/raid5/xuhd/rgbd_sam3d/r5_controlled_camera_v2')
load=lambda p:json.loads((root/p).read_text())
assert load('dataset/FINAL_DATASET_QA.json')['status']=='FINAL_DATASET_QA_PASS'
assert load('dataset/CAMERA_FACTOR_QA.json')['status']=='CAMERA_FACTOR_QA_PASS'
preview=load('previews/PREVIEW_RECEIPT.json');assert preview['rgb_images']==3072 and preview['all_asset_sheets']==48
ledger=load('EXECUTION_LEDGER.json')
assert hashlib.sha256((root/'RENDER_PLAN.json').read_bytes()).hexdigest()==ledger['plan_sha256']
now=datetime.now(timezone.utc)
ledger.update(status='COMPLETE',completed_utc=now.isoformat(),
              elapsed_s=(now-datetime.fromisoformat(ledger['started_utc'])).total_seconds(),
              samples=3072,lanes=list(range(8)),final_dataset_qa='PASS',camera_factor_qa='PASS',previews='COMPLETE',
              cached_finalize_after_numeric_qa_repair=True,renderer_or_sample_cache_rerun=False,
              qa_repair='1 micrometre arbitrary tolerance -> 8*float32 epsilon*4m; actual max 1.412 micrometres')
(root/'EXECUTION_LEDGER.json').write_text(json.dumps(ledger,indent=2))
sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'code').glob('*.py')}
(root/'CODE_SOURCE_SHA256.json').write_text(json.dumps(sha,indent=2))
print(json.dumps(ledger),flush=True)
