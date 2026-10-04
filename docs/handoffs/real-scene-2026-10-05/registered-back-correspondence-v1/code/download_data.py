"""Acquire the public author-provided FAUST/SCAPE remeshing and vts files on server."""
import hashlib
import json
import time
import zipfile
from pathlib import Path
import requests

ROOT=Path('/raid5/xuhd/datasets/registered_human_correspondence_20261005')
URL='https://nuage.lix.polytechnique.fr/public.php/dav/files/LJFXrsTG22wYCXx/'
FILES={'FAUST_r.zip':19843377,'FAUST_r_vts.zip':2185404,
       'SCAPE_r.zip':14224946,'SCAPE_r_vts.zip':1581854}


def main():
    ROOT.mkdir(parents=True,exist_ok=True);rows=[];start=time.monotonic()
    for name,expected in FILES.items():
        path=ROOT/name
        if not path.exists():
            with requests.get(URL+name,stream=True,timeout=(30,120)) as r:
                r.raise_for_status()
                with path.open('wb') as f:
                    for chunk in r.iter_content(1024*1024):f.write(chunk)
        assert path.stat().st_size==expected
        target=ROOT/('faust' if name.startswith('FAUST') else 'scape')
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                assert (target/member).resolve().is_relative_to(target.resolve())
            z.extractall(target)
            listing=[dict(name=i.filename,bytes=i.file_size) for i in z.infolist()]
        rows.append(dict(name=name,url=URL+name,bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),files=listing))
        print('DOWNLOADED',name,path.stat().st_size,flush=True)
    report=dict(status='COMPLETE',source='GeomFMaps author public derivative, linked by DiffusionNet',
                original_data='FAUST/SCAPE registered real scans; not RGB-D prone or acupoint data',
                license_note='Original dataset research/noncommercial terms retained; no raw data redistributed in Git',
                files=rows,seconds=time.monotonic()-start)
    (ROOT/'DOWNLOAD_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    print('DOWNLOAD_COMPLETE',round(report['seconds'],2),flush=True)


if __name__=='__main__':main()
