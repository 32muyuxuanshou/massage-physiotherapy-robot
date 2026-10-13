"""Predeclared aggregation; no checkpoint or frame selection from outcomes."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import numpy as np

def equal_group(rows,key):
    grouped=defaultdict(list)
    for r in rows:grouped[r[key]].append(r)
    return {g:{k:float(np.mean([r['metrics'][k] for r in values])) for k in values[0]['metrics']} for g,values in grouped.items()}

def aggregate(rows):
    rr=[dict(r,metrics={**{k:r['pve'][k] for k in ['pve_absolute_mm','pve_centroid_centered_mm','pa_pve_similarity_mm']},
                           **{'surface_'+k:v for k,v in r['frame_surface_camera_equal_mean'].items()}}) for r in rows]
    sequence=equal_group(rr,'sequence')
    seqrows=[{'sequence':seq,'subject':seq.split('_')[1],'metrics':m} for seq,m in sequence.items()]
    subject=equal_group(seqrows,'subject')
    return {'frames':len(rr),'sequences':len(sequence),'subjects':len(subject),
            'frame_equal_mean':{k:float(np.mean([r['metrics'][k] for r in rr])) for k in rr[0]['metrics']},
            'sequence_then_subject_equal_mean':{k:float(np.mean([r[k] for r in subject.values()])) for k in next(iter(subject.values()))},
            'per_sequence':sequence,'per_subject':subject}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();a.root=a.root.resolve();by=defaultdict(list)
    for path in sorted((a.root/'evaluation').glob('*/RESULTS.json')):
        report=json.loads(path.read_text())
        if report['status']!='EVALUATION_COMPLETE':raise ValueError('Incomplete evaluation')
        for row in report['records']:by[row['cell']].append(row)
    expected=json.loads((a.root/'inputs/INPUT_MANIFEST.json').read_text())['records'];keys={(r['sequence'],r['frame']) for r in expected}
    expected_cells={f'official_s{s}'+tail for s in [11,23,37] for tail in ['','_txyz']}
    expected_cells|={f'{m}_s{s}_{c}' for m in ['rgb_only','g1','coarse','full'] for s in [11,23,37] for c in ['best','last']}
    if set(by)!=expected_cells:raise ValueError('Incomplete actual model/seed/checkpoint coverage')
    reference={(r['seed'],r['sequence'],r['frame']):r for name,rows in by.items() if name.startswith('official_') and not name.endswith('_txyz') for r in rows}
    for name,rows in by.items():
        if name.startswith(('coarse_','full_')) or name.endswith('_txyz'):
            for r in rows:
                original=reference[(r['seed'],r['sequence'],r['frame'])]
                if abs(r['pve']['pve_centroid_centered_mm']-original['pve']['pve_centroid_centered_mm'])>0.001:
                    raise ValueError('Translation-only centered-PVE invariant failed')
    cells={}
    for name,rows in by.items():
        if {(r['sequence'],r['frame']) for r in rows}!=keys or len(rows)!=len(keys):raise ValueError('Unequal actual frame coverage: '+name)
        cells[name]=aggregate(rows)
    out=a.root/'reports';out.mkdir(exist_ok=True)
    grouped=defaultdict(list)
    for name,c in cells.items():
        base,suffix=name.split('_s',1);checkpoint=suffix.split('_',1)[1] if '_' in suffix else 'fixed'
        grouped[base+'_'+checkpoint].append(c['frame_equal_mean'])
    seed_stats={group:{k:{'mean':float(np.mean([r[k] for r in rr])),
                         'std_ddof1':float(np.std([r[k] for r in rr],ddof=1)),'seeds':3} for k in rr[0]} for group,rr in grouped.items()}
    result={'status':'AGGREGATED_FIXED_COHORT','cells':cells,'three_seed_summary':seed_stats,
            'primary':'Absolute corresponding-vertex mean L2, then frame-equal mean',
            'surface_aggregation':'camera summary mean → frame mean within sequence → sequence mean within subject → subject mean',
            'M3_paper_report_only':{'BEHAVE_AMASS_only_PVE_mm':93.1,'BEHAVE_finetuned_PVE_mm':70.9,'exact_protocol_match':False}}
    (out/'AGGREGATED.json').write_text(json.dumps(result,indent=2))
    flat=[]
    for cell,rows in by.items():
        for r in rows:flat.append({'cell':cell,'seed':r['seed'],'subject':r['subject'],'sequence':r['sequence'],'frame':r['frame'],
            **{k:r['pve'][k] for k in ['pve_absolute_mm','pve_centroid_centered_mm','pa_pve_similarity_mm']},
            **{'surface_'+k:v for k,v in r['frame_surface_camera_equal_mean'].items()}})
    with (out/'PER_FRAME.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)

if __name__=='__main__':main()
