"""Full cohort counts, explicit source defects, and every-case visual index."""
import csv
import json
from collections import Counter

from PIL import Image, ImageDraw

from download_ct_subset import ROOT


def main():
    rows=json.loads((ROOT/'ALL_SOURCE_QUALIFICATION.json').read_text())
    summary=dict(cases=len(rows),author_splits=dict(Counter(r['meta']['split'] for r in rows)),
                 label_present_per_level={},unclipped_per_level={},proxy_definition_vertical_median_mm={})
    import numpy as np
    table=[]
    for r in rows:
        for t in r['targets']:
            table.append(dict(subject=r['subject'],author_split=r['meta']['split'],level=t['level'],label_status=t['status'],
                              scanner_boundary_contact=t.get('touches_scanner_boundary'),voxels=t.get('voxels',0),
                              bone_to_skin_mm=t.get('bone_to_skin_posterior_distance_mm'),
                              reference_definition_delta_z_mm=t.get('proxy_definition_vertical_difference_mm')))
    for level in ['C7','T3','T5','T9','L2']:
        values=[t for t in table if t['level']==level and t['label_status']=='CT_SURFACE_PROXY']
        summary['label_present_per_level'][level]=len(values)
        summary['unclipped_per_level'][level]=sum(not t['scanner_boundary_contact'] for t in values)
        summary['proxy_definition_vertical_median_mm'][level]=float(np.median([t['reference_definition_delta_z_mm'] for t in values])) if values else None
    with (ROOT/'SOURCE_QUALIFICATION.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    (ROOT/'SOURCE_SUMMARY.json').write_text(json.dumps(summary,indent=2))
    pages=ROOT/'montages';pages.mkdir(exist_ok=True)
    for start in range(0,len(rows),6):
        page=Image.new('RGB',(1600,1170),'white');draw=ImageDraw.Draw(page)
        draw.text((15,10),'TotalSegmentator CT qualification | every case, no model selection',(0,0,0))
        for i,r in enumerate(rows[start:start+6]):
            im=Image.open(ROOT/'derived'/r['subject']/'CT_SURFACE_REFERENCE.png');im.thumbnail((780,360))
            page.paste(im,(10+(i%2)*800,40+(i//2)*375))
        page.save(pages/(f'qualification_{start//6+1:02}.jpg'),quality=92)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
