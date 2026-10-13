import argparse,hashlib,json,tarfile,shutil,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--assets-only',action='store_true');a=p.parse_args()
r=Path('/root/autodl-tmp/rgbd_sam3d/evaluations/behave_model_comparison_v1')
target=r.parent/('behave_model_comparison_v1_assets.tar.gz' if a.assets_only else 'behave_model_comparison_v1_private.tar.gz')
freeze=json.loads((r/'reports/MODEL_ASSET_FREEZE.json').read_text());config=json.loads((r/'reports/EXPERIMENT_CONFIG.json').read_text())
files=[p for p in r.rglob('*') if p.is_file() and not ('cache' in p.relative_to(r).parts and p.suffix=='.pt')]
upper=(sum(Path(x['path']).stat().st_size for x in freeze['assets']+freeze['checkpoints']) if a.assets_only else
       sum(p.stat().st_size for p in files)+sum(Path(x['path']).stat().st_size for x in config['source_files'])+len(files)*4096)
assert upper<shutil.disk_usage(r).free-500_000_000,(upper,shutil.disk_usage(r).free)
def keep(info):
 p=Path(info.name)
 return None if 'cache' in p.parts and p.suffix=='.pt' else info
with tarfile.open(target,mode='w:gz',compresslevel=1) as tar:
 if a.assets_only:
  for i,row in enumerate(freeze['assets']+freeze['checkpoints']):tar.add(row['path'],arcname='frozen_assets/'+str(i).zfill(2)+'_'+Path(row['path']).name)
 else:
  tar.add(r,arcname='behave_model_comparison_v1',filter=keep)
  for row in config['source_files']:tar.add(row['path'],arcname='frozen_sources/'+row['path'].lstrip('/'))
h=hashlib.sha256()
with target.open('rb') as f:
 for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
receipt=dict(status='SERVER_PRIVATE_ARCHIVE_COMPLETE',scope='assets' if a.assets_only else 'experiment',path=str(target),bytes=target.stat().st_size,sha256=h.hexdigest(),core_assets=6 if a.assets_only else 0,checkpoints=24 if a.assets_only else 0,
 skipped='Backbone feature .pt caches only; final native meshes/data/point indices/residuals/private images/core weights included',ended_unix=time.time())
(r/'reports'/('PRIVATE_ASSET_ARCHIVE_RECEIPT.json' if a.assets_only else 'PRIVATE_ARCHIVE_RECEIPT.json')).write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
