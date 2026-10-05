"""Read only native NIfTI headers; full 77GB CT is not needed for geometry QA."""
import ftplib, json, io, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,'/raid5/xuhd/datasets/ct_back_anatomical_reference_20261005/deps')
import nibabel as nib
ROOT=Path('/raid5/xuhd/datasets/tum_synchronized_anatomy_validation_20261005')
paths=sorted({x['path'].split('/')[2] for x in json.loads((ROOT/'DOWNLOAD_SELECTION.json').read_text())['files'] if '/dataset/' in x['path']})
rows=[]
for subject in paths:
    dest=ROOT/'native_headers'/(subject+'.nii.header');dest.parent.mkdir(exist_ok=True)
    if dest.exists():blocks=dest.read_bytes()
    else:
        ftp=ftplib.FTP('dataserv.ub.tum.de',timeout=60);ftp.login('m1846795','m1846795')
        ftp.cwd('PLOS_repo/dataset/'+subject+'/ct_scan');ftp.voidcmd('TYPE I')
        conn=ftp.transfercmd('RETR ct_scan.nii');blocks=b''
        while len(blocks)<352:blocks+=conn.recv(352-len(blocks))
        conn.close();ftp.close()
    header=nib.Nifti1Header.from_fileobj(io.BytesIO(blocks));affine=header.get_best_affine()
    dest=ROOT/'native_headers'/(subject+'.nii.header');dest.parent.mkdir(exist_ok=True);dest.write_bytes(blocks)
    row=dict(subject=subject,shape=[int(x) for x in header.get_data_shape()],voxel_spacing_mm=[float(x) for x in header.get_zooms()],units=header.get_xyzt_units()[0],affine_ras_mm=affine.tolist(),axes=nib.aff2axcodes(affine),bytes=len(blocks),qform_code=int(header['qform_code']),sform_code=int(header['sform_code']))
    assert row['units'] in ['mm','unknown'];rows.append(row);print(subject,row,flush=True)
(ROOT/'NATIVE_HEADERS.json').write_text(json.dumps(rows,indent=2)+'\n')
