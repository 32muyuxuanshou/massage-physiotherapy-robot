"""Explicit RGB-only review of all 180 views; conservative visible back patches.

Not whole-back ROI, not bare skin, not model-derived. Keep all 45 timestamps.
"""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageOps
from run_cached_point_diagnostics import read,write,sha

# Per sequence: three original timestamps, K0/K1/K2/K3.
# B = visible clothed posterior; P = side/ambiguous partial, F = front;
# X = posterior occluded by carried/worn object. Only B has an evaluation patch.
REVIEW={
'Date03_Sub03_backpack_back':['XXFF','XXFF','XXFF'],
'Date03_Sub03_stool_sit':['BFFB','PFFB','FFBP'],
'Date03_Sub03_yogaball_play':['FBBF','FBBF','BPFF'],
'Date03_Sub04_backpack_back':['FXXF','FFXX','FXXF'],
'Date03_Sub04_stool_sit':['PBFF','BPFF','FFPB'],
'Date03_Sub04_yogaball_play':['FBBF','PFPB','PBFX'],
'Date03_Sub05_backpack':['FFBB','FFBB','FPBF'],
'Date03_Sub05_stool':['PFPB','FBPF','FPPB'],
'Date03_Sub05_yogaball':['PBFF','PBFF','BPFF'],
'Date05_Sub06_backpack_back':['XXFF','FXXF','XFFX'],
'Date05_Sub06_stool_sit':['BFFB','BFFP','BPFF'],
'Date05_Sub06_yogaball_play':['BFPB','FFBP','BFFB'],
'Date06_Sub07_backpack_back':['PXPF','PXFX','PFPX'],
'Date06_Sub07_stool_sit':['BFFB','PFFB','PFFB'],
'Date06_Sub07_yogaball_play':['FBBF','FBBF','FBBF'],
}
# Manual centers, in each saved display_crop_xyxy's source-pixel normalized coordinates.
CENTERS={
'Date03_Sub03_stool_sit':{(0,0):(.86,.43),(0,3):(.17,.40),(1,3):(.53,.40),(2,2):(.66,.30)},
'Date03_Sub03_yogaball_play':{(0,1):(.45,.14),(0,2):(.66,.18),(1,1):(.46,.20),(1,2):(.60,.21),(2,0):(.38,.20)},
'Date03_Sub04_stool_sit':{(0,1):(.62,.40),(1,0):(.44,.40),(2,3):(.74,.39)},
'Date03_Sub04_yogaball_play':{(0,1):(.30,.34),(0,2):(.75,.30),(1,3):(.47,.38),(2,1):(.38,.33)},
'Date03_Sub05_backpack':{(0,2):(.44,.19),(0,3):(.48,.25),(1,2):(.43,.26),(1,3):(.59,.24),(2,2):(.51,.31)},
'Date03_Sub05_stool':{(0,3):(.50,.42),(1,1):(.35,.38),(1,2):(.74,.32),(2,3):(.52,.38)},
'Date03_Sub05_yogaball':{(0,1):(.39,.27),(1,1):(.54,.27),(2,0):(.46,.29)},
'Date05_Sub06_stool_sit':{(0,0):(.62,.27),(0,3):(.52,.36),(1,0):(.62,.48),(2,0):(.50,.43)},
'Date05_Sub06_yogaball_play':{(0,0):(.57,.33),(0,3):(.53,.28),(1,2):(.68,.30),(2,0):(.48,.32),(2,3):(.50,.30)},
'Date06_Sub07_stool_sit':{(0,0):(.67,.42),(0,3):(.48,.43),(1,3):(.50,.46),(2,0):(.65,.50),(2,3):(.50,.43)},
'Date06_Sub07_yogaball_play':{(0,1):(.42,.23),(0,2):(.62,.26),(1,1):(.50,.24),(1,2):(.65,.29),(2,1):(.43,.25),(2,2):(.66,.29)},
}


