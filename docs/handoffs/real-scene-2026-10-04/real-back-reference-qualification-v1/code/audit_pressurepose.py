"""Read all 20 cached real RGB-D input identities; no marker labels invented."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw,ImageOps
from audit_references import ROOT,write,sha

SOURCE=Path('/raid5/xuhd/datasets/pressurepose_pselect_real_20260928/corrected_comparison_v2/run_v2')
def main():
    subjects=json.loads(Path('/raid5/xuhd/datasets/back_reference_assisted_v1_20261004/CONTRACT.json').read_text())['subjects']
    reviewed={r['subject']:r for r in json.loads((ROOT/'PRESSUREPOSE_VISUAL_QUALIFICATION.json').read_text())['rows']}
    rows=[];images=[]
    for s in subjects:
        p=SOURCE/'inputs'/s/'input.npz';z=np.load(p);identity=json.loads((p.parent/'input_manifest.json').read_text())
        assert sha(p)==identity['input_npz_sha256']
        rgb=z['rgb'];assert hashlib.sha256(np.ascontiguousarray(rgb).tobytes()).hexdigest()==identity['rgb_array_sha256']
        assert reviewed[s]['rgb_array_sha256']==identity['rgb_array_sha256']
        rows.append(dict(subject=s,input_npz_sha256=sha(p),rgb_array_sha256=identity['rgb_array_sha256'],rgb_size=[rgb.shape[1],rgb.shape[0]],
            posterior_rgb_roi_pixels=int(z['posterior_rgb_mask'].sum()),posterior_point_count=int(z['posterior_point_mask'].sum()),
            camera_status=identity['camera_status'],source_type='real_p_select_prone_rgb_plus_filtered_cloud',
            independent_anatomical_landmark_fields=[],medical_reference_qualified=False))
        images.append((s,Image.fromarray(rgb)))
    private=ROOT/'private_review';private.mkdir(exist_ok=True)
    for page,start in enumerate([0,10],1):
        canvas=Image.new('RGB',(1400,1200),'white');d=ImageDraw.Draw(canvas)
        for j,(s,rgb) in enumerate(images[start:start+10]):
            im=ImageOps.contain(rgb,(270,540));x=j%5*280;y=j//5*600
            canvas.paste(im,(x+(280-im.width)//2,y+35));d.text((x+12,y+8),s,fill='black')
        canvas.save(private/f'pressurepose_review_{page}.jpg',quality=95)
    write(ROOT/'PRESSUREPOSE_INPUT_AUDIT.json',dict(status='COMPLETE',rows=rows,input_count=20,independent_reference_count=0,
        limits='Input schema has RGB/depth/cloud/camera/mask, no independent anatomical annotations. Clothing review is recorded separately; no hidden landmark inferred from garment lines.'))
    print('PRESSUREPOSE_INPUT_AUDIT_COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()
