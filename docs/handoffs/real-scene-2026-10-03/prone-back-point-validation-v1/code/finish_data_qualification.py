"""Close the actual image review and qualify existing surface-line rebinding.

No new labels, model inference, scale fitting or anatomical truth are created.
"""
import argparse,base64,importlib.util,io
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from run_cached_point_diagnostics import read,write,sha,save_csv


def main(a):
    out=a.root/'p3_data_qualification'
    audit=read(out/'IMAGE_LABEL_IDENTITY_AUDIT.json')
    download=read(a.acquired/'dmd_bak/historical_v1_quality_audit/DOWNLOAD_AUDIT.json')
    reviewed=[];embedded=[]
    for row,item in zip(audit['rows'],download['records']):
        sid=row['sample_id'];image_file,annotation=item['files']
        assert sha(Path(image_file['path']))==row['image_sha256']
        assert sha(Path(annotation['path']))==row['annotation_sha256']
        ann=read(annotation['path'])
        if ann.get('imageData'):
            external=np.asarray(Image.open(image_file['path']).convert('RGB'))
            inner=np.asarray(Image.open(io.BytesIO(base64.b64decode(ann['imageData']))).convert('RGB'))
            same_shape=external.shape==inner.shape
            embedded.append(dict(sample_id=sid,external_shape=list(external.shape),embedded_shape=list(inner.shape),
                mean_absolute_pixel_difference=float(np.abs(external.astype(float)-inner).mean()) if same_shape else None,
                exact_pixel_identity=bool(same_shape and np.array_equal(external,inner)),
                judgement='EXACT_IDENTITY_NOT_ESTABLISHED; unequal pixels can reflect encoding or a different image, not proof of mismatch'))
        reviewed.append(dict(sample_id=sid,image_sha256=row['image_sha256'],annotation_sha256=row['annotation_sha256'],
            visual_review='ALL_35_CONTACT_PAGES_ACTUALLY_VIEWED',
            posture='PRONE_BACK_ON_SUPPORT_CONFIRMED' if sid=='dmd_audit_020' else 'UPRIGHT_OR_PARTIAL_NO_PRONE_EVIDENCE',
            bare_back_visible=True,medical_annotation_review='NOT_CLINICALLY_VERIFIED',
            structural_status=row['geometry_qualification'],calibrated_depth_available=False,
            usable_as_prone_rgb_2d_diagnostic=sid=='dmd_audit_020' and row['geometry_qualification']=='2D_DEVELOPMENT_ONLY'))
    save_csv(out/'DMD_205_VISUAL_QUALIFICATION.csv',reviewed)
    write(out/'DMD_VISUAL_REVIEW.json',dict(status='205_OF_205_VISUALLY_REVIEWED',reviewer='Codex engineering review',
        contact_pages=35,images=205,confirmed_prone_ids=['dmd_audit_020'],
        confirmed_prone_structural_candidates=[r['sample_id'] for r in reviewed if r['usable_as_prone_rgb_2d_diagnostic']],
        reliable_subjects_verified=None,medical_gt_approved=0,rows=reviewed,
        limits=['A horizontal JPEG is not classified as prone without scene evidence','No exact vertebral or acupoint validity determined by visual inspection','Other views include seated, bent and cropped backs; not all called standing']))
    write(out/'DMD_EMBEDDED_PIXEL_DIAGNOSIS.json',embedded)

    source=a.acquired/'pcdare_35f7a1d9'
    spec=importlib.util.spec_from_file_location('reader',a.reader);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    inventory=read(a.acquired/'quality_audit/PCDARE_STRUCTURE_AUDIT.json')
    scans=[x for x in inventory['files'] if not x['derived_output_path']]
    candidates=read(out/'SCAN_REFERENCE_CANDIDATES.json')
    selected=[r for r in candidates if r['indices_in_range_and_length_match']]
    cache={};rebound=[]
    evidence=source/'Asymmetry/E2_StartPCDrawLineApp.m'
    assert 'knnsearch(pc.Location*1000, pcLinePts)' in evidence.read_text()
    for r in selected:
        sid=r['scan_id'];scan=source/scans[int(sid.split('_')[1])]['path'];ann=source/r['json_path']
        if sid not in cache:cache[sid]=mod.read_ply(scan)[0]
        points=cache[sid];line=np.asarray(read(ann)['pcLinePts'],float).reshape(-1,3)
        near,idx=cKDTree(points*1000).query(line)
        # V1 audit used stored indices; official application explicitly rebinds
        # the saved line coordinates to the currently loaded (possibly downsampled) cloud.
        stem=scan.stem
        compatible_name=stem in ann.stem or ann.stem in stem
        rebound.append(dict(**r,scan_sha256=sha(scan),filename_association_hint=compatible_name,
            nearest_max_mm=float(near.max()),nearest_rebound_zero_based_indices=idx.tolist(),
            geometric_rebinding_compatible=bool(near.max()<.01),
            session_identity='UNVERIFIED_NOT_PROMOTED_FROM_NUMERIC_AGREEMENT',
            qualification='SOURCE_LINE_REBINDING_DEVELOPMENT_ONLY_NOT_ANATOMICAL_GT'))
    write(out/'PCDARE_LINE_REBINDING_DIAGNOSIS.json',dict(status='SOURCE_SUPPORTED_REBINDING_DIAGNOSIS',
        source_code=dict(path=str(evidence.relative_to(source)),sha256=sha(evidence),line=58),
        candidate_count=len(candidates),index_range_compatible_candidates=len(selected),rows=rebound,
        compatible_candidates=sum(r['geometric_rebinding_compatible'] for r in rebound),
        independent_session_bindings_verified=0,acupoint_ground_truth_qualified=0,
        limits=['Stale stored indices alone do not disqualify saved surface-line coordinates',
            'Nearest scan association alone does not establish unique session or subject identity',
            'Drawn surface lines and smoothed eslLinePts are not vertebral or acupoint ground truth']))
    print('QUALIFICATION_CLOSED',205,len(rebound),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--acquired',type=Path,required=True)
    p.add_argument('--reader',type=Path,required=True);main(p.parse_args())
