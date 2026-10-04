"""Counts and quality extrema across all consumed-validation cases, cache only."""
import numpy as np
from common import ROOT,CASES,METHODS,read,write,sha

def main():
    x=read(ROOT/'AGGREGATED_RESULTS.json');counts=[];quality=[]
    for case in CASES:
        for method in METHODS[2:]:
            rows=[r for r in x['paired_changes'] if r['role']=='validation_consumed' and r['case']==case and r['method']==method]
            counts.append(dict(case=case,method=method,sources=len(rows),
                surface_improved=sum(r['surface_change_vs_rigid_mm']<0 for r in rows),
                binding_improved=sum(r['known_probe_change_vs_rigid_mm']<0 for r in rows),
                binding_change_median_mm=float(np.median([r['known_probe_change_vs_rigid_mm'] for r in rows]))))
        for method in METHODS:
            rows=[r for r in x['per_source_case'] if r['role']=='validation_consumed' and r['case']==case and r['method']==method]
            quality.append(dict(case=case,method=method,
                any_normal_reversal_sources=sum(r['face_normal_reversal_fraction']>0 for r in rows),
                max_normal_reversal_fraction=max(r['face_normal_reversal_fraction'] for r in rows),
                max_p99_edge_strain=max(r['edge_strain_p99'] for r in rows),
                lowest_ray_hit_fraction=min(r['ray_hit_fraction'] for r in rows)))
    write(ROOT/'PAIRED_COUNT_AUDIT.json',dict(paired_counts=counts,quality=quality,script_sha256=sha(__file__),
        changes='derived counts only; no filtering or new threshold; geometry contract unchanged'))
    print('PAIRED_AND_QUALITY_AUDIT_COMPLETE',len(counts),len(quality),flush=True)

if __name__=='__main__':main()
