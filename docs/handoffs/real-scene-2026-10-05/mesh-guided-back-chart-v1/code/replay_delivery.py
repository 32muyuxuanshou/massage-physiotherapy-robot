"""Recalculate this chart experiment from cached outputs, without torch or fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def span(points):
    return np.max([np.linalg.norm(points[i]-points[j],axis=1)
                   for i,j in [(0,1),(0,2),(1,2)]],axis=0)*1000


def main(root):
    rows=sum([read(root/f'BINDING_MANIFEST_{phase}.json') for phase in ['dev','test']],[])
    cache={}
    for r in rows:
        p=root/'bindings'/Path(r['path']).name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
        cache[r['path']]=dict(np.load(p))
    results=read(root/'RESULTS.json');errors=[]
    keys=['bound_span_median_mm','bound_center_span_median_mm','query_span_median_mm',
          'query_center_span_median_mm','bound_span_max_mm','projection_median_mm','clamped_fraction']
    group_keys=['subject','chart','strategy','mesh_method']
    for r in results['per_model']:
        group=sorted([x for x in rows if all(x[k]==r[k] for k in group_keys+['model_seed'])],key=lambda x:x['split_seed'])
        data=[cache[x['path']] for x in group]
        b=span([x['xyz_m'] for x in data]);q=span([x['query_m'] for x in data])
        values=[np.median(b),np.median(b[1::3]),np.median(q),np.median(q[1::3]),b.max(),
                np.mean([np.median(x['projection_distance_m'])*1000 for x in data]),
                np.mean([x['clamped'].mean() for x in data])]
        errors.extend(abs(float(x)-r[k]) for x,k in zip(values,keys))
    for r in results['per_subject']:
        group=[x for x in results['per_model'] if all(x[k]==r[k] for k in group_keys)]
        errors.extend(abs(float(np.mean([x[k] for x in group]))-r[k]) for k in keys)
    for r in results['aggregate']:
        group=[x for x in results['per_subject'] if all(x[k]==r[k] for k in ['role','chart','strategy','mesh_method'])]
        assert len(group)==r['subjects']
        errors.extend(abs(float(np.median([x[k] for x in group]))-r[k]) for k in keys)
    assert max(errors)<1e-9
    receipt=dict(status='PASS',bindings_reopened=len(cache),metric_checks=len(errors),
                 maximum_difference_mm=max(errors),new_inference=False,mesh_refit=False,
                 scope='Metric consistency only; not anatomical or clinical validation')
    (root/'CACHE_REPLAY_VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
