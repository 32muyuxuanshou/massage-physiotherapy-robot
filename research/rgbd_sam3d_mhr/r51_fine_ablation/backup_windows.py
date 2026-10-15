"""Eight direct SFTP ranges with actual-byte progress and whole-file SHA."""
import argparse,hashlib,json,os,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import paramiko
OUT=Path('output/r51_fine_supervision_ablation_v1')
REMOTE='/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1'


def connect():
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('172.18.6.218',port=436,username='xuhd',password=os.environ['ROBOT_SSH_PASSWORD'],timeout=25,look_for_keys=False,allow_agent=False)
    c.get_transport().set_keepalive(30);return c


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8388608),b''):h.update(block)
    return h.hexdigest()


def main(scope):
    c=connect();s=c.open_sftp()
    with s.open(REMOTE+'/ARCHIVE_'+scope+'.json') as f:receipt=json.loads(f.read())
    s.close();c.close();target=OUT/Path(receipt['path']).name;size=receipt['bytes']
    if target.exists():assert digest(target)==receipt['sha256'];print('BACKUP_REUSED',scope,flush=True);return
    partial=target.with_suffix(target.suffix+'.partial');progress=OUT/('BACKUP_PROGRESS_'+scope+'.json')
    if progress.exists():
        saved=json.loads(progress.read_text(encoding='utf-8'));assert saved['source']==receipt;counts=saved['counts']
    else:
        with partial.open('wb') as f:f.truncate(size)
        counts=[0]*8
    def worker(i):
        lo,hi=size*i//8,size*(i+1)//8;c=connect();s=c.open_sftp()
        with s.open(receipt['path'],'rb') as source,partial.open('r+b') as dest:
            chunks=[(p,min(1048576,hi-p)) for p in range(lo+counts[i],hi,1048576)]
            for (pos,length),blob in zip(chunks,source.readv(chunks,max_concurrent_prefetch_requests=64)):
                assert len(blob)==length;dest.seek(pos);dest.write(blob);dest.flush();counts[i]+=length
        s.close();c.close()
    def save():
        state=dict(source=receipt,counts=list(counts),downloaded_bytes=sum(counts),total_bytes=size)
        progress.write_text(json.dumps(state,indent=2),encoding='utf-8')
        print('BACKUP_BYTES',scope,state['downloaded_bytes'],size,flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(worker,i) for i in range(8)]
        while not all(f.done() for f in futures):time.sleep(15);save()
        for f in futures:f.result()
    save();actual=digest(partial);assert actual==receipt['sha256'];partial.replace(target)
    result=dict(status='218_WINDOWS_ACTUAL_SHA_MATCH',source=receipt,windows=str(target.resolve()),windows_sha256=actual,transport='Direct SFTP, 8 fixed ranges, no FlClash',source_retained=True)
    path=OUT/('BACKUP_RECEIPT_'+scope+'.json');path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    c=connect();s=c.open_sftp();s.put(str(path),REMOTE+'/'+path.name);s.close();c.close()
    print('BACKUP_COMPLETE',scope,size,actual,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scope',choices=['training','inputs','final'],required=True);main(p.parse_args().scope)
