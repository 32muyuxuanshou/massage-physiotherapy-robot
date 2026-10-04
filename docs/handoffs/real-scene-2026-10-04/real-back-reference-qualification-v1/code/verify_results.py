"""Replay every real reference packet from its original cloud and annotation."""
import csv
import numpy as np
from audit_references import ROOT,SOURCE,PREVIOUS,read,write,sha,load_reader,verify_freeze

def main():
    scan={r['scan_id']:r for r in csv.DictReader((PREVIOUS/'SCAN_REFERENCE_BINDING.csv').open())}
    candidates=read(PREVIOUS/'SCAN_REFERENCE_CANDIDATES.json');reader=load_reader();checked=[]
    for row in read(ROOT/'REFERENCE_PACKET_MANIFEST.json'):
        p=ROOT/'reference_packets'/(row['candidate_id']+'.npz');assert sha(p)==row['sha256'];z=np.load(p)
        source=SOURCE/scan[row['scan_id']]['path'];points,_=reader.read_ply(source)
        ann=read(SOURCE/candidates[int(row['candidate_id'].split('_')[1])]['json_path'])
        raw=np.asarray([m['World'] for m in ann['pcMarkers']],float)[:4]
        expected=raw/(1000 if raw.max()>10 else 1)
        np.testing.assert_array_equal(z['markers_m'],expected)
        np.testing.assert_allclose(z['basis'].T@z['basis'],np.eye(3),rtol=0,atol=1e-12)
        assert abs(np.linalg.det(z['basis'])-1)<1e-12
        line=np.asarray(ann['pcLinePts'],float)/1000
        np.testing.assert_array_equal(z['line_m'],line)
        np.testing.assert_allclose(z['line_local_m']@z['basis'].T+z['origin_m'],line,rtol=0,atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(points[z['line_rebound_indices']]-line,axis=1),z['line_to_scan_m'],rtol=0,atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(points[z['marker_rebound_indices']]-expected,axis=1),z['marker_to_scan_m'],rtol=0,atol=1e-12)
        # Independent brute-force marker nearest point check, no KD-tree reuse.
        brute=np.array([np.linalg.norm(points-m,axis=1).min() for m in expected])
        np.testing.assert_allclose(brute,z['marker_to_scan_m'],rtol=0,atol=1e-12)
        checked.append(dict(candidate_id=row['candidate_id'],scan_id=row['scan_id'],status='PASS'))
    visuals=read(ROOT/'VISUALIZATION_MANIFEST.json')
    for row in visuals:assert sha(row['path'])==row['sha256']
    assert len(visuals)==len(checked)
    verified=verify_freeze()
    write(ROOT/'REFERENCE_PACKET_VERIFICATION.json',dict(status='PASS',rows=checked,packet_count=len(checked),
        all_original_sources_reopened=True,marker_bruteforce_nearest_check=True,coordinates_reconstructed=True,
        frozen_files_post_verified=verified,visualizations_verified=len(visuals),medical_validation=False))
    print('REFERENCE_PACKET_VERIFIED',len(checked),'FROZEN',verified,flush=True)

if __name__=='__main__':main()
