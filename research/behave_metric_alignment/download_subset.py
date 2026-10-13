"""Download frozen BEHAVE members with coalesced direct HTTP ranges and CRC QA."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import struct
import threading
import time
import zlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from remotezip import RemoteZip
from inspect_archive import BASE

local=threading.local()
def session():
    if not hasattr(local,'session'):
        local.session=requests.Session();local.session.trust_env=False
        # The official server actually closed one range connection mid-download.
        # Retry only transport/status failures; CRC/Range mismatches still stop.
        retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=.5,
                    status_forcelist=[429,500,502,503,504],allowed_methods=['GET'])
        local.session.mount('https://',HTTPAdapter(max_retries=retry))
    return local.session

def unpack_member(blob, start, info):
    offset=info['offset']-start
    header=struct.unpack_from('<4s5H3I2H',blob,offset)
    if header[0]!=b'PK\x03\x04' or header[2]&1:
        raise ValueError('Invalid or encrypted ZIP local member')
    data_start=offset+30+header[-2]+header[-1]
    compressed=blob[data_start:data_start+info['compressed']]
    if info['method']==8:data=zlib.decompress(compressed,-15)
    elif info['method']==0:data=compressed
    else:raise ValueError('Unsupported actual source ZIP compression')
    if len(data)!=info['size'] or zlib.crc32(data)&0xffffffff!=info['crc32']:
        raise ValueError('ZIP member size/CRC mismatch: '+info['name'])
    return data

def fetch_group(url, archive_bytes, infos, targets):
    if all(p.exists() and p.stat().st_size==i['size'] for i,p in zip(infos,targets)):
        # Re-open completed files and verify their original archive CRC before resuming.
        data=[p.read_bytes() for p in targets]
        if all(zlib.crc32(b)&0xffffffff==i['crc32'] for i,b in zip(infos,data)):
            return {'network_bytes':0,'files':[{'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for p,b in zip(targets,data)]}
    start=min(i['offset'] for i in infos)
    end=min(archive_bytes-1,max(i['offset']+30+131070+i['compressed'] for i in infos))
    r=session().get(url,headers={'Range':f'bytes={start}-{end}'},timeout=(20,90))
    r.raise_for_status()
    if r.status_code!=206 or len(r.content)!=end-start+1:
        raise ValueError('Server did not honor exact HTTP Range')
    files=[]
    for i,p in zip(infos,targets):
        data=unpack_member(r.content,start,i);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        files.append({'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'archive_member':i['name'],'crc32':i['crc32']})
    return {'network_bytes':len(r.content),'files':files}

def archive_size(url):
    with session().get(url,headers={'Range':'bytes=0-0'},stream=True,timeout=(15,45)) as r:
        if r.status_code!=206:raise ValueError('Range unavailable')
        return int(r.headers['Content-Range'].split('/')[-1])

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--qa-assets-only',action='store_true',help='Fetch only metadata/calibration early, without touching the frozen frame selection')
    a=p.parse_args();manifest=json.loads((a.data/'FROZEN_INPUT_MANIFEST.json').read_text())
    inventory=json.loads((a.data/'DATE03_ARCHIVE_INDEX.json').read_text());index={x['name']:x for x in inventory}
    url=manifest['source'];size=archive_size(url)
    # Sequence metadata is fetched independently and retains its original bytes.
    info_names=sorted({r['archive_frame_prefix'].rsplit('/',2)[0]+'/info.json' for r in manifest['rows']})
    groups=[]
    for r in manifest['rows']:
        names=r['members'];targets=[a.data/'sequences'/r['sequence']/r['frame']/n[len(r['archive_frame_prefix']):] for n in names]
        if not a.qa_assets_only:groups.append((url,size,[index[n] for n in names],targets))
    for name in info_names:
        sequence=next(s for s in manifest['rows'] if s['sequence']+'/' in name)['sequence']
        groups.append((url,size,[index[name]],[a.data/'sequences'/sequence/'info.json']))
    calib_url=BASE+'calibs.zip';calib_size=archive_size(calib_url)
    with RemoteZip(calib_url,session=session(),timeout=60) as archive:
        selected=[i for i in archive.infolist() if not i.is_dir() and
                  (('intrinsics/' in i.filename and (i.filename.endswith('.json') or i.filename.endswith('pointcloud_table.npy'))) or
                   ('Date03/config/' in i.filename and i.filename.endswith('config.json')))]
    for i in selected:
        name=i.filename;relative=name[name.index('intrinsics/'):] if 'intrinsics/' in name else name[name.index('Date03/'):]
        info={'name':name,'size':i.file_size,'compressed':i.compress_size,'offset':i.header_offset,'crc32':i.CRC,'method':i.compress_type}
        groups.append((calib_url,calib_size,[info],[a.data/'calibs'/relative]))
    receipt={'status':'DOWNLOADING_FROZEN_SUBSET','direct_http':True,'started_unix':time.time(),'groups':[],
             'expected_frames':len(manifest['rows']),'expected_groups':len(groups),'calibration_members':len(selected)}
    path=a.data/('QA_ASSETS_DOWNLOAD_RECEIPT.json' if a.qa_assets_only else 'DOWNLOAD_RECEIPT.json')
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(fetch_group,*g) for g in groups]
        for f in as_completed(futures):
            receipt['groups'].append(f.result())
            if len(receipt['groups'])%10==0:
                temp=path.with_suffix('.tmp.json');temp.write_text(json.dumps(receipt,indent=2));temp.replace(path)
                print('DOWNLOADED_GROUPS',len(receipt['groups']),len(groups),flush=True)
    receipt.update(status='COMPLETE_CRC_AND_SHA_VERIFIED',completed_unix=time.time(),
                   network_bytes=sum(g['network_bytes'] for g in receipt['groups']),
                   stored_bytes=sum(f['bytes'] for g in receipt['groups'] for f in g['files']))
    path.write_text(json.dumps(receipt,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k!='groups'},indent=2),flush=True)

if __name__=='__main__':main()
