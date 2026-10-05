"""Official public FTP subset, verified against author's SHA512 list."""
import ftplib, hashlib, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path('/raid5/xuhd/datasets/tum_synchronized_anatomy_validation_20261005')

def batch(rows):
    ftp=ftplib.FTP('dataserv.ub.tum.de',timeout=120);ftp.login('m1846795','m1846795')
    base=ftp.pwd();out=[]
    for row in rows:
        dest=ROOT/'raw'/row['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        ftp.cwd(base+'/'+str(Path(row['path']).parent));ftp.voidcmd('TYPE I')
        size=ftp.size(Path(row['path']).name);started=time.time()
        if not (dest.exists() and hashlib.sha512(dest.read_bytes()).hexdigest()==row['sha512']):
            with dest.open('wb') as f:ftp.retrbinary('RETR '+dest.name,f.write,blocksize=1024*1024)
        digest=hashlib.sha512(dest.read_bytes()).hexdigest()
        assert digest==row['sha512'] and dest.stat().st_size==size
        receipt=dict(**row,actual_bytes=size,actual_sha512=digest,seconds=time.time()-started,status='PASS')
        (ROOT/'receipts').mkdir(exist_ok=True)
        key=hashlib.sha256(row['path'].encode()).hexdigest()
        (ROOT/'receipts'/(key+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        print('verified',row['path'],size,flush=True);out.append(receipt)
    ftp.quit();return out

if __name__=='__main__':
    rows=json.loads((ROOT/'DOWNLOAD_SELECTION.json').read_text())['files'];started=time.time()
    # Metadata and source first; big surface geometries last on each stream.
    rows=sorted(rows,key=lambda x:(Path(x['path']).suffix in ['.ply','.stl'],x['path']))
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(batch,[rows[i::4] for i in range(4)]))
    records=[x for group in results for x in group]
    (ROOT/'DOWNLOAD_RESULT.json').write_text(json.dumps(dict(status='PASS',files=len(records),bytes=sum(x['actual_bytes'] for x in records),seconds=time.time()-started,records=records),indent=2)+'\n')
    print('DOWNLOAD_COMPLETE',len(records),flush=True)
