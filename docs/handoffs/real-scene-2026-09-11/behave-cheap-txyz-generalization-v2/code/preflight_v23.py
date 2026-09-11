"""Pure-code V2.2 preflight. Creates only synthetic files in a temporary directory."""
import json, subprocess, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np

from prepare_frozen_manifest import SUBJECT_PLAN, choose_frames, find_action
from preflight_contracts import assert_qa_coverage, classify_outcome, file_sha, source_tree_sha, validate_runner_manifest, verify_assets

def fake_sequence(root, name, frame_count=3):
    sequence=root/name
    for frame_id in range(1,frame_count+1):
        frame=sequence/f"t{frame_id:04d}.000";frame.mkdir(parents=True)
        for camera in range(4):
            cv2.imwrite(str(frame/f"k{camera}.color.jpg"),np.zeros((4,4,3),np.uint8))
            cv2.imwrite(str(frame/f"k{camera}.depth.png"),np.full((4,4),1000,np.uint16))
            cv2.imwrite(str(frame/f"k{camera}.person_mask.jpg"),np.full((4,4),255,np.uint8))
    return sequence

def main():
    with tempfile.TemporaryDirectory(prefix="behave_v22_preflight_") as tmp:
        root=Path(tmp);sequences=root/'sequences';sequences.mkdir()
        for subject,plan in SUBJECT_PLAN.items():
            for action in plan['actions'].values():fake_sequence(sequences,f"{plan['date']}_Sub{subject:02d}_{action}")
        for action in ('backpack_back','stool_sit'):fake_sequence(sequences,f"Date01_Sub01_{action}")
        for subject in SUBJECT_PLAN:
            for alias in ('backpack','stool','yogaball'):assert len(choose_frames(find_action(sequences,subject,alias)))==3
        smoke_path=root/'smoke.json';subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_smoke_manifest.py')),'--sequences',str(sequences),'--out',str(smoke_path)],check=True);validate_runner_manifest(json.loads(smoke_path.read_text()))
        short=fake_sequence(sequences,'Date99_Sub99_short',4)
        try:choose_frames(short);raise AssertionError('duplicate frame indices were accepted')
        except RuntimeError as error:assert 'DATA_INSUFFICIENT_FOR_FROZEN_SAMPLING' in str(error)
        assert classify_outcome([0.,0.,0.],True)=='FALLBACK_OFFICIAL'
        manifest={'status':'FROZEN_BEFORE_MODEL_RUN','rows':[{'sequence':f"{plan['date']}_Sub{subject:02d}_{next(iter(plan['actions'].values()))}"} for subject,plan in SUBJECT_PLAN.items()]}
        qa={'status':'PASS','rows':[]}
        for item in manifest['rows']:
            for target in ('K1','K2','K3'):qa['rows'].append({'sequence':item['sequence'],'target':target,'pass':True})
            qa['rows'].append({'sequence':item['sequence'],'world_person_cloud_overlap':[{'pair':'synthetic'}],'pass':True})
        assert_qa_coverage(manifest,qa)
        broken=json.loads(json.dumps(qa));broken['rows']=[row for row in broken['rows'] if row.get('target')!='K3']
        try:assert_qa_coverage(manifest,broken);raise AssertionError('missing QA was accepted')
        except RuntimeError as error:assert 'CAMERA_QA_COVERAGE_MISSING' in str(error)
        assets=root/'assets';assets.mkdir();paths={}
        for name in ('checkpoint','model_config','mhr','anchors','surface_metrics'):
            paths[name]=assets/name;paths[name].write_text(name)
        sam_repo=assets/'sam';sam_repo.mkdir();(sam_repo/'model.py').write_text('x=1\n');(sam_repo/'model.yaml').write_text('x: 1\n')
        freeze={'assets':{'official_checkpoint':{'sha256':file_sha(paths['checkpoint'])},'model_config':{'sha256':file_sha(paths['model_config'])},'mhr_model':{'sha256':file_sha(paths['mhr'])},'surface_anchors':{'sha256':file_sha(paths['anchors'])},'surface_metrics_py':{'sha256':file_sha(paths['surface_metrics'])},'sam3d_source':{'python_yaml_tree_hash':source_tree_sha(sam_repo)}}};freeze_path=assets/'freeze.json';freeze_path.write_text(json.dumps(freeze))
        asset_args=SimpleNamespace(**paths,sam_repo=sam_repo,asset_freeze=freeze_path);verify_assets(asset_args);paths['anchors'].write_text('changed')
        try:verify_assets(asset_args);raise AssertionError('changed asset was accepted')
        except RuntimeError as error:assert 'ASSET_FREEZE_MISMATCH' in str(error)
        rows=[];formal_rows=[]
        metric={'median_mm':40,'p90_mm':60,'p95_mm':70,'p99_mm':510,'max_mm':900,'coverage_50mm':.6,'above_500mm_count':2,'above_500mm_ratio':.02}
        corrected={**metric,'median_mm':34,'p95_mm':68}
        for subject in ('Sub03','Sub04','Sub05','Sub06','Sub07'):
            for action in ('backpack','stool','yogaball'):
                for frame_id in (1,2,3):
                    spec={'subject':subject,'sequence':f'{subject}_{action}','frame':f't{frame_id:04d}.000'};formal_rows.append(spec);cameras={cam:{'official':metric,'txyz':corrected,'rendered_depth_pinhole_undistorted_sensor':{'official':metric,'txyz':corrected}} for cam in ('K1','K2','K3')}
                    rows.append({'spec':spec,'Txyz_m':[.001,.002,.003],'fallback':False,'runtime_sam_ms':10,'runtime_txyz_ms':20,'runtime_total_ms':30,'multicamera_outcome':'ALL_3_IMPROVED','translation_only_qa':{'pass':True},'cameras':cameras})
        manifest_path=root/'formal.json';manifest_path.write_text(json.dumps({'role':'FRESH_FORMAL_GENERALIZATION','fresh_only':True,'rows':formal_rows}));results=root/'results.json';results.write_text(json.dumps(rows));out=root/'report';cmd=[sys.executable,str(Path(__file__).with_name('aggregate_v2.py')),'--results',str(results),'--manifest',str(manifest_path),'--out',str(out)]
        subprocess.run(cmd,check=True);rendered=json.loads((out/'BEHAVE_RENDERED_DEPTH_EVAL_V2.json').read_text())['rows'];outliers=json.loads((out/'BEHAVE_DEPTH_OUTLIER_AUDIT_V2.json').read_text())['rows'];assert len(rendered)==135 and len(outliers)==270 and (out/'per_frame_per_camera_metrics.csv').is_file()
        results.write_text(json.dumps(rows[:-1]));blocked=subprocess.run(cmd,capture_output=True,text=True);assert blocked.returncode!=0 and 'PIPELINE_BLOCKED_INCOMPLETE_FORMAL_RUN' in blocked.stderr
    print('PURE_CODE_PREFLIGHT_V2_3_PASS')

if __name__=='__main__':main()
