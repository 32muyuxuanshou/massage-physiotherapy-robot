"""Snapshot this completed diagnostic on 218 and independently SHA it on Windows."""
import hashlib
import json
import os
from pathlib import Path
import paramiko

WORK='/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1'
OUT=Path('output/r5_fine_negative_update_audit_v1')


def main():
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('172.18.6.218',port=436,username='xuhd',password=os.environ['ROBOT_SSH_PASSWORD'],
        timeout=25,look_for_keys=False,allow_agent=False)
    script='''import tarfile,json,hashlib
from pathlib import Path
w=Path("'''+WORK+'''");archive=w/'FINE_QUERY_DIAGNOSTICS.tar.gz'
files=list(w.glob('*.json'))+list(w.glob('*.log'))+list((w/'code').glob('*.py'))+list((w/'code').glob('*.sh'))+list((w/'code').glob('*.zip'))
files+=[w/'ENVIRONMENT_PACKAGES.txt']
for directory in ['reports','native_surface_tradeoff','query_replay_frozen_coarse','query_replay','pilot','probe']:
 files+=[p for p in (w/directory).rglob('*') if p.is_file()]
files=sorted(set(p for p in files if p.exists() and p.name not in ['BACKUP_RECEIPT.json','ARCHIVE_MANIFEST.json']))
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for p in files:t.add(p,arcname=str(p.relative_to(w)),recursive=False)
h=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(4194304),b''):h.update(block)
r=dict(path=str(archive),bytes=archive.stat().st_size,sha256=h.hexdigest(),files=len(files),excludes='Original 15.34GB caches, checkpoints and environment are retained separately; this archive contains newly produced query traces, all replay attempts, diagnostics, code and receipts')
(w/'ARCHIVE_MANIFEST.json').write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
'''
    command=WORK+'/../runtime218/env/bin/python - <<\'PY\'\n'+script+'\nPY'
    _,stdout,stderr=c.exec_command(command);data=stdout.read().decode();error=stderr.read().decode()
    if stdout.channel.recv_exit_status()!=0:raise RuntimeError(error)
    manifest=json.loads(data);target=OUT/Path(manifest['path']).name
    s=c.open_sftp();s.get(manifest['path'],str(target));h=hashlib.sha256()
    with target.open('rb') as f:
        for block in iter(lambda:f.read(4194304),b''):h.update(block)
    assert h.hexdigest()==manifest['sha256'] and target.stat().st_size==manifest['bytes']
    receipt=dict(status='218_WINDOWS_ACTUAL_SHA_MATCH',source=manifest,windows_path=str(target.resolve()),
        windows_sha256=h.hexdigest(),transport='Direct SFTP; no FlClash',original_sources_retained=True)
    (OUT/'BACKUP_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    s.put(str(OUT/'BACKUP_RECEIPT.json'),WORK+'/BACKUP_RECEIPT.json');s.close();c.close()
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':main()
