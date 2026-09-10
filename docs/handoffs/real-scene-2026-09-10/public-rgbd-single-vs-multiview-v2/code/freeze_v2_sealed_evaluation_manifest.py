"""Freeze one deterministic SEALED evaluation ruler for all required comparators."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np

REQUIRED={"OFFICIAL","TRAIN_ONLY_TXYZ","HISTORICAL_V1_E1","V2_WINNER"}
SEED="v2-sealed-fixed-evaluation-points-20260910"
def read(p): return json.loads(Path(p).read_text(encoding="utf8"))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf8")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--winner-freeze',type=Path,required=True); ap.add_argument('--geometry-qa',type=Path,required=True); ap.add_argument('--visual-qa',type=Path,required=True); ap.add_argument('--cache-root',type=Path,required=True); ap.add_argument('--comparators',type=Path,required=True); ap.add_argument('--output-json',type=Path,required=True); ap.add_argument('--output-npz',type=Path,required=True); ap.add_argument('--max-points',type=int,default=25000); a=ap.parse_args()
    from prepare_v2_sealed_after_winner import require_winner
    winner=require_winner(a.winner_freeze); qa=read(a.geometry_qa); visual=read(a.visual_qa); comps=read(a.comparators)
    if qa.get('status')!='AUTO_QA_COMPLETE_VISUAL_REVIEW_PENDING' or qa.get('auto_usable')!=qa.get('observations'): raise RuntimeError('SEALED geometry auto-QA not complete')
    if visual.get('status')!='PASS_GROSS_VISUAL_REGISTRATION_REVIEW': raise RuntimeError('SEALED visual QA not passed')
    if set(comps.get('models',{}))!=REQUIRED: raise RuntimeError('required comparator roster mismatch')
    if comps['models']['V2_WINNER'].get('sha256')!=winner['checkpoint_sha256']: raise RuntimeError('winner comparator mismatch')
    for name,row in comps['models'].items():
        if name=='TRAIN_ONLY_TXYZ':
            if row.get('fit_subject_scope')!='V2_TRAIN_ONLY': raise RuntimeError('Txyz must be V2 TRAIN-only')
        if sha(row['path'])!=row['sha256']: raise RuntimeError(f'{name} hash mismatch')
    arrays={}; rows=[]
    for path in sorted(a.cache_root.glob('*.npz')):
        z=np.load(path,allow_pickle=False); subject=str(z['subject']); sequence=str(z['sequence']); frame=int(z['frame_id'])
        points=z['points_b']; key=f'{subject}_{sequence}_f{frame:06d}'
        seed=int.from_bytes(hashlib.sha256(f'{SEED}:{key}'.encode()).digest()[:8],'big')
        rng=np.random.default_rng(seed); n=min(len(points),a.max_points)
        idx=np.sort(rng.choice(len(points),size=n,replace=False)).astype(np.int32) if n<len(points) else np.arange(len(points),dtype=np.int32)
        arrays[key]=idx
        rows.append({'id':key,'subject_id':subject,'sequence':sequence,'frame_id':frame,'input_camera':'kinect_008',
            'qa_cache_path':str(path.resolve()),
            'qa_cache_sha256':sha(path),'person_points_available':len(points),'evaluation_point_count':len(idx),'index_array_key':key})
    if len({r['subject_id'] for r in rows})!=12 or len(rows)!=36: raise RuntimeError('expected 12 subjects x 3 frames')
    np.savez_compressed(a.output_npz,**arrays)
    manifest={'status':'V2_SEALED_FIXED_EVALUATION_MANIFEST_FROZEN','winner_checkpoint_sha256':winner['checkpoint_sha256'],
      'subject_count':12,'sample_count':36,'input_contract':'dataset ROI + Camera A RGB + Camera A K -> MHR',
        'camera_rule':{'input':'kinect_008','absolute_evaluation':'kinect_009','transform':'predicted Camera-A mesh -> world -> Camera B','kinect_009_not_model_input':True},
      'point_rule':{'source':'registered Camera B person Depth','seed':SEED,'max_points':a.max_points,'replacement':False},
      'metrics':['absolute camera-space surface error','translation-aligned surface error diagnostic only','rendered-depth error','coverage','common-coverage paired error','camera/root outputs','joint output stability'],
      'same_ruler_models':comps['models'],'indices_npz':str(a.output_npz),'indices_npz_sha256':sha(a.output_npz),'rows':rows,
      'final_reserve_opened':False}
    write(a.output_json,manifest)
if __name__=='__main__': main()
