"""Direct SFTP of selected Scan caches; preserve their actual frozen ZIP bytes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,time
from pathlib import Path
import paramiko

OUT=Path('output/r51_fine_supervision_ablation_v1')
REMOTE='/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1'


def connect(host,port,user,key):
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host,port=port,username=user,password=os.environ[key],timeout=25,look_for_keys=False,allow_agent=False)
    return c


def worker(rows):
    a=connect('connect.cqa1.seetacloud.com',39846,'root','AUTODL_SSH_PASSWORD');b=connect('172.18.6.218',436,'xuhd','ROBOT_SSH_PASSWORD')
    sa=a.open_sftp();sb=b.open_sftp();records=[]
    for row in rows:
        name=row['cache_file'];target=REMOTE+'/cache/scan/'+name
        h=hashlib.sha256();size=0
        with sa.open('/root/autodl-tmp/rgbd_sam3d/runs/r5_complete_comparison_v1/scan_cache/'+name,'rb') as source,sb.open(target+'.partial','wb') as dest:
            source.prefetch()
            for chunk in iter(lambda:source.read(1048576),b''):dest.write(chunk);h.update(chunk);size+=len(chunk)
        assert h.hexdigest()==row['cache_sha256'],name
        sb.rename(target+'.partial',target)
        # Independently read destination bytes, not its stat or the stream digest.
        actual=hashlib.sha256()
        with sb.open(target,'rb') as f:
            f.prefetch()
            for chunk in iter(lambda:f.read(1048576),b''):actual.update(chunk)
        assert actual.hexdigest()==row['cache_sha256'],name
        records.append(dict(file=name,sha256=actual.hexdigest(),bytes=size,role=row['role']))
        if len(records)%50==0:print('SCAN_TRANSFER',len(records),len(rows),flush=True)
    sa.close();sb.close();a.close();b.close();return records


def main():
    rows=json.loads((OUT/'DATA_MANIFEST.json').read_text())['scan'];start=time.monotonic()
    with ThreadPoolExecutor(max_workers=6) as pool:records=sum(pool.map(worker,[rows[i::6] for i in range(6)]),[])
    result=dict(status='COMPLETE_ACTUAL_DESTINATION_SHA_VERIFIED',records=records,count=len(records),bytes=sum(r['bytes'] for r in records),seconds=time.monotonic()-start,transport='Direct SFTP; no FlClash',TEST_read=False)
    (OUT/'SCAN_TRANSFER_RECEIPT.json').write_text(json.dumps(result,indent=2))
    c=connect('172.18.6.218',436,'xuhd','ROBOT_SSH_PASSWORD');s=c.open_sftp();s.put(str(OUT/'SCAN_TRANSFER_RECEIPT.json'),REMOTE+'/SCAN_TRANSFER_RECEIPT.json');s.close();c.close()
    print('SCAN_TRANSFER_COMPLETE',result['count'],result['bytes'],flush=True)


if __name__=='__main__':main()
