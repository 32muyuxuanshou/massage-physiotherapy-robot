"""Post-only checks of exported arrays and reports; no original scan required."""
import ast,csv,hashlib,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    packets=read(ROOT/'REFERENCE_PACKET_MANIFEST.json')
    rows=list(csv.DictReader((ROOT/'ALL_CANDIDATES.csv').open(encoding='utf-8-sig')))
    candidates={r['candidate_id']:r for r in rows}
    assert len(rows)==1326 and len(packets)==30
    checked=[]
    for r in packets:
        p=ROOT/'reference_packets'/(r['candidate_id']+'.npz');assert sha(p)==r['sha256'];z=np.load(p)
        assert len(z['markers_m'])==4 and len(z['line_m'])==r['line_points']
        np.testing.assert_allclose(z['line_local_m']@z['basis'].T+z['origin_m'],z['line_m'],rtol=0,atol=1e-12)
        np.testing.assert_allclose(z['basis'].T@z['basis'],np.eye(3),rtol=0,atol=1e-12)
        assert abs(np.linalg.det(z['basis'])-1)<1e-12
        c=candidates[r['candidate_id']]
        assert c['four_reference_packet_candidate']=='True' and c['injected_marker_scan']=='False'
        np.testing.assert_allclose(np.median(z['line_to_scan_m'])*1000,float(c['line_median_mm']),rtol=0,atol=1e-10)
        np.testing.assert_allclose(np.percentile(z['line_to_scan_m'],95)*1000,float(c['line_p95_mm']),rtol=0,atol=1e-10)
        np.testing.assert_allclose(z['marker_to_scan_m'].max()*1000,float(c['first_four_marker_max_mm']),rtol=0,atol=1e-10)
        assert not r['anatomical_accuracy_validated'] and not r['acupoint_gt'] and not r['calibrated_prone_rgbd']
        checked.append(r['candidate_id'])
    visuals=read(ROOT/'VISUALIZATION_MANIFEST.json')
    for r in visuals:assert sha(ROOT/'figures'/Path(r['path']).name)==r['sha256']
    assert len(visuals)==len(checked)==30
    summary=read(ROOT/'QUALIFICATION_RESULTS.json')
    assert summary['geometry_pass_candidates']==sum(r['geometry_pass']=='True' for r in rows)
    assert summary['four_marker_route_candidates']==sum(r['four_reference_packet_candidate']=='True' for r in rows)
    assert summary['unique_reference_packets']==len(packets)
    assert summary['independent_subject_count'] is None
    inputs=read(ROOT/'PRESSUREPOSE_INPUT_AUDIT.json')['rows'];reviewed=read(ROOT/'PRESSUREPOSE_VISUAL_QUALIFICATION.json')['rows']
    assert len(inputs)==len(reviewed)==20
    assert {r['rgb_array_sha256'] for r in inputs}=={r['rgb_array_sha256'] for r in reviewed}
    # The six frozen qualification scripts/protocol must be byte-identical to server freeze.
    frozen={r['sha256'] for r in read(ROOT/'SOURCE_FREEZE_PUBLIC.json')['rows']}
    for name in ['reference_frame.py','test_reference_frame.py','audit_pressurepose.py','audit_references.py','make_reference_figures.py','verify_results.py']:
        assert sha(ROOT/'code'/name) in frozen
    assert sha(ROOT/'PROTOCOL.md') in frozen
    scripts=list((ROOT/'code').glob('*.py'))
    for p in scripts:ast.parse(p.read_text(encoding='utf-8-sig'))
    report=dict(status='PASS',reference_packet_hashes=30,source_figure_hashes=30,candidate_rows=1326,pressurepose_rgb_identities=20,
        exported_coordinates_reconstructed=True,all_counts_match=True,original_scans_reopened_locally=False,
        original_scan_bruteforce_and_frame_replay='server REFERENCE_PACKET_VERIFICATION.json PASS',
        six_initial_scripts_and_protocol_byte_exact=True,python_ast_files=len(scripts),medical_accuracy=False,
        script_sha256=sha(Path(__file__)))
    (ROOT/'PUBLIC_DELIVERY_VERIFICATION.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report))

if __name__=='__main__':main()
