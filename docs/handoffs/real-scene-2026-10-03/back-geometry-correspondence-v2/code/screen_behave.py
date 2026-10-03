"""Bounded pre-model original-data review. Images stay on the private server."""
import argparse,sys
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageOps
from common import ROOT,OLD,BEHAVE,read,write,sha
sys.path.insert(0,str(OLD/'code'))
from behave_v2_io import read_camera,local_to_world

DATES={'Sub03':'Date03','Sub04':'Date03','Sub05':'Date03','Sub06':'Date05','Sub07':'Date06'}
Q=ROOT/'b_qualification'

def tile(rec,w=350,h=490,grid=False):
    rgb=Image.open(rec['source_files'][0]['path']).convert('RGB')
    box=rec['display_crop_xyxy'];thumb=ImageOps.contain(rgb.crop(box),(w-10,h-55))
    panel=Image.new('RGB',(w,h),'white');panel.paste(thumb,((w-thumb.width)//2,50))
    d=ImageDraw.Draw(panel);d.text((5,5),f"#{rec['candidate_index']:03d} {rec['frame']} K{rec['camera']}",fill='black')
    d.text((5,24),f"{rec['sequence']} / data only",fill='black')
    if grid:
        # Grid coordinates are fractions of the SOURCE crop, not the display canvas.
        left=(w-thumb.width)//2
        for f in [.1,.2,.3,.4,.5,.6,.7,.8,.9]:
            x=left+f*thumb.width;y=50+f*thumb.height
            d.line((x,50,x,50+thumb.height),fill=(230,170,0));d.text((x,50),str(f),fill='black')
            d.line((left,y,left+thumb.width,y),fill=(230,170,0));d.text((left,y),str(f),fill='black')
    return panel

def inventory():
    excluded={(r['sequence'],r['frame']) for r in read(BEHAVE/'v2_3/report/BEHAVE_V2_FROZEN_TEST_MANIFEST.json')['rows']}
    contract=dict(status='FROZEN_BEFORE_MODEL',candidate_budget=300,
        sampling='20 numeric-time uniform quantile positions per each of 15 existing subject/date sequences; exclude old 45 first',
        date_mapping=DATES,target_frames_per_person=6,target_sequences_per_person=2,
        selected_timestamp_min_gap_s=3,subjects_previously_consumed=True,
        qualification='K0 clear posterior patch plus >=1 heldout camera with same patch world NN support',
        patch_half_width_height_crop_fraction=[.06,.05],
        minimum_valid_patch_points=30,same_patch_nn_radius_m=.05,
        minimum_bidirectional_support_fraction=.50,
        planned_development=['Sub03','Sub04'],planned_validation=['Sub05','Sub06','Sub07'],
        model_outputs_used_for_selection=0,all_selected_ROIs_require_original_RGB_visual_review=True,
        purpose='visible clothed posterior surface, not bare-skin/prone/anatomical reference')
    write(Q/'QUALIFICATION_CONTRACT.json',contract)
    frames=[];views=[];idx=0
    for sub,date in DATES.items():
        seqs=sorted((BEHAVE/'data/sequences').glob(f'{date}_{sub}_*'))
        assert len(seqs)==3
        for seq in seqs:
            candidates=sorted([f for f in seq.glob('t*') if f.is_dir() and (seq.name,f.name) not in excluded],key=lambda f:float(f.name[1:]))
            indices=np.unique(np.rint(np.linspace(0,len(candidates)-1,min(20,len(candidates)))).astype(int))
            seqviews=[]
            for j in indices:
                folder=candidates[j];spec=dict(candidate_index=idx,subject=sub,sequence=seq.name,frame=folder.name,previously_consumed=True)
                frames.append(spec)
                for k in range(4):
                    paths=[folder/f'k{k}.{x}' for x in ['color.jpg','depth.png','person_mask.jpg']]
                    mask=cv2.imread(str(paths[2]),0);depth=cv2.imread(str(paths[1]),-1)
                    ys,xs=np.where(mask>127);valid=(mask>127)&(depth>0)
                    box=[max(0,int(xs.min())-30),max(0,int(ys.min())-30),min(mask.shape[1],int(xs.max())+31),min(mask.shape[0],int(ys.max())+31)] if len(xs) else [0,0,mask.shape[1],mask.shape[0]]
                    rec={**spec,'camera':k,'display_crop_xyxy':box,
                        'data_valid':bool(len(xs) and valid.sum()),'valid_person_depth_pixels':int(valid.sum()),
                        'person_mask_pixels':len(xs),'source_files':[dict(path=str(p),sha256=sha(p)) for p in paths]}
                    views.append(rec)
                    if k==0:seqviews.append(rec)
                idx+=1
            page=Image.new('RGB',(5*350,4*490+40),'white');ImageDraw.Draw(page).text((5,5),seq.name+' | original K0; no SAM results',fill='black')
            for j,r in enumerate(seqviews):page.paste(tile(r),(j%5*350,j//5*490+40))
            page.save(Q/'private_images'/(seq.name+'_K0.jpg'),quality=92)
    assert len(frames)<=300 and not any((f['sequence'],f['frame']) in excluded for f in frames)
    write(Q/'CANDIDATE_INVENTORY.json',dict(status='DATA_READ_COMPLETE_VISUAL_QA_PENDING',frames=frames,views=views,
        candidates=len(frames),camera_views=len(views),old_frame_overlap=0,model_runs=0,
        contract_sha256=sha(Q/'QUALIFICATION_CONTRACT.json')))
    print('CANDIDATE_INVENTORY',len(frames),len(views),flush=True)

def review_pages():
    inv=read(Q/'CANDIDATE_INVENTORY.json');codes=read(Q/'K0_VISUAL_REVIEW.json')['rows']
    possible={r['candidate_index'] for r in codes if r['code']=='B'}
    selected=[f for f in inv['frames'] if f['candidate_index'] in possible]
    lookup={(v['candidate_index'],v['camera']):v for v in inv['views']}
    for start in range(0,len(selected),3):
        fs=selected[start:start+3];page=Image.new('RGB',(1600,3*620+40),'white')
        ImageDraw.Draw(page).text((5,5),'K0 clear back candidates: four ORIGINAL cameras, source-crop fractional grid',fill='black')
        for j,f in enumerate(fs):
            for k in range(4):page.paste(tile(lookup[f['candidate_index'],k],400,620,True),(k*400,j*620+40))
        page.save(Q/'private_images'/f'four_camera_{start//3:02d}.jpg',quality=94)
    write(Q/'FOUR_CAMERA_PAGE_INDEX.json',[[f['candidate_index'] for f in selected[s:s+3]] for s in range(0,len(selected),3)])
    print('FOUR_CAMERA_PAGES',len(selected),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['inventory','fourcam'],required=True)
    a=p.parse_args();inventory() if a.phase=='inventory' else review_pages()
