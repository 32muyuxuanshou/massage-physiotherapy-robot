"""Three predeclared worst-review cases: sensor support versus fitted reference, no filtering."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import cv2


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    config=json.loads((root/'reports/EXPERIMENT_CONFIG.json').read_text());sys.path.insert(0,config['r41_code'])
    from run_r41_txyz import dependencies
    distance=dependencies(Path(config['r41_code']))['distance']
    cases={('Date03_Sub03_chairwood_lift','t0027.000'),('Date03_Sub04_basketball','t0027.000'),('Date03_Sub05_tablesmall','t0068.000')}
    rows=[]
    for row in json.loads((root/'inputs/INPUT_MANIFEST.json').read_text())['records']:
        if (row['sequence'],row['frame']) not in cases:continue
        inp=np.load(row['input_file']);ref=np.load(row['reference_file']);held=np.load(row['heldout_file'])
        for k in [1,2,3]:
            v=(ref['vertices_camera_m']@inp['K0_R'].T+inp['K0_t']-held[f'K{k}_t'])@held[f'K{k}_R']
            points=held[f'K{k}_points_m'];d=distance(points,v,ref['faces'])*1000
            indices=held[f'K{k}_source_pixel_indices'];depth=cv2.imread(str(root/'data/sequences'/row['sequence']/row['frame']/f'k{k}.depth.png'),cv2.IMREAD_UNCHANGED)
            bad=d>500;worst=np.argsort(d)[-10:][::-1]
            rows.append(dict(sequence=row['sequence'],frame=row['frame'],camera=f'K{k}',points=len(d),
                fitted_reference_to_sensor_median_mm=float(np.median(d)),p95_mm=float(np.percentile(d,95)),
                p99_mm=float(np.percentile(d,99)),max_mm=float(d.max()),above500mm_count=int(bad.sum()),
                measured_z_range_m=[float(points[:,2].min()),float(points[:,2].max())],
                fitted_z_range_m=[float(v[:,2].min()),float(v[:,2].max())],
                worst_source_pixels=[dict(flat_index=int(indices[i]),original_depth_mm=int(depth.ravel()[indices[i]]),
                                         distance_mm=float(d[i])) for i in worst]))
    report=dict(status='DIAGNOSTIC_ONLY',records=rows,selection='Same worst Full seed11 Best P95 frame per subject as private review, disclosed posthoc diagnostic',
                points_removed=0,primary_scores_changed=False,interpretation='Large disagreement also present against fitted reference flags support/occlusion/measurement ambiguity; not a proof of which individual source point is invalid.')
    (root/'reports/WORST_REFERENCE_SUPPORT_AUDIT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps([r for r in rows if r['camera']=='K3'],indent=2),flush=True)


if __name__=='__main__':main()
