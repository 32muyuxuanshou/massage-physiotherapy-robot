"""Inspect the official archive and freeze a geometry-only test subsample."""
import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter
import requests
from remotezip import RemoteZip

BASE = 'https://datasets.d2.mpi-inf.mpg.de/cvpr22behave/'
REQUIRED = [f'k{k}.{kind}' for k in range(4) for kind in ['color.jpg','depth.png','person_mask.jpg']]
REQUIRED += ['person/fit02/person_fit.ply']

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.trust_env=False
    response=s.get(BASE+'split.json',timeout=45);response.raise_for_status()
    (a.out/'split.json').write_bytes(response.content);split=response.json()
    with RemoteZip(BASE+'Date03.zip',session=s,timeout=60) as archive:
        infos=archive.infolist()
        inventory=[{'name':x.filename,'size':x.file_size,'compressed':x.compress_size,
                    'offset':x.header_offset,'crc32':x.CRC,'method':x.compress_type,'flags':x.flag_bits} for x in infos if not x.is_dir()]
    (a.out/'DATE03_ARCHIVE_INDEX.json').write_text(json.dumps(inventory))
    by_name={x['name']:x for x in inventory};rows=[];coverage=[]
    for sequence in split['test']:
        if not sequence.startswith('Date03_'):
            raise ValueError('Official TEST date changed; review the download contract.')
        prefixes=sorted({x['name'].split(sequence+'/')[0]+sequence+'/' for x in inventory if sequence+'/' in x['name']})
        if len(prefixes)!=1:
            coverage.append({'sequence':sequence,'status':'SEQUENCE_MISSING_OR_AMBIGUOUS','prefixes':prefixes});continue
        prefix=prefixes[0]
        frames=sorted({x['name'][len(prefix):].split('/')[0] for x in inventory if x['name'].startswith(prefix) and x['name'][len(prefix):].startswith('t')})
        valid=[f for f in frames if all(prefix+f+'/'+r in by_name for r in REQUIRED)]
        if not valid:
            coverage.append({'sequence':sequence,'status':'NO_COMPLETE_TIMESTAMPS','total':len(frames)});continue
        indices=sorted({int(q*(len(valid)-1)+.5) for q in [.25,.5,.75]})
        for index in indices:
            frame=valid[index];members=[prefix+frame+'/'+r for r in REQUIRED]
            params=prefix+frame+'/person/fit02/person_fit.pkl'
            if params in by_name:members.append(params)
            rows.append({'sequence':sequence,'subject':sequence.split('_')[1],'date':'Date03',
                         'frame':frame,'role':'OFFICIAL_TEST_SUBSAMPLED_PREVIOUSLY_CONSUMED_IDENTITIES',
                         'members':members,'archive_frame_prefix':prefix+frame+'/',
                         'selection':'sorted structurally complete timestamps, rounded quantiles .25/.5/.75; no model outputs'})
        coverage.append({'sequence':sequence,'status':'COVERED','total_timestamps':len(frames),
                         'complete_timestamps':len(valid),'selected_indices':indices})
    manifest={'status':'FROZEN_BEFORE_NEW_MODEL_INFERENCE','source':BASE+'Date03.zip',
              'split_sha256':hashlib.sha256(response.content).hexdigest(),'camera_input':'K0',
              'heldout':['K1','K2','K3'],'rows':rows,'coverage':coverage,
              'subject_counts':dict(Counter(x['subject'] for x in rows)),
              'download_uncompressed_bytes':sum(by_name[n]['size'] for x in rows for n in x['members'])}
    (a.out/'FROZEN_INPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'frames':len(rows),'sequence_coverage':dict(Counter(x['status'] for x in coverage)),
                      'subject_counts':manifest['subject_counts'],'uncompressed_GB':manifest['download_uncompressed_bytes']/1e9,
                      'first_row':rows[0] if rows else None,'archive_files':len(inventory)},indent=2),flush=True)

if __name__=='__main__':main()