def main(a):
    inventory=read(a.out/'BEHAVE_DATA_COVERAGE_INVENTORY.json');grouped={};rows=[]
    lookup={(r['sequence'],r['frame'],r['camera']):r for r in inventory['rows']}
    frames=read(a.behave_root/'v2_3/report/BEHAVE_V2_FROZEN_TEST_MANIFEST.json')['rows']
    for frame in frames:grouped.setdefault(frame['sequence'],[]).append(frame)
    for seq,seqframes in grouped.items():
        canvas=Image.new('RGB',(1800,1930),'white');draw=ImageDraw.Draw(canvas);draw.text((5,5),seq+' | BLUE: manually reviewed conservative clothed back patch; NO MODEL',fill='black')
        for i,frame in enumerate(seqframes):
            for k,code in enumerate(REVIEW[seq][i]):
                source=lookup[seq,frame['frame'],f'K{k}'];x0,y0,x1,y1=source['display_crop_xyxy'];rgb=Image.open(source['sources'][0]['path']).convert('RGB');mask_path=source['sources'][2]['path'];depth_path=source['sources'][1]['path']
                mask=cv2.imread(mask_path,0);depth=cv2.imread(depth_path,-1);roi=np.zeros(mask.shape,np.uint8);polygon=[]
                if code=='B':
                    cx,cy=CENTERS[seq][i,k];half_x,half_y=.04,.03
                    polygon=[[x0+(cx+dx)*(x1-x0),y0+(cy+dy)*(y1-y0)] for dx,dy in [(-half_x,-half_y),(half_x,-half_y),(half_x,half_y),(-half_x,half_y)]]
                    cv2.fillPoly(roi,[np.rint(polygon).astype(np.int32)],255)
                    visual=np.array(rgb);cv2.polylines(visual,[np.rint(polygon).astype(np.int32)],True,(0,150,255),4);rgb=Image.fromarray(visual)
                valid=(roi>0)&(mask>127)&(depth>0)
                roi_path=a.out/'reference_patches'/seq/frame['frame']/f'K{k}.png';roi_path.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(roi).save(roi_path)
                rows.append(dict(subject=frame['subject'],sequence=seq,frame=frame['frame'],camera=f'K{k}',review_code=code,
                    posterior_visibility={'B':'VISIBLE_CLOTHED_BACK_PATCH','P':'SIDE_OR_PARTIAL_NOT_QUALIFIED','F':'ANTERIOR_VIEW','X':'OBJECT_OCCLUDED_POSTERIOR'}[code],
                    evaluation_qualified=code=='B',roi_polygon_original_rgb_px=polygon,valid_depth_points=int(valid.sum()),
                    roi_path=str(roi_path),roi_sha256=sha(roi_path),source_files=source['sources'],bare_skin=False,prone=False))
                tile=Image.new('RGB',(450,630),'white')
                if a.grid:
                    thumb=rgb.crop((x0,y0,x1,y1)).resize((440,580));grid=ImageDraw.Draw(thumb)
                    for n in range(1,10):
                        grid.line((n*44,0,n*44,580),fill=(255,200,0),width=1);grid.text((n*44+1,2),str(n/10),fill=(0,0,0))
                        grid.line((0,n*58,440,n*58),fill=(255,200,0),width=1);grid.text((1,n*58+1),str(n/10),fill=(0,0,0))
                    tile.paste(thumb,(5,30))
                else:
                    thumb=ImageOps.contain(rgb.crop((x0,y0,x1,y1)),(440,580));tile.paste(thumb,((450-thumb.width)//2,30))
                ImageDraw.Draw(tile).text((5,5),f"{frame['frame']} K{k}: {code} / points {int(valid.sum())}",fill='black');canvas.paste(tile,(k*450,i*630+40))
        canvas.save(a.out/'behave_reference_review'/(seq+('_grid.jpg' if a.grid else '_patches.jpg')),quality=94)
    assert len(rows)==180 and all(r['valid_depth_points']>0 for r in rows if r['evaluation_qualified'])
    write(a.out/'BEHAVE_POSTERIOR_PATCH_ROI_FREEZE.json',dict(status='FROZEN_RGB_ONLY_VISUAL_QA' if a.freeze else 'DRAFT_FOR_RGB_ONLY_VISUAL_QA',
        reviewer='Codex original-RGB inspection; not clinician',reviewed_camera_views=180,
        frozen_before_new_model_runs=True,rectangle_half_extent_normalized=[.04,.03],
        inventory_sha256=sha(a.out/'BEHAVE_DATA_COVERAGE_INVENTORY.json'),rows=rows,
        camera_views=180,qualified_views=sum(r['evaluation_qualified'] for r in rows),
        qualified_heldout_views=sum(r['evaluation_qualified'] and r['camera']!='K0' for r in rows),
        independent_prone_skin_views=0,reference='conservative manually selected clothed posterior patch in original RGB',
        limitations=['Not whole-back coverage','Not prone or bare-skin validation','All subjects previously consumed',
                    'P/F/X kept as missing data; no zero-error replacement or new timestamp selection']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--behave-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--grid',action='store_true');p.add_argument('--freeze',action='store_true');main(p.parse_args())
