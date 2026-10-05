"""Diagnostic of learned chart orientation on all actual patient cache faces.

No point filtering or model selection. Compare chart orientation with the input
reference frame's planar chart on the same nondegenerate faces.
"""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def area(p):
    a=p[:,1]-p[:,0];b=p[:,2]-p[:,0]
    return a[:,0]*b[:,1]-a[:,1]*b[:,0]


def main():
    records=[]
    for path in sorted((ROOT/'patient_paths').glob('*.npz')):
        document=json.loads(path.with_suffix('.json').read_text());span=document['frame']['reference_length_mm']
        with np.load(path) as cache:
            local=cache['local_query'];faces=cache['faces'];field=cache['learned_field']
        base=np.column_stack([local[:,2]*500./span,local[:,0]])
        centers=base[faces].mean(1)
        roi=(centers[:,0]>=-.4)&(centers[:,0]<=1.4)&(abs(centers[:,1]*500)<=150)
        baseline_area=area(base[faces]);learned_area=area(field[faces])
        evaluated=roi&(abs(baseline_area)>1e-12)
        ratio=learned_area[evaluated]/baseline_area[evaluated]
        records.append(dict(subject=document['subject'],ROI_faces=int(roi.sum()),compared_faces=int(evaluated.sum()),
                            baseline_degenerate_faces=int((roi&~evaluated).sum()),
                            chart_orientation_reversed_faces=int((ratio<0).sum()),
                            chart_orientation_reversed_fraction=float(np.mean(ratio<0)),
                            chart_area_ratio_median=float(np.median(ratio)),
                            coordinate_miss_slots=sum(v['coordinate_residual_mm']>1e-5 for v in document['suggestions'].values()),
                            diagnostic_only=True,accuracy_claim=False))
    result=dict(status='TWENTY_CACHE_CHART_DIAGNOSTIC_COMPLETE',records=records,
                subject_median_orientation_reversed_fraction=float(np.median([r['chart_orientation_reversed_fraction'] for r in records])),
                anatomy_labels_used=False,point_filter_or_model_selection=False)
    (ROOT/'checks/CHART_DIAGNOSTIC.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':main()
