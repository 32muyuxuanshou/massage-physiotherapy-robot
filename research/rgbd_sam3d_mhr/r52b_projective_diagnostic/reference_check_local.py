"""All four unchanged references must reproduce the preceding delivery."""
import argparse,json
from pathlib import Path


def main(root,previous):
    keep={'official_hist6','coarse','fine','hist_plane6'}
    def read(p):
        rows=json.loads((p/'reports/FRAME_RESULTS.json').read_text(encoding='utf-8'))
        return {(r['dataset'],r['seed'],r['key'],r['method']):r for r in rows if r['method'] in keep}
    old,new=read(previous),read(root);assert old.keys()==new.keys()
    maximum=0.;fields=set()
    for k,a in new.items():
        b=old[k]
        for f in ['vertex_camera_mm','vertex_p95_mm','camera_mm','median_mm','p95_mm','coverage_50mm','pve_mm']:
            if f in a:maximum=max(maximum,abs(a[f]-b[f]));fields.add(f)
        assert a['fallback']==b['fallback']
    assert maximum<1e-6,maximum
    (root/'REFERENCE_REPRODUCTION_FULL.json').write_text(json.dumps(dict(status='PASS',records=len(new),maximum_metric_difference=maximum,fields=sorted(fields),references=sorted(keep)),indent=2),encoding='utf-8')
    print('REFERENCE_REPRODUCTION_FULL_PASS',len(new),maximum)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--previous',type=Path,default=Path('output/r52_solver_factor_diagnostic_v1'));a=p.parse_args();main(a.root,a.previous)
