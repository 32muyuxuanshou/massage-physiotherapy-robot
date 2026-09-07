"""Raster QA from recorded draft observations; does not alter model predictions."""
import csv,json,pathlib
import numpy as np
from PIL import Image,ImageDraw
root=pathlib.Path(__file__).resolve().parent;handoff=root.parent
geometry=json.loads((root/'geometry_audit.json').read_text('utf-8'))
annotations=json.loads((root/'visual_annotations.json').read_text('utf-8'))
colors={'VISIBLE_BACK_CORE':(45,190,90),'CLOTHED':(210,80,190),'HEAD_HAIR':(125,120,220),'ROBOT_OCCLUDED':(235,100,35),'BACKGROUND':(70,145,220)}
point_rows=[];boundary_rows=[];gallery=[]
for frame in geometry['frames']:
    sid=frame['id'];img=Image.open(handoff/f'input/{sid}.png').convert('RGB');w,h=img.size
    ann=annotations['frames'][sid];show=img.copy();paint=ImageDraw.Draw(show)
    masks=[]
    for region in ann['regions']:
        mask=Image.new('L',(w,h));ImageDraw.Draw(mask).polygon([tuple(p) for p in region['polygon']],fill=255)
        edge=Image.new('L',(w,h));ImageDraw.Draw(edge).line([tuple(p) for p in region['polygon']+[region['polygon'][0]]],fill=255,width=annotations['boundary_margin_px']*2+1)
        masks.append((region['label'],np.array(mask)>0,np.array(edge)>0))
        paint.polygon([tuple(p) for p in region['polygon']],fill=colors[region['label']])
    show=Image.blend(img,show,.23);paint=ImageDraw.Draw(show)
    for p in frame['points']:
        x,y=p['xy'];ix,iy=round(x),round(y)
        label='UNKNOWN'
        if not(0<=ix<w and 0<=iy<h):label='OUT_OF_IMAGE'
        else:
            hits=[name for name,m,e in masks if m[iy,ix]]
            near=any(e[iy,ix] for _,_,e in masks)
            if len(hits)==1 and not near:label=hits[0]
        point_rows.append(dict(image_id=sid,point_id=p['point_id'],x_px=x,y_px=y,observation=label,geometry_review_candidate=label=='VISIBLE_BACK_CORE',training_eligible=False,target_reference='UNAVAILABLE',target_error_px=''))
        if 0<=ix<w and 0<=iy<h:
            color=(0,255,90) if label=='VISIBLE_BACK_CORE' else (255,220,0) if label=='UNKNOWN' else (255,65,65)
            paint.ellipse((x-6,y-6,x+6,y+6),fill=color,outline='black',width=2)
            paint.text((x+8,y-12),p['point_id'],fill=color,stroke_width=2,stroke_fill='black')
    # Whole mesh silhouette in the same camera convention. Occluders are not masked away.
    d=np.load(handoff/f'results/{sid}/prediction.npz');camera=d['pred_vertices']+d['pred_cam_t'];uv=camera[:,:2]/camera[:,2:3]*float(d['focal_length'])+[w/2,h/2]
    raster=Image.new('L',(w,h));rd=ImageDraw.Draw(raster)
    for face in d['faces']:
        if np.all(camera[face,2]>0):rd.polygon([tuple(v) for v in uv[face]],fill=255)
    silhouette=np.array(raster)>0
    refview=img.copy();rp=ImageDraw.Draw(refview)
    for ref in ann['contour_refs']:
        x,y=ref['x'],ref['y'];lo,hi=ref['search'];vertical=ref['axis']=='vertical'
        line=silhouette[:,x] if vertical else silhouette[y,:]
        edges=np.flatnonzero(line[1:]!=line[:-1])+1
        edges=edges[(edges>=lo)&(edges<=hi)]
        target=y if vertical else x
        nearest=int(edges[np.argmin(abs(edges-target))]) if len(edges) else None
        deviation=abs(nearest-target) if nearest is not None else None
        uncertainty=ref['uncertainty_px']
        boundary_rows.append(dict(image_id=sid,reference_id=ref['id'],axis=ref['axis'],reference_x=x,reference_y=y,reference_uncertainty_px=uncertainty,predicted_scan_coordinate=nearest,absolute_scan_gap_px=deviation,gap_exceeding_reference_band_px=max(0,deviation-uncertainty) if deviation is not None else None,scope='assistant draft 2D silhouette check, not landmark/acupoint error'))
        px,py=(x,nearest) if vertical else (nearest,y)
        rp.ellipse((x-7,y-7,x+7,y+7),outline=(0,255,70),width=3)
        if nearest is not None:
            rp.line((x,y,px,py),fill=(255,70,40),width=3);rp.ellipse((px-5,py-5,px+5,py+5),fill=(255,70,40))
        rp.text((x+10,y-35),f"{ref['id']} gap={deviation}px +/-{uncertainty}",fill='white',stroke_width=2,stroke_fill='black')
    for picture,title in [(show,f'{sid} DRAFT REGION REVIEW | green=candidate yellow=unknown red=excluded'),(refview,f'{sid} DRAFT CONTOUR REFERENCE | green=observed red=model | NOT POINT ACCURACY')]:
        draw=ImageDraw.Draw(picture);draw.rectangle((0,0,w,45),fill=(20,20,20));draw.text((12,15),title,fill='white')
    show.save(root/f'{sid}_regions.png');refview.save(root/f'{sid}_contour_check.png')
    pair=Image.new('RGB',(1280,360));pair.paste(show.resize((640,360)),(0,0));pair.paste(refview.resize((640,360)),(640,0));gallery.append(pair)
for name,rows in [('point_observations.csv',point_rows),('contour_diagnostics.csv',boundary_rows)]:
    with (root/name).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
overview=Image.new('RGB',(1280,1080))
for i,pair in enumerate(gallery):overview.paste(pair,(0,i*360))
overview.save(root/'review_overview.jpg',quality=94)
from collections import Counter
summary={sid:dict(Counter(r['observation'] for r in point_rows if r['image_id']==sid)) for sid in annotations['frames']}
(root/'observation_summary.json').write_text(json.dumps(dict(status='DRAFT_ASSISTANT_VISUAL_REVIEW',counts=summary,training_labels_approved=0,independent_anatomical_references=0),indent=2)+'\n','utf-8')
print(json.dumps(summary));print(json.dumps(boundary_rows,indent=2))
