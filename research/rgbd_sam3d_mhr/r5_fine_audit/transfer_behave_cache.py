"""Direct SFTP bridge for frozen BEHAVE features; no HTTP or FlClash proxy."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import time
import paramiko

SOURCE='/root/autodl-tmp/rgbd_sam3d/evaluations/behave_model_comparison_v1'
DEST='/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1'
LOCAL=Path('output/r5_fine_negative_update_audit_v1')


def connect(which):
    host,port,user,key=('connect.cqa1.seetacloud.com',39846,'root','AUTODL_SSH_PASSWORD') if which=='source' else ('172.18.6.218',436,'xuhd','ROBOT_SSH_PASSWORD')
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host,port=port,username=user,password=os.environ[key],timeout=25,look_for_keys=False,allow_agent=False)
    c.get_transport().set_keepalive(30);return c


def run():
    LOCAL.mkdir(parents=True,exist_ok=True)
    a=connect('source');b=connect('dest');tasks=[]
    with a.open_sftp() as s:
        for seed in [11,23,37]:
            report=json.loads(s.open(SOURCE+'/cache/s'+str(seed)+'/CACHE_MANIFEST.json').read())
            assert len(report['records'])==270
            for r in report['records']:
                key=r['sequence']+'_'+r['frame']
                tasks.append(dict(seed=seed,key=key,source=r['cache_file'],sha256=r['cache_sha256'],
                    destination=DEST+'/cache/behave/s'+str(seed)+'/'+key+'.pt'))
    cmd='mkdir -p '+' '.join(DEST+'/cache/behave/s'+str(seed) for seed in [11,23,37])
    _,o,e=b.exec_command(cmd);assert o.channel.recv_exit_status()==0,e.read().decode();a.close();b.close()
    completed=[];start=time.monotonic()
    def copy_group(group):
        a=connect('source');b=connect('dest')
        with a.open_sftp() as sf,b.open_sftp() as df:
            for t in group:
                source=t['source'];destination=t['destination'];h=hashlib.sha256();count=0
                size=sf.stat(source).st_size
                with sf.open(source,'rb') as src,df.open(destination+'.partial','wb') as dst:
                    src.prefetch(size,max_concurrent_requests=32);dst.set_pipelined(True)
                    for blob in iter(lambda:src.read(1024*1024),b''):
                        dst.write(blob);h.update(blob);count+=len(blob)
                assert count==size and h.hexdigest()==t['sha256']
                df.rename(destination+'.partial',destination)
                completed.append(dict(t,bytes=count))
                if len(completed)%20==0:
                    (LOCAL/'TRANSFER_PROGRESS.json').write_text(json.dumps(dict(files=len(completed),total=810,
                        bytes=sum(r['bytes'] for r in completed),elapsed_seconds=time.monotonic()-start),indent=2))
                    print('COPIED',len(completed),810,sum(r['bytes'] for r in completed),round(time.monotonic()-start,1),flush=True)
        a.close();b.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(copy_group,tasks[i::4]) for i in range(4)]
        for future in futures:future.result()
    result=dict(status='SOURCE_STREAM_SHA_VERIFIED_AWAITING_DESTINATION_REHASH',records=completed,
                http_proxy_used=False,sealed_TEST_read=False,new_training=False)
    (LOCAL/'BEHAVE_TRANSFER_RECEIPT.json').write_text(json.dumps(result,indent=2))
    b=connect('dest')
    with b.open_sftp() as s:s.put(str(LOCAL/'BEHAVE_TRANSFER_RECEIPT.json'),DEST+'/BEHAVE_TRANSFER_RECEIPT.json')
    b.close();print('BEHAVE_TRANSFER_COMPLETE',len(completed),flush=True)


if __name__=='__main__':run()
