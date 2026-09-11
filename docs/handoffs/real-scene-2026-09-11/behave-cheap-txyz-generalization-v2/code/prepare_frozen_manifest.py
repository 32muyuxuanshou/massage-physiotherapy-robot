"""Create the test manifest without using SAM/Txyz/evaluation results."""
import argparse, hashlib, json
from pathlib import Path

SUBJECT_PLAN={
 3:{'date':'Date03','actions':{'backpack':'backpack_back','stool':'stool_sit','yogaball':'yogaball_play'}},
 4:{'date':'Date03','actions':{'backpack':'backpack_back','stool':'stool_sit','yogaball':'yogaball_play'}},
 5:{'date':'Date03','actions':{'backpack':'backpack','stool':'stool','yogaball':'yogaball'}},
 6:{'date':'Date05','actions':{'backpack':'backpack','stool':'stool','yogaball':'yogaball'}},
 7:{'date':'Date06','actions':{'backpack':'backpack_back','stool':'stool_sit','yogaball':'yogaball_play'}}}
FRACTIONS=[.25,.50,.75]
REQUIRED=[f'k{k}.{x}' for k in range(4) for x in ['color.jpg','depth.png','person_mask.jpg']]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def choose_frames(sequence):
    valid=[]
    for f in sorted(Path(sequence).glob('t*')):
        if not all((f/x).is_file() for x in REQUIRED): continue
        good=True
        for k in range(4):
            import cv2
            mask=cv2.imread(str(f/f'k{k}.person_mask.jpg'),0);depth=cv2.imread(str(f/f'k{k}.depth.png'),-1)
            good &= mask is not None and depth is not None and bool((mask>127).any()) and bool(((mask>127)&(depth>0)).any())
        if good: valid.append(f)
    if len(valid)<3: raise RuntimeError(f'{sequence}: fewer than 3 structurally complete frames')
    ids=[round(q*(len(valid)-1)) for q in FRACTIONS]
    return [valid[i] for i in ids]
def find_action(root,subject,alias):
    plan=SUBJECT_PLAN[subject];seq=Path(root)/f"{plan['date']}_Sub{subject:02d}_{plan['actions'][alias]}"
    if not seq.is_dir():raise RuntimeError(f'Frozen sequence missing: {seq}')
    return seq
def main():
    p=argparse.ArgumentParser();p.add_argument('--sequences',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--fresh-subjects',type=int,nargs='+',default=[3,4,5,6,7]);a=p.parse_args()
    rows=[]
    for subject in a.fresh_subjects:
        for action in ['backpack','stool','yogaball']:
            seq=find_action(a.sequences,subject,action)
            for frame in choose_frames(seq): rows.append({'subject':f'Sub{subject:02d}','fresh':True,'sequence':seq.name,'date':seq.name[:6],'action_label':action,'frame':frame.name,'camera_A':'K0','heldout':['K1','K2','K3'],'selection':'structural completeness + fixed 25/50/75 percent; no model/error inspection'})
    payload={'status':'FROZEN_BEFORE_MODEL_RUN','fresh_only':True,'consumed_smoke_subject':'Sub01','rows':rows,'subjects':len(set(x['subject'] for x in rows)),'sequences':len(set(x['sequence'] for x in rows)),'frames':len(rows),'subject_plan':SUBJECT_PLAN,'selection_contract':{'aliases':['backpack','stool','yogaball'],'fractions':FRACTIONS,'required_files':REQUIRED,'data_qa':'all four masks nonempty and each mask contains valid depth'}}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(payload,indent=2)+'\n');print(sha(a.out),len(rows))
if __name__=='__main__':main()
