"""Wait for the verified scan transfer, export spatial inputs, freeze weak loss."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
def main(a):
    r=a.root;c=Path(__file__).parent
    while not (r/'scan_source').exists():time.sleep(20)
    # Transfer extracts only after archive SHA verification. Audit actual source
    # files after the complete extraction, not just a manifest appearing early.
    while True:
        matches=list((r/'scan_source').rglob('MANIFEST.json'))
        if matches:
            assert len(matches)==1
            source=matches[0].parent;manifest=json.loads(matches[0].read_text())
            if all((source/row['file']).exists() for row in manifest['samples']):break
        time.sleep(20)
    for row in manifest['samples']:
        assert hashlib.sha256((source/row['file']).read_bytes()).hexdigest()==row['sha256'],'SOURCE_NPZ_SHA_MISMATCH'
    (r/'SCAN_SOURCE_READY.json').write_text(json.dumps(dict(data_root=str(source),status='SOURCE_HASH_PASS',samples=len(manifest['samples'])),indent=2))
    assert len(manifest['samples'])==3072
    jobs=[]
    for k in range(2):
        log=(r/'logs'/f'scan_cache_{k}.log').open('a')
        command=[sys.executable,str(c/'prepare_scan.py'),'--official-root','/root/autodl-tmp/rgbd_sam3d',
            '--data',str(source),'--out',str(r/'scan_cache'),'--shard',str(k),'--shards','2']
        jobs.append((subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT),log))
    for process,log in jobs:
        rc=process.wait();log.close();assert rc==0,'SCAN_SPATIAL_EXPORT_FAILED'
    subprocess.run([sys.executable,str(c/'compact_scan_cache.py'),'--root',str(r/'scan_cache')],check=True)
    subprocess.run([sys.executable,str(c/'merge_scan.py'),'--root',str(r/'scan_cache')],check=True)
    subprocess.run([sys.executable,str(c/'calibrate_scan.py'),'--paths',str(r/'PATHS.json'),
        '--out',str(r/'SCAN_LOSS_FREEZE.json')],check=True)
    (r/'SCAN_PREPARATION_COMPLETE.json').write_text(json.dumps(dict(status='PASS',samples=3072,TEST_read=False,camera_B_read=False),indent=2))
    print('SCAN_AND_LOSS_READY_FOR_FORMAL',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args())
