"""Read existing real scans and marker candidates without fitting a Mesh."""
import csv,hashlib,importlib.util,json,sys,time
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from reference_frame import reference_frame,local_coordinates,world_coordinates

ROOT=Path('/raid5/xuhd/datasets/real_back_reference_qualification_v1_20261004')
ACQUISITION=Path('/raid5/xuhd/datasets/back_prone_acquisition_20261003')
SOURCE=ACQUISITION/'pcdare_35f7a1d9'
PREVIOUS=Path('/raid5/xuhd/datasets/prone_back_point_validation_20261003/p3_data_qualification')
READER=ACQUISITION/'back-data-acquisition-v1/code/audit_acquired_assets.py'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(x,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def csv_write(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def marker_m(x):
    markers=np.asarray([v['World'] for v in x.get('pcMarkers',[])],float).reshape(-1,3)
    branch='mm_to_m' if markers.size and np.max(markers)>10 else 'already_m'
    return markers/1000 if branch=='mm_to_m' else markers,branch

def load_reader():
    spec=importlib.util.spec_from_file_location('source_ply_reader',READER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def freeze():
    scans=list(csv.DictReader((PREVIOUS/'SCAN_REFERENCE_BINDING.csv').open()))
    candidates=read(PREVIOUS/'SCAN_REFERENCE_CANDIDATES.json')
    assert len(scans)==324 and len(candidates)==1326
    files={str(SOURCE/r['path']):r['sha256'] for r in scans}
    files.update({str(SOURCE/r['json_path']):r['json_sha256'] for r in candidates})
    for p in [READER,PREVIOUS/'SCAN_REFERENCE_BINDING.csv',PREVIOUS/'SCAN_REFERENCE_CANDIDATES.json',
              SOURCE/'README.md',SOURCE/'LICENSE',SOURCE/'StartPCdareRegisterApp.m',
              SOURCE/'XrayRegistration/PcMarkerApp.m',SOURCE/'XrayRegistration/SelectPointFromPc.m',SOURCE/'XrayRegistration/ReadPc.m',
              ROOT/'PROTOCOL.md',*(ROOT/'code').glob('*.py')]:files[str(p)]=sha(p)
    pp=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2/inputs')
    cohort=Path('/raid5/xuhd/datasets/back_reference_assisted_v1_20261004/CONTRACT.json')
    files[str(cohort)]=sha(cohort)
    for s in read(cohort)['subjects']:
        for p in [pp/s/'input.npz',pp/s/'input_manifest.json']:files[str(p)]=sha(p)
    for p in [ROOT/'PRESSUREPOSE_VISUAL_QUALIFICATION.json',ROOT/'ANALYTIC_FRAME_CHECK.json']:
        files[str(p)]=sha(p)
    for p,h in files.items():assert sha(p)==h,p
    write(ROOT/'SOURCE_FREEZE.json',[dict(path=p,sha256=h) for p,h in sorted(files.items())])
    return scans,candidates

def verify_freeze():
    rows=read(ROOT/'SOURCE_FREEZE.json')
    for r in rows:assert sha(r['path'])==r['sha256'],r['path']
    return len(rows)

def main():
    start=time.time();scans,candidates=freeze();reader=load_reader()
    indexed={}
    for i,r in enumerate(candidates):indexed.setdefault(r['scan_id'],[]).append((f'candidate_{i:04d}',r))
    rows=[];scan_rows=[];packets=[];duplicate={}
    for scan in scans:
        p=SOURCE/scan['path'];points,colors=reader.read_ply(p);tree=cKDTree(points)
        family=Path(scan['path']).parts[0];injected='_wmarkers' in p.stem.lower()
        accepted=0
        for cid,candidate in indexed.get(scan['scan_id'],[]):
            ann=read(SOURCE/candidate['json_path']);line=np.asarray(ann['pcLinePts'],float).reshape(-1,3)/1000
            markers,unit=marker_m(ann);line_d,line_idx=tree.query(line);has_markers=len(markers)>=4 and np.isfinite(markers).all()
            marker_d,marker_idx=tree.query(markers) if has_markers else (np.array([]),np.array([],int))
            frame=reference_frame(markers) if has_markers else None
            line_med=float(np.median(line_d)*1000);line_p95=float(np.percentile(line_d,95)*1000)
            marker_max=float(marker_d[:4].max()*1000) if has_markers else None
            reasons=[]
            if not has_markers:reasons.append('NO_FOUR_FINITE_MARKERS')
            if line_med>2 or line_p95>5:reasons.append('LINE_SCAN_GEOMETRY_MISMATCH')
            if has_markers and marker_max>5:reasons.append('MARKER_SCAN_GEOMETRY_MISMATCH')
            if has_markers and frame is None:reasons.append('DEGENERATE_FOUR_MARKER_FRAME')
            geometry_pass=not reasons
            order_supported=len(markers)==4 and family in ['IIR','Balgrist']
            semantic='FOUR_MARKER_SOURCE_ORDER_CANDIDATE' if order_supported else 'M1_TO_MN_ORDER_NOT_PROMOTED'
            qualified=geometry_pass and order_supported and not injected
            key=hashlib.sha256(bytes.fromhex(scan['sha256'])+np.ascontiguousarray(markers[:4]).tobytes()+np.ascontiguousarray(line).tobytes()).hexdigest()
            duplicate_of=duplicate.get(key)
            if qualified and duplicate_of is None:
                duplicate[key]=cid
                body=local_coordinates(line,frame);reconstructed=world_coordinates(body,frame)
                np.testing.assert_allclose(reconstructed,line,rtol=0,atol=1e-12)
                packet_path=ROOT/'reference_packets'/(cid+'.npz');packet_path.parent.mkdir(exist_ok=True)
                np.savez_compressed(packet_path,markers_m=markers[:4],line_m=line,line_rebound_indices=line_idx,
                    marker_rebound_indices=marker_idx[:4],line_to_scan_m=line_d,marker_to_scan_m=marker_d[:4],
                    origin_m=frame['origin_m'],basis=frame['basis'],line_local_m=body,axis_length_m=np.asarray(frame['axis_length_m']))
                packets.append(dict(candidate_id=cid,scan_id=scan['scan_id'],family=family,path=str(packet_path),sha256=sha(packet_path),
                    scan_sha256=scan['sha256'],annotation_sha256=candidate['json_sha256'],line_points=len(line),
                    axis_length_mm=float(frame['axis_length_m']*1000),line_lateral_deviation_median_mm=float(np.median(np.abs(body[:,0]))*1000),
                    line_lateral_deviation_p95_mm=float(np.percentile(np.abs(body[:,0]),95)*1000),
                    coordinate_reconstruction_max_m=float(np.max(np.linalg.norm(reconstructed-line,axis=1))),
                    source_order=['C7_label_candidate','L5_label_candidate','SIPS_image_right_candidate','SIPS_image_left_candidate'],
                    anatomical_accuracy_validated=False,acupoint_gt=False,calibrated_prone_rgbd=False,standalone_scan_only=True))
            if qualified:accepted+=1
            rows.append(dict(candidate_id=cid,scan_id=scan['scan_id'],family=family,scan_sha256=scan['sha256'],annotation_sha256=candidate['json_sha256'],
                marker_count=len(markers),marker_unit_branch=unit,line_median_mm=line_med,line_p95_mm=line_p95,
                first_four_marker_max_mm=marker_max,all_marker_max_mm=float(marker_d.max()*1000) if has_markers else None,
                geometry_pass=geometry_pass,geometry_fail_reasons=';'.join(reasons),source_order_status=semantic,
                injected_marker_scan=injected,four_reference_packet_candidate=qualified,duplicate_packet_of=duplicate_of,
                independent_session_verified=False,anatomical_accuracy_validated=False,acupoint_gt=False))
        scan_rows.append(dict(scan_id=scan['scan_id'],family=family,scan_sha256=scan['sha256'],vertices=len(points),
            color_present=colors is not None,injected_marker_scan=injected,candidates=len(indexed.get(scan['scan_id'],[])),qualified_candidates=accepted))
        if len(scan_rows)%25==0:print('SCANS',len(scan_rows),'CANDIDATES',len(rows),'PACKETS',len(packets),flush=True)
    assert len(rows)==1326
    rows.sort(key=lambda r:r['candidate_id']);packets.sort(key=lambda r:r['candidate_id'])
    csv_write(ROOT/'ALL_CANDIDATES.csv',rows);csv_write(ROOT/'ALL_SCANS.csv',scan_rows)
    write(ROOT/'REFERENCE_PACKET_MANIFEST.json',packets)
    write(ROOT/'QUALIFICATION_RESULTS.json',dict(status='COMPLETE',scans=len(scans),candidate_records=len(rows),
        unique_annotation_files=len({r['annotation_sha256'] for r in rows}),marker_counts=dict(Counter(str(r['marker_count']) for r in rows)),
        geometry_pass_candidates=sum(r['geometry_pass'] for r in rows),four_marker_route_candidates=sum(r['four_reference_packet_candidate'] for r in rows),
        unique_reference_packets=len(packets),packet_scans=len({r['scan_sha256'] for r in packets}),
        independent_subject_count=None,clinical_acupoint_ground_truth=0,calibrated_prone_rgbd_pairs=0,
        limits='Candidate count is not subjects; geometric agreement is not unique session identity or anatomical accuracy; scan markers are selected/injected objects, not validated skin contact targets'))
    verified=verify_freeze();write(ROOT/'POST_EXECUTION_INTEGRITY.json',dict(status='PASS',frozen_source_files=verified,
        source_unchanged=True,new_sam_inferences=0,new_mesh_fits=0,training_runs=0))
    write(ROOT/'EXECUTION_LEDGER.json',dict(status='COMPLETE',scans=324,candidate_rows=1326,reference_packets=len(packets),
        new_sam_inferences=0,new_mesh_fits=0,training_runs=0,seconds=time.time()-start))
    print('AUDIT_COMPLETE',len(rows),len(packets),flush=True)

if __name__=='__main__':main()
