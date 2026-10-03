"""Report all local movement/quality tails; movement is not clinical error."""
import argparse,csv
from collections import Counter
from pathlib import Path
import numpy as np
from run_cached_point_diagnostics import read,write


def main(root):
    out=root/'p1_cached_transfer'
    rows=list(csv.DictReader((out/'PER_POINT_DIAGNOSTICS.csv').open()))
    assert len(rows)==480
    columns=['movement_total_mm','movement_normal_abs_mm','movement_tangent_mm','point_face_normal_angle_deg',
        'rgb_projection_movement_px','local_edge_change_p99','local_area_ratio_median',
        'local_normal_angle_p95_deg','local_normal_reversal_fraction','local_degenerate_faces']
    stats={}
    for key in columns:
        order=sorted(rows,key=lambda r:float(r[key]),reverse=True);v=np.array([float(r[key]) for r in rows])
        stats[key]=dict(min=float(v.min()),median=float(np.median(v)),p95=float(np.percentile(v,95)),max=float(v.max()),
            maximum_case={k:order[0][k] for k in ['subject','seed','point_id',key]})
    failures=read(out/'FAILURE_AND_LIMITATION_RECORDS.json')
    write(out/'ALL_POINT_TAILS_AND_LIMITATIONS.json',dict(status='ALL_480_RIGID_D_PAIRS_REPORTED',stats=stats,
        normal_component_larger_than_tangent_pairs=sum(float(r['movement_normal_abs_mm'])>float(r['movement_tangent_mm']) for r in rows),
        pair_count=len(rows),pairs_with_local_normal_reversal=sum(float(r['local_normal_reversal_fraction'])>0 for r in rows),
        pairs_with_local_degenerate_faces=sum(float(r['local_degenerate_faces'])>0 for r in rows),
        limitation_flags=dict(Counter(v for row in failures for v in row['flags'])),
        caveats=['Quantiles here pool diagnostic pairs, not independent subjects; primary equal-person summary remains SUMMARY.json',
            'Local one-ring checks do not establish global absence of self-intersection',
            'No target ground truth; old atlas semantic labels on HOLD']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
