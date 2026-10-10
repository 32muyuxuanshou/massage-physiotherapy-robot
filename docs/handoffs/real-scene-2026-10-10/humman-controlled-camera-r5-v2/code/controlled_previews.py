"""Complete, portable RGB gallery plus controlled-camera and depth contact sheets."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--plan', type=Path, required=True)
    a = p.parse_args()
    plan = json.loads(a.plan.read_text())
    manifest = json.loads((a.root/'MANIFEST.json').read_text())
    out = a.out
    (out/'rgb').mkdir(parents=True, exist_ok=True)
    (out/'all_assets').mkdir(exist_ok=True)
    font_path = '/usr/share/fonts/dejavu/DejaVuSans.ttf'
    def font(size):
        return ImageFont.truetype(font_path, size)
    rows = manifest['samples']
    indexed = {r['sample_id']:r for r in rows}

    def image(row):
        rgba = np.array(Image.open(a.root/'renders'/(row['sample_id']+'.png')).convert('RGBA'))
        alpha = rgba[...,3:4]/255
        return Image.fromarray(np.clip(rgba[...,:3]*alpha+np.array([.12,.15,.19])*255*(1-alpha),0,255).astype('uint8'))

    def sheet(selected, name, title, cols, width=256):
        height = width*3//4
        stride = height+52
        canvas = Image.new('RGB', (cols*width, 64+((len(selected)+cols-1)//cols)*stride), 'white')
        draw = ImageDraw.Draw(canvas)
        draw.text((12,10), title, font=font(19), fill='black')
        draw.text((12,36),'Unchanged scan/pose/texture; explicit metric cameras. Clipped views retained.',font=font(13),fill='#555555')
        for i,r in enumerate(selected):
            x,y=(i%cols)*width,64+(i//cols)*stride
            canvas.paste(image(r).resize((width,height)),(x,y))
            v=r['view']
            draw.text((x+4,y+height+3),f"C{v['camera_id']:02d}  Z={v['distance_m']:.1f}m  f={v['focal_px']:.0f}px",font=font(14),fill='black')
            draw.text((x+4,y+height+22),f"yaw {v['yaw_deg']}  elev {v['elevation_deg']}  roll {v['roll_deg']}",font=font(12),fill='#333333')
            draw.text((x+4,y+height+37),f"dx {v['offset_x_fraction']:+.2f}  dy {v['offset_y_fraction']:+.2f}  clipped {r['image_truncated']}",font=font(11),fill='#555555')
        canvas.save(out/name,quality=93)

    # Show the fifth frozen source (second identity) for factor sweeps; no metric-based selection.
    demonstration = plan['assets'][4]['asset_id']
    chosen = [r for r in rows if r['asset_id']==demonstration]
    for group in plan['camera_group_counts_per_asset']:
        group_rows=[r for r in chosen if r['view']['group']==group]
        sheet(group_rows, group+'.jpg', 'Camera factor: '+group, min(6,len(group_rows)))
    sheet(chosen,'same_mesh_64_cameras.jpg','One unchanged textured scan / all 64 cameras',8,width=192)

    for asset in plan['assets']:
        selected=[r for r in rows if r['asset_id']==asset['asset_id']]
        sheet(selected,'all_assets/'+asset['asset_id']+'.jpg',asset['asset_id']+' / '+asset['role'],8,width=160)

    # Absolute colour scale is identical in every row; metric Z changes remain visible.
    selected=[r for r in chosen if r['view']['group']=='distance']
    canvas=Image.new('RGB',(1280,70+len(selected)*268),'white');draw=ImageDraw.Draw(canvas)
    draw.text((12,10),'RGB / clean axial Z / noisy axial Z / camera-facing normals',font=font(24),fill='black')
    draw.text((12,42),'Depth uses the same 0.3-4.5 m colour scale in all rows. No per-image normalization.',font=font(17),fill='#555555')
    for i,r in enumerate(selected):
        sample=np.load(a.root/r['file']);tiles=[sample['rgb']]
        for key in ['depth_clean_m','depth_m']:
            depth=sample[key]
            colour=cv2.applyColorMap(np.clip((depth-.3)/4.2*255,0,255).astype('uint8'),cv2.COLORMAP_TURBO)[...,::-1]
            colour[depth<=0]=245;tiles.append(colour)
        normal=np.clip((sample['normals_camera']+1)*127.5,0,255).astype('uint8')
        normal[~sample['mask']]=245;tiles.append(normal)
        y=70+i*268
        for j,tile in enumerate(tiles):canvas.paste(Image.fromarray(tile).resize((320,240)),(j*320,y))
        draw.text((10,y+243),f"C{r['view']['camera_id']:02d} reference Z={r['view']['distance_m']:.1f}m / observed median Z={np.median(sample['depth_clean_m'][sample['mask']]):.3f}m",font=font(16),fill='black')
    canvas.save(out/'rgb_depth_normals.jpg',quality=93)

    gallery=[]
    for i,r in enumerate(rows):
        # A standalone JPEG for every frame; neither NPZ nor Python needed for visual review.
        image(r).save(out/'rgb'/(r['sample_id']+'.jpg'),quality=85)
        gallery.append(dict(id=r['sample_id'],identity=r['identity'],role=r['role'],group=r['view']['group'],
                            view=r['view'],clipped=r['image_truncated']))
        if (i+1)%384==0:print('PREVIEWED',i+1,len(rows),flush=True)
    (out/'GALLERY_MANIFEST.json').write_text(json.dumps(gallery,indent=2))
    data=json.dumps(gallery)
    html='''<!doctype html><meta charset="utf-8"><title>R5 controlled camera RGB-D gallery</title>
<style>body{font:16px sans-serif;background:#edf0f4;color:#17202a;margin:24px}header{position:sticky;top:0;background:#edf0f4;padding:12px}select{font-size:16px;margin-right:12px}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}.card{background:white;padding:8px;border-radius:8px}.card img{width:100%}.card p{font-size:13px;margin:6px 0}</style>
<header><h2>R5: fixed textured bodies, controlled metric cameras</h2><p>Every generated RGB image. Scan surfaces are reconstructed clothing geometry; no native MHR root/body GT.</p><select id="identity"><option value="">All identities</option></select><select id="group"><option value="">All camera groups</option></select><span id="count"></span></header><div id="grid"></div>
<script>const rows=DATA;for(const [id,key] of [['identity','identity'],['group','group']]){const select=document.getElementById(id);for(const val of [...new Set(rows.map(r=>r[key]))]){const op=document.createElement('option');op.value=val;op.textContent=val;select.appendChild(op)}select.onchange=draw}
function draw(){const filtered=rows.filter(r=>(!identity.value||r.identity===identity.value)&&(!group.value||r.group===group.value));count.textContent=filtered.length+' images';grid.innerHTML='';for(const r of filtered){const c=document.createElement('div');c.className='card';const link=document.createElement('a');link.href='rgb/'+r.id+'.jpg';link.target='_blank';const im=document.createElement('img');im.loading='lazy';im.src=link.href;link.appendChild(im);c.appendChild(link);const p=document.createElement('p');p.textContent=r.id+' / '+r.role+' | '+r.group+' | Z '+r.view.distance_m+' m | yaw '+r.view.yaw_deg+' | elev '+r.view.elevation_deg+' | roll '+r.view.roll_deg+' | clipped '+r.clipped;c.appendChild(p);grid.appendChild(c)}}draw();</script>'''
    (out/'index.html').write_text(html.replace('DATA',data),encoding='utf8')
    (out/'PREVIEW_RECEIPT.json').write_text(json.dumps(dict(status='COMPLETE',rgb_images=len(rows),
                                                        all_asset_sheets=len(plan['assets']),
                                                        demonstration_asset=demonstration),indent=2))


if __name__=='__main__':
    main()
