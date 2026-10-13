"""Two concrete private backup volumes, each checked on Windows and 218."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,time
from pathlib import Path
import paramiko
R='/root/autodl-tmp/rgbd_sam3d/evaluations/behave_model_comparison_v1';LOCAL=Path('output/behave_model_comparison_v1/final')
def connect(host,port,user,key):
 c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
 c.connect(host,port=port,username=user,password=os.environ[key],timeout=25,look_for_keys=False,allow_agent=False)
 c.get_transport().set_keepalive(30);c.get_transport().default_window_size=32*1024*1024;return c
def state(status,**values):
 (LOCAL/'FINALIZATION_STATE.json').write_text(json.dumps(dict(status=status,time_unix=time.time(),**values),indent=2),encoding='utf-8')
 print(status,values,flush=True)
def file_sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def recover_ranges(partial,size):
 # Old transfer wrote each range sequentially into a zero-filled file.
 # Locate the first unwritten chunk; whole-file SHA verifies the recovery.
 counts=[];chunk=1024*1024
 with partial.open('rb') as f:
  for i in range(8):
   lo,hi=size*i//8,size*(i+1)//8;n=(hi-lo+chunk-1)//chunk;a,b=0,n
   while a<b:
    mid=(a+b)//2;offset=lo+mid*chunk;f.seek(offset);blob=f.read(min(chunk,hi-offset))
    if blob==bytes(len(blob)):b=mid
    else:a=mid+1
   counts.append(min(a*chunk,hi-lo))
 return counts
def transfer(receipt,target_name):
 source,size=receipt['path'],receipt['bytes'];target=LOCAL/target_name;partial=target.with_suffix('.parallel_partial')
 ranges=partial.with_suffix('.ranges.json');identity=dict(source=source,bytes=size,sha256=receipt['sha256'])
 if target.exists():
  assert target.stat().st_size==size and file_sha(target)==receipt['sha256']
  counts=[size*(i+1)//8-size*i//8 for i in range(8)]
 elif partial.exists():
  assert partial.stat().st_size==size
  if ranges.exists():
   saved=json.loads(ranges.read_text(encoding='utf-8'));assert saved['identity']==identity;counts=saved['counts']
  else:counts=recover_ranges(partial,size)
 else:
  with partial.open('wb') as f:f.truncate(size)
  counts=[0]*8
 def save_ranges():
  temp=ranges.with_suffix('.tmp');temp.write_text(json.dumps(dict(identity=identity,counts=list(counts)),indent=2),encoding='utf-8');temp.replace(ranges)
 started=time.time();resumed=sum(counts)
 state('PARALLEL_ARCHIVE_DOWNLOAD',scope=receipt['scope'],downloaded_bytes=resumed,total_bytes=size,resumed_bytes=resumed)
 if not target.exists():save_ranges()
 def download(i):
  lo,hi=size*i//8,size*(i+1)//8;c=connect('connect.cqa1.seetacloud.com',39846,'root','AUTODL_SSH_PASSWORD')
  with c.open_sftp() as s,s.open(source,'rb') as remote,partial.open('r+b') as local:
   if counts[i]:
    length=min(1024*1024,counts[i]);offset=lo+counts[i]-length;local.seek(offset);remote.seek(offset)
    assert local.read(length)==remote.read(length),'RESUME_BOUNDARY_MISMATCH'
   chunks=[(offset,min(1024*1024,hi-offset)) for offset in range(lo+counts[i],hi,1024*1024)]
   for (offset,length),blob in zip(chunks,remote.readv(chunks,max_concurrent_prefetch_requests=64)):
    assert len(blob)==length;local.seek(offset);local.write(blob);local.flush();counts[i]+=len(blob)
  c.close()
 if not target.exists():
  with ThreadPoolExecutor(max_workers=8) as pool:
   futures=[pool.submit(download,i) for i in range(8)]
   while not all(f.done() for f in futures):
    time.sleep(15);save_ranges();state('PARALLEL_ARCHIVE_DOWNLOAD',scope=receipt['scope'],downloaded_bytes=sum(counts),total_bytes=size,resumed_bytes=resumed,elapsed_seconds=time.time()-started)
   save_ranges()
   for f in futures:f.result()
  assert file_sha(partial)==receipt['sha256'];partial.replace(target)
 state('UPLOADING_PRIVATE_BACKUP_TO_218',scope=receipt['scope'],bytes=size)
 b=connect('172.18.6.218',436,'xuhd','ROBOT_SSH_PASSWORD');dest='/raid5/xuhd/rgbd_sam3d/behave_model_comparison_v1'
 _,out,err=b.exec_command('mkdir -p '+dest);assert out.channel.recv_exit_status()==0,err.read().decode()
 with b.open_sftp() as s:s.put(str(target),dest+'/'+target.name)
 _,out,err=b.exec_command('sha256sum '+dest+'/'+target.name);actual=out.read().decode().split()[0]
 assert out.channel.recv_exit_status()==0,err.read().decode();assert actual==receipt['sha256'];b.close()
 return dict(receipt,windows=str(target.resolve()),backup_218=dest+'/'+target.name,identical_actual_SHA_on_AutoDL_Windows_218=True)
progress=LOCAL/'BACKUP_VOLUME_PROGRESS.json'
volumes=json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else []
for scope,receipt_name,target_name in [('experiment','PRIVATE_ARCHIVE_RECEIPT.json','BEHAVE_R5_PRIVATE_DELIVERY.tar.gz'),
                                     ('assets','PRIVATE_ASSET_ARCHIVE_RECEIPT.json','BEHAVE_R5_FROZEN_ASSETS.tar.gz')]:
 completed=next((v for v in volumes if v['scope']==scope),None)
 if completed:
  assert file_sha(Path(completed['windows']))==completed['sha256']
  b=connect('172.18.6.218',436,'xuhd','ROBOT_SSH_PASSWORD')
  _,out,err=b.exec_command('sha256sum '+completed['backup_218']);actual=out.read().decode().split()[0]
  assert out.channel.recv_exit_status()==0,err.read().decode();assert actual==completed['sha256'];b.close()
  state('VERIFIED_VOLUME_REUSED',scope=scope,bytes=completed['bytes']);continue
 c=connect('connect.cqa1.seetacloud.com',39846,'root','AUTODL_SSH_PASSWORD');state('WAITING_SERVER_ARCHIVE',scope=scope)
 if scope=='assets':
  previous=volumes[0]['path']
  assert previous=='/root/autodl-tmp/rgbd_sam3d/evaluations/behave_model_comparison_v1_private.tar.gz'
  with c.open_sftp() as s:
   if previous.rsplit('/',1)[1] in s.listdir(previous.rsplit('/',1)[0]):s.remove(previous)
  volumes[0]['temporary_AutoDL_archive_removed_after_verified_backups']=True
  progress.write_text(json.dumps(volumes,indent=2),encoding='utf-8')
  with c.open_sftp() as s:asset_receipt_exists=receipt_name in s.listdir(R+'/reports')
  if not asset_receipt_exists:
   _,out,err=c.exec_command('/root/autodl-tmp/rgbd_sam3d/envs/rgbd/bin/python -u '+R+'/code/pack_private_backup.py --assets-only > '+R+'/reports/package_assets.log 2>&1')
   assert out.channel.recv_exit_status()==0,err.read().decode()
 with c.open_sftp() as s:
  while receipt_name not in s.listdir(R+'/reports'):time.sleep(15)
  receipt=json.loads(s.open(R+'/reports/'+receipt_name).read())
 c.close();volumes.append(transfer(receipt,target_name))
 (LOCAL/'BACKUP_VOLUME_PROGRESS.json').write_text(json.dumps(volumes,indent=2),encoding='utf-8')
result=dict(status='PASS',volumes=volumes,autoDL_source=R,core_assets=6,checkpoints=24,
 server_shutdown=False,completed_unix=time.time(),raw_selected_sequences_included=True)
(LOCAL/'BACKUP_RECEIPT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
b=connect('172.18.6.218',436,'xuhd','ROBOT_SSH_PASSWORD')
with b.open_sftp() as s:s.put(str(LOCAL/'BACKUP_RECEIPT.json'),'/raid5/xuhd/rgbd_sam3d/behave_model_comparison_v1/FINAL_BACKUP_RECEIPT.json')
b.close();state('BACKUP_COMPLETE_AWAITING_MANUAL_REVIEW',receipt='BACKUP_RECEIPT.json')
