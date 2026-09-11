"""Create the test manifest without using SAM/Txyz/evaluation results."""
import argparse, hashlib, json
from pathlib import Path

ACTION_PRIORITY=['backpack_back','stool_sit','yogaball_play']
FRACTIONS=[.25,.50,.75]
REQUIRED=[f'k{k}.{x}' for k in range(4) for x in ['color.jpg','depth.png','person_mask.jpg']]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def choose_frames(sequence):
    valid=[]
    for f in sorted(Path(sequence).glob('t*')):
        if all((f/x).is_file() for x in REQUIRED): valid.append(f)
    if len(valid)<3: raise RuntimeError(f'{sequence}: fewer than 3 structurally complete frames')
    ids=[round(q*(len(valid)-1)) for q in FRACTIONS]
    return [valid[i] for i in ids]
def find_action(root,subject,action):
    hits=sorted(Path(root).glob(f'Date*_Sub{subject:02d}_{action}'))
    if not hits and subject==5:
        hits=sorted(Path(root).glob(f'Date*_Sub05_{action.split("_")[0]}'))
    if len(hits)!=1: raise RuntimeError(f'{subject=} {action=} hits={hits}')
    return hits[0]
def main():
    p=argparse.ArgumentParser();p.add_argument('--sequences',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--fresh-subjects',type=int,nargs='+',default=[3,4,5,6,7]);a=p.parse_args()
    rows=[]
    for subject in a.fresh_subjects:
        for action in ACTION_PRIORITY:
            seq=find_action(a.sequences,subject,action)
            for frame in choose_frames(seq): rows.append({'subject':f'Sub{subject:02d}','fresh':True,'sequence':seq.name,'date':seq.name[:6],'action_label':action,'frame':frame.name,'camera_A':'K0','heldout':['K1','K2','K3'],'selection':'structural completeness + fixed 25/50/75 percent; no model/error inspection'})
    payload={'status':'FROZEN_BEFORE_MODEL_RUN','rows':rows,'subjects':len(set(x['subject'] for x in rows)),'sequences':len(set(x['sequence'] for x in rows)),'frames':len(rows),'selection_contract':{'actions':ACTION_PRIORITY,'fractions':FRACTIONS,'required_files':REQUIRED}}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(payload,indent=2)+'\n');print(sha(a.out),len(rows))
if __name__=='__main__':main()
