"""Independent cached-curve replay; no estimator import or fitting."""
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main(root,reference_root):
    predictions=read(root/'PREDICTION_MANIFEST.json')
    packets={r['candidate_id']:r for r in read(reference_root/'REFERENCE_PACKET_MANIFEST.json')}
    scores=list(csv.DictReader((root/'PER_SCAN_RESULTS.csv').open()))
    assert len(scores)==90 and len(predictions)==90
    verified=0
    for cid in packets:
        rows=[r for r in predictions if r['candidate_id']==cid]
        reference=np.load(reference_root/'reference_packets'/(cid+'.npz'))['line_m']
        curves={r['method']:np.load(root/'curves'/Path(r['path']).name) for r in rows if r['status']=='COMPLETE'}
        lo=max(z['query_y_m'].min() for z in curves.values());hi=min(z['query_y_m'].max() for z in curves.values())
        common=(reference[:,1]>=lo)&(reference[:,1]<=hi);target=reference[common]
        for row in rows:
            saved=next(r for r in scores if r['candidate_id']==cid and r['method']==row['method'])
            assert abs(float(saved['common_coverage'])-common.mean())<1e-12
            assert int(saved['common_points'])==len(target)
            if row['status']!='COMPLETE':continue
            p=root/'curves'/Path(row['path']).name;assert sha(p)==row['sha256']
            z=curves[row['method']]
            # Explicit bracketing interpolation independent of evaluator's np.interp.
            ys=z['query_y_m'];right=np.searchsorted(ys,target[:,1],side='right');right=np.clip(right,1,len(ys)-1);left=right-1
            weight=(target[:,1]-ys[left])/(ys[right]-ys[left]);pred=z['curve_m'][left]*(1-weight[:,None])+z['curve_m'][right]*weight[:,None]
            xyz=np.linalg.norm(pred-target,axis=1)*1000;lateral=np.abs(pred[:,0]-target[:,0])*1000
            for key,value in [('median_xyz_mm',np.median(xyz)),('p95_xyz_mm',np.percentile(xyz,95)),('max_xyz_mm',xyz.max()),('median_lateral_mm',np.median(lateral)),('p95_lateral_mm',np.percentile(lateral,95))]:
                assert abs(float(saved[key])-value)<1e-8,(cid,row['method'],key)
            verified+=1
    summary=read(root/'RESULTS.json')
    for method,record in summary['methods'].items():
        values=[float(r['median_xyz_mm']) for r in scores if r['method']==method and r['status']=='COMPLETE']
        assert abs(np.median(values)-record['median_of_scan_median_xyz_mm'])<1e-10
    for row in read(root/'VISUALIZATION_MANIFEST.json'):
        assert sha(root/'figures'/Path(row['path']).name)==row['sha256']
    result=dict(status='PASS',curves_recomputed=verified,score_rows=90,reference_packets=30,
                all_shared_coverage_recomputed=True,independent_interpolation=True,figures_sha256=30)
    (root/'CACHE_REPLAY_VERIFICATION.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--reference-root',type=Path,required=True)
    args=p.parse_args();main(args.root,args.reference_root)
