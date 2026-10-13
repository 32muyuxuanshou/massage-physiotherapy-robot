"""Six-frame object-mask overlap diagnostic; never filters frozen model/eval points."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from download_subset import fetch_group,archive_size


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    root=a.root.resolve();m=json.loads((root/'data/FROZEN_INPUT_MANIFEST.json').read_text())
    index={x['name']:x for x in json.loads((root/'data/DATE03_ARCHIVE_INDEX.json').read_text())}
    inputs=json.loads((root/'inputs_smoke/INPUT_MANIFEST.json').read_text())['records']
    archive_bytes=archive_size(m['source']);report=[]
    for row,source in zip(inputs,m['rows'][:6]):
        for k in [0,1,2,3]:
            name=source['archive_frame_prefix']+f'k{k}.obj_rend_mask.jpg'
            file=root/'reports/object_support_audit/masks'/source['sequence']/source['frame']/f'k{k}.obj_rend_mask.jpg'
            receipt=fetch_group(m['source'],archive_bytes,[index[name]],[file])
            mask=cv2.imread(str(file),cv2.IMREAD_GRAYSCALE)>127
            pointfile=row['input_file'] if k==0 else row['heldout_file']
            with np.load(pointfile) as z:flat=z[f'K{k}_source_pixel_indices']
            overlap=mask.ravel()[flat]
            report.append(dict(sequence=source['sequence'],frame=source['frame'],camera=f'K{k}',points=len(flat),
                               object_render_mask_overlap_count=int(overlap.sum()),
                               object_render_mask_overlap_ratio=float(overlap.mean()),mask_receipt=receipt['files'][0]))
    out=root/'reports/OBJECT_SUPPORT_SMOKE_AUDIT.json'
    out.write_text(json.dumps(dict(status='DIAGNOSTIC_ONLY',records=report,points_removed=0,model_inputs_changed=False,
        interpretation='Rendered object masks can overlap occluded human projections; overlap is potential object/occlusion support, not a definitive mislabeled-point classification. All benchmark points and scores remain unchanged.'),indent=2))
    print(json.dumps(report[:4],indent=2),flush=True)


if __name__=='__main__':main()
