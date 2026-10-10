"""Readable previews of actual generated samples (no AI image generation)."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


FONT = 'C:/Windows/Fonts/arial.ttf'


def font(size):
    return ImageFont.truetype(FONT, size)


def rgb_image(path):
    rgba = np.array(Image.open(path).convert('RGBA'))
    a = rgba[..., 3:4]/255
    return Image.fromarray(np.clip(rgba[..., :3]*a+np.array([.12,.15,.19])*255*(1-a),0,255).astype('uint8'))


def make(root, out, plan):
    out.mkdir(parents=True, exist_ok=True)
    assets = plan['assets']
    # All identities appear exactly once, in frozen identity order; no quality ranking.
    selected = []
    for identity in plan['identities']:
        asset = next(a for a in assets if a['identity']==identity['identity'])
        sid = asset['asset_id']+'_c00_l0'
        if (root/'renders'/(sid+'.png')).exists():
            selected.append(sid)
    cols, w, h = 4, 320, 240
    rows = (len(selected)+cols-1)//cols
    sheet = Image.new('RGB',(cols*w,70+rows*(h+45)), 'white')
    draw = ImageDraw.Draw(sheet)
    draw.text((14,10),'R5: photographed HuMMan textures in a virtual studio',fill='black',font=font(24))
    draw.text((14,40),'One frozen source pose / identity; camera 0; lighting 0. No cherry-picking.',fill='#555555',font=font(16))
    for i,sid in enumerate(selected):
        x,y=(i%cols)*w,70+(i//cols)*(h+45)
        sheet.paste(rgb_image(root/'renders'/(sid+'.png')).resize((w,h)),(x,y))
        meta=json.loads((root/'renders'/(sid+'.json')).read_text())
        draw.text((x+8,y+h+4),meta['identity']+' / '+meta['role'],fill='black',font=font(18))
        draw.text((x+8,y+h+24),meta['sequence'].split('_')[-1]+' frame '+meta['frame'],fill='#555555',font=font(15))
    sheet.save(out/'identities.jpg',quality=94)
    # Every preregistered source mesh, one fixed camera/light: complete source-pose coverage.
    mesh_sheet=Image.new('RGB',(4*w,70+12*(h+38)),'white');md=ImageDraw.Draw(mesh_sheet)
    md.text((14,10),'All 48 source meshes: 4 frozen poses per identity',fill='black',font=font(25))
    md.text((14,43),'Rows follow frozen identity order; camera 0, lighting 0. Missing rows are not omitted.',fill='#555555',font=font(16))
    for i,a in enumerate(assets):
        sid=a['asset_id']+'_c00_l0';path=root/'renders'/(sid+'.png')
        x,y=(i%4)*w,70+(i//4)*(h+38)
        if path.exists():mesh_sheet.paste(rgb_image(path).resize((w,h)),(x,y))
        md.text((x+6,y+h+3),a['asset_id'],fill='black',font=font(14))
        md.text((x+6,y+h+20),a['role'],fill='#555555',font=font(13))
    mesh_sheet.save(out/'all_48_source_poses.jpg',quality=94)
    asset=assets[0]
    sheet=Image.new('RGB',(6*w,70+2*(h+32)), 'white');draw=ImageDraw.Draw(sheet)
    draw.text((14,10),'Same scan, 12 calibrated cameras (pose and texture unchanged)',fill='black',font=font(27))
    draw.text((14,44),'First row: elevation 5 deg; second row: 25 deg. Yaw: 0 / 60 / 120 / 180 / 240 / 300.',fill='#555555',font=font(18))
    for camera in plan['cameras']:
        i=camera['camera_id'];sid=asset['asset_id']+f'_c{i:02d}_l0'
        path=root/'renders'/(sid+'.png')
        if not path.exists():continue
        x,y=(i%6)*w,70+(i//6)*(h+32)
        sheet.paste(rgb_image(path).resize((w,h)),(x,y))
        draw.text((x+8,y+h+5),f"C{i:02d}: yaw {camera['yaw_deg']}, f={camera['focal_px']} px",fill='black',font=font(17))
    sheet.save(out/'same_mesh_12_cameras.jpg',quality=94)
    # Fixed first sample of each identity; RGB and metric depth are displayed together.
    available=[sid for sid in selected if (root/'samples'/(sid+'.npz')).exists()]
    sheet=Image.new('RGB',(1280,80+len(available)*260),'white');draw=ImageDraw.Draw(sheet)
    draw.text((14,12),'RGB / clean metric Z / noisy sensor-like Z / valid depth mask',fill='black',font=font(25))
    draw.text((14,45),'Depth colour: Z - per-image median, fixed [-0.6,+0.6] m; blue nearer, red farther.',fill='#555555',font=font(18))
    for i,sid in enumerate(available):
        a=np.load(root/'samples'/(sid+'.npz'));y=80+i*260;mask=a['mask'];z=a['depth_clean_m'];centre=float(np.median(z[mask]))
        tiles=[a['rgb']]
        for key in ['depth_clean_m','depth_m']:
            d=a[key];valid=d>0
            colour=cv2.applyColorMap(np.clip((d-centre+.6)/1.2*255,0,255).astype('uint8'),cv2.COLORMAP_TURBO)[...,::-1]
            colour[~valid]=[245,245,245];tiles.append(colour)
        valid=a['depth_m']>0;tiles.append(np.repeat(np.where(valid,255,0).astype('uint8')[...,None],3,axis=2))
        for j,tile in enumerate(tiles):sheet.paste(Image.fromarray(tile).resize((320,240)),(j*320,y))
        draw.text((8,y+242),f"{sid.split('_')[0]}: median Z={centre:.3f} m",fill='black',font=font(15))
    sheet.save(out/'rgb_depth_masks.jpg',quality=93)
    print('PREVIEWS',len(selected),'identities',len(available),'RGB-D rows',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);a=p.parse_args()
    make(a.root,a.out,json.loads(a.plan.read_text()))
