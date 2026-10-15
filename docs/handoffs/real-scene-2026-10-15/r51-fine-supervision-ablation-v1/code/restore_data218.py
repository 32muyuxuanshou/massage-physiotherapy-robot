"""Restore Native from the old archive; Scan is transferred separately."""
import hashlib,json,tarfile,time
from pathlib import Path

BASE=Path('/raid5/xuhd/rgbd_sam3d')
WORK=BASE/'r51_fine_supervision_ablation_v1'


def main():
    manifest=json.loads((WORK/'DATA_MANIFEST.json').read_text());wanted={}
    for domain in ['native']:
        for r in manifest[domain]:wanted[r['cache_file']]=(domain,r)
    old=BASE/'r5_fine_negative_update_audit_v1/cache/native_scale_v2'
    found={};records=[]
    for name,(domain,r) in wanted.items():
        dest=WORK/'cache'/domain/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if domain=='native' and (old/name).exists():
            dest.symlink_to(old/name) if not dest.exists() else None
            found[name]=str(old/name)
    source=BASE/'r5_complete_comparison_v1/assets/SPATIAL_INPUT_BACKUP.tar.gz'
    h=hashlib.sha256()
    with source.open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    assert h.hexdigest()=='85044a00e3d18302198959fae69cd8bcae1a4292a47f129cdfb0f58cae7b18a1'
    print('ARCHIVE_SHA_PASS; need',len(wanted)-len(found),flush=True)
    with tarfile.open(source,'r|gz') as archive:
        for member in archive:
            name=Path(member.name).name
            if name in wanted and name not in found and member.isfile():
                domain,r=wanted[name];dest=WORK/'cache'/domain/name
                h=hashlib.sha256();f=archive.extractfile(member)
                with dest.open('wb') as output:
                    for b in iter(lambda:f.read(4194304),b''):output.write(b);h.update(b)
                found[name]=member.name
                records.append(dict(domain=domain,file=name,archive_member=member.name,sha256=h.hexdigest(),bytes=member.size))
                if len(records)%100==0:print('RESTORED',len(records),len(found),len(wanted),flush=True)
    missing=sorted(set(wanted)-set(found))
    receipt=dict(status='COMPLETE' if not missing else 'MISSING',records=records,source_archive_sha256='85044a00e3d18302198959fae69cd8bcae1a4292a47f129cdfb0f58cae7b18a1',already_verified_native_VAL_symlinks=400,missing=missing,scan='Not in this archive; transfer_scan218.py restores selected Scan caches from AutoDL')
    (WORK/'DATA_RESTORE_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print('RESTORE_END',receipt['status'],'missing',len(missing),flush=True)
    assert not missing,missing[:5]


if __name__=='__main__':main()
