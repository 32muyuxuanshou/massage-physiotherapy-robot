"""Compare frozen draft silhouette references; not independent point accuracy."""
import pathlib,json,csv
import numpy as np
from PIL import Image,ImageDraw
r=pathlib.Path(__file__).resolve().parent
refs=json.loads((r.parent/'audit-2026-09-07/visual_annotations.json').read_text('utf-8'))['frames']['S05']['contour_refs']
original=Image.open(r.parent/'input/S05.png').convert('RGB');w,h=original.size
rows=[];panels=[]
for name in ['baseline','mask']:
    d=np.load(r/f'{name}.npz');xyz=d['pred_vertices']+d['pred_cam_t']
    uv=xyz[:,:2]/xyz[:,2:3]*float(d['focal_length'])+[w/2,h/2]
    raster=Image.new('L',(w,h));draw=ImageDraw.Draw(raster)
    for face in d['faces']:
        if np.all(xyz[face,2]>0):draw.polygon([tuple(p) for p in uv[face]],fill=255)
    silhouette=np.array(raster)>0
    panel=Image.open(r/f'{name}.png').convert('RGB');draw=ImageDraw.Draw(panel)
    for ref in refs:
        x,y=ref['x'],ref['y'];line=silhouette[:,x]
        edges=np.flatnonzero(line[1:]!=line[:-1])+1
        lo,hi=ref['search'];edges=edges[(edges>=lo)&(edges<=hi)]
        near=int(edges[np.argmin(abs(edges-y))]) if len(edges) else None
        gap=abs(near-y) if near is not None else None
        rows.append(dict(condition=name,reference=ref['id'],x=x,y=y,predicted_y=near,gap_px=gap,reference_uncertainty_px=ref['uncertainty_px']))
        draw.ellipse((x-8,y-8,x+8,y+8),outline='lime',width=3)
        if near is not None:draw.line((x,y,x,near),fill='red',width=4)
        draw.text((x+12,y-40),f"{ref['id']}: {gap}px",fill='white',stroke_width=2,stroke_fill='black')
    panels.append((name,panel))
panels=[('Original real frame',original),('Draft visible-person mask',Image.open(r/'mask_preview.jpg').convert('RGB'))]+panels
gallery=Image.new('RGB',(1920,1160),(20,20,20));gd=ImageDraw.Draw(gallery)
for i,(title,panel) in enumerate(panels):
    x=(i%2)*960;y=(i//2)*580
    gallery.paste(panel.resize((960,540)),(x,y+40));gd.text((x+12,y+12),title+' | NO independent landmark ground truth',fill='white')
gallery.save(r/'ab_comparison.jpg',quality=94)
with (r/'contour_comparison.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(r/'comparison.json').write_text(json.dumps(dict(references_frozen_before_ab=True,independent_accuracy=False,rows=rows),indent=2)+'\n','utf-8')
print(json.dumps(rows,indent=2))
