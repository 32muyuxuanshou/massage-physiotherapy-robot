"""Selectively extract and decode the precommitted V2 TRAIN_NEW/VAL_NEW workset."""
import argparse, json, os, shutil, subprocess, tempfile
from pathlib import Path

ARCHIVES = Path('/raid5/xuhd/datasets/humman/archives')
WORKSET = Path('/raid5/xuhd/public_rgbd_single_vs_multiview_v2/workset_nonsealed_v1')
SEVEN_ZIP = Path('/raid5/xuhd/MRC/dataset/tools/7zip/7zz')

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--plan',required=True); ap.add_argument('--report',required=True); a=ap.parse_args()
    plan=read(a.plan)
    assert plan['sealed_or_reserve_pixels_selected'] is False
    excluded=set(plan['v2_sealed_subjects_excluded'])|set(plan['final_reserve_subjects_excluded'])
    assert not ({r['subject'] for r in plan['observations']} & excluded)
    assert all(r['split'] in ('TRAIN_NEW','VAL_NEW') for r in plan['observations'])
    WORKSET.mkdir(parents=True,exist_ok=True)
    report={'status':'RUNNING','plan':str(Path(a.plan).resolve()),'archives':[],'views':[],
            'sealed_or_reserve_pixels_materialized':False,'free_bytes_before':shutil.disk_usage(WORKSET).free}
    write(a.report,report)
    env=dict(os.environ); env['LD_LIBRARY_PATH']='/raid5/xuhd/miniconda3/lib'
    for ar in plan['archives']:
        missing=[m for m in ar['members'] if not (WORKSET/m).exists()]
        if missing:
            with tempfile.NamedTemporaryFile('w',encoding='utf8',delete=False,dir=Path(a.report).parent,suffix='.txt') as f:
                f.write('\n'.join(missing)+'\n'); listfile=f.name
            try:
                subprocess.run([str(SEVEN_ZIP),'x',str(ARCHIVES/ar['file']),f'-o{WORKSET}','-y','-scsUTF-8',f'@{listfile}'],check=True,env=env)
            finally: Path(listfile).unlink(missing_ok=True)
        absent=[m for m in ar['members'] if not (WORKSET/m).is_file()]
        if absent: raise RuntimeError(f'missing after extraction {ar["file"]}: {absent[:3]}')
        report['archives'].append({'file':ar['file'],'planned_sha256':ar['sha256'],'selected_files':len(ar['members']),'newly_extracted':len(missing)})
        write(a.report,report); print('EXTRACTED',ar['file'],len(missing),flush=True)
    import cv2, numpy as np
    for row in plan['observations']:
        for cam in row['camera_candidates']:
            cap=cv2.VideoCapture(str(WORKSET/row['sequence']/'kinect_color'/f'{cam}.mp4')); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for frame in row['frame_ids']:
                cap.set(cv2.CAP_PROP_POS_FRAMES,frame); ok,rgb=cap.read()
                depth=cv2.imread(str(WORKSET/row['sequence']/'kinect_depth'/cam/f'{frame:06d}.png'),cv2.IMREAD_UNCHANGED)
                mask=cv2.imread(str(WORKSET/row['sequence']/'kinect_mask'/cam/f'{frame:06d}.png'),cv2.IMREAD_UNCHANGED)
                if not ok or depth is None or mask is None or not np.any(depth) or not np.any(mask): raise RuntimeError((row['sequence'],cam,frame))
                target=WORKSET/row['sequence']/'selected_rgb'/cam/f'{frame:06d}.png'; target.parent.mkdir(parents=True,exist_ok=True)
                if not cv2.imwrite(str(target),rgb): raise RuntimeError(target)
                report['views'].append({'subject':row['subject'],'sequence':row['sequence'],'split':row['split'],'camera':cam,'frame_id':frame,
                    'video_frame_count':count,'exact_frame_decoded':True,'rgb_shape':list(rgb.shape),'depth_shape':list(depth.shape),'mask_shape':list(mask.shape),
                    'depth_dtype':str(depth.dtype),'mask_dtype':str(mask.dtype),'depth_nonzero_fraction':float(np.count_nonzero(depth)/depth.size),'mask_nonzero_fraction':float(np.count_nonzero(mask)/mask.size)})
            cap.release()
        write(a.report,report)
    report['status']='DECODE_AND_FRAME_ID_QA_PASS_GEOMETRY_PENDING'; report['free_bytes_after']=shutil.disk_usage(WORKSET).free
    write(a.report,report); print('COMPLETE',len(report['views']),flush=True)
if __name__=='__main__': main()
