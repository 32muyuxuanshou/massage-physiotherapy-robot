"""Export completed derived points, source snapshots, and all visual cases."""
import shutil,zipfile
from pathlib import Path
from common import ROOT,SOURCE,BASE,read,write,sha
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def main():
    assert read(ROOT/'EXECUTION_LEDGER.json')['status']=='COMPLETE';dest=ROOT/'export_public';dest.mkdir(exist_ok=True)
    for p in ROOT.glob('*.json'):copy(p,dest/p.name)
    for p in ROOT.glob('*.csv'):copy(p,dest/p.name)
    copy(ROOT/'PROTOCOL.md',dest/'PROTOCOL.md')
    for folder in ['code','inputs','evaluation_truth','runs','ledger','figures']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:copy(p,dest/folder/p.relative_to(ROOT/folder))
    for p in (BASE/'delivery/code').glob('*.py'):copy(p,dest/'frozen_baseline_code'/p.name)
    rows=[]
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and 'export_public' not in p.parts and p.suffix!='.zip' and '__pycache__' not in p.parts:
            rows.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
    write(dest/'SERVER_OUTPUT_MANIFEST.json',dict(rows=rows,fixed_meshes='source experiment only; unchanged'))
    write(dest/'PUBLIC_DATA_BOUNDARY.json',dict(raw_RGB=False,raw_sensor_depth=False,weights=False,native_MHR_assets=False,
        point_outputs='180 derived 8-point NPZ',reference_inputs='60 four-point oracle/noisy input NPZ',
        point_truth='60 synthetic-reference 8-point NPZ; not measured patient acupoints',
        full_human_mesh_arrays='parent SOURCE/runs, not redistributed',parent_delivery_commit=read(ROOT/'CONTRACT.json')['parent_commit']))
    p=ROOT/'delivery_public.zip'
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(dest.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(dest).as_posix())
    print('EXPORTED',len(rows),'MB',p.stat().st_size/1e6,flush=True)
if __name__=='__main__':main()
