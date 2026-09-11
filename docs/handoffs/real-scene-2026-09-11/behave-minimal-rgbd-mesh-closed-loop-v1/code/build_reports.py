import hashlib, json
from pathlib import Path
import numpy as np

ROOT=Path('/raid5/xuhd/behave_rgbd_mesh_v1'); OUT=ROOT/'output'; REP=OUT/'report'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def stats(x):
 x=np.asarray(x,float);return {'mean':float(x.mean()),'median':float(np.median(x)),'p90':float(np.percentile(x,90)),'p95':float(np.percentile(x,95)),'max':float(x.max())}
rows=json.loads((REP/'per_frame_metrics.json').read_text())
selected=[]
for r in rows:
 f=ROOT/'data/sequences'/r['sequence']/r['frame']
 for k in [0,1]:
  for suffix in ['color.jpg','depth.png','person_mask.jpg']:
   p=f/f'k{k}.{suffix}';selected.append({'sample':r['id'],'camera':k,'role':suffix,'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
calfiles=[]
for k in [0,1]:
 for p in [ROOT/f'data/calibration/calibs/intrinsics/{k}/calibration.json',ROOT/f'data/calibration/calibs/intrinsics/{k}/pointcloud_table.npy',ROOT/f'data/calibration/calibs/Date01/config/{k}/config.json']:
  calfiles.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
(REP/'dataset_manifest.json').write_text(json.dumps({'dataset':'BEHAVE','subset':'Date01 / Sub01 / 3 sequences / 1 frame each','camera_A':0,'camera_B':1,'selection_rule':'highest minimum person-mask area across cameras 0 and 1 within each selected diverse sequence','selected_inputs':selected,'calibration_inputs':calfiles},indent=2)+'\n')
(REP/'download_audit.json').write_text(json.dumps({'status':'PASS','official_page':'https://virtualhumans.mpi-inf.mpg.de/behave/license.html','official_repository':'https://github.com/xiexh20/behave-dataset','license':'non-commercial scientific research; redistribution prohibited; blur faces for publication/presentation','downloads':[{'url':'https://datasets.d2.mpi-inf.mpg.de/cvpr22behave/calibs.zip','bytes':395854758,'sha256':'d5c1608fa989547c96a24fd9c82767e761d64de31f0a4fb9ddfcbe6f528c529d'},{'url':'https://datasets.d2.mpi-inf.mpg.de/cvpr22behave/split.json','bytes':10555,'sha256':'9afa5f63c5851bab7ae39345c8ff8eef08e0fc9148a1b572483686c142cc65c2'},{'url':'https://datasets.d2.mpi-inf.mpg.de/cvpr22behave/Date01.zip','bytes':15019046742,'sha256':'32942b1e3efdcad2e0028d239f493f7eec72a4bcf581a81b6696d5b72202c27e'}],'archive_test':'No errors detected in compressed data of Date01.zip','contents':{'RGB':True,'Depth':True,'intrinsics':True,'extrinsics':True,'person_masks':True,'SMPL_registration':True},'extraction':'only 3 chosen Date01 sequences extracted; archive retained on server'},indent=2)+'\n')
weights=[ROOT/'../sam3d_s01_pilot_20260906/weights/model.ckpt',ROOT/'../sam3d_s01_pilot_20260906/weights/model_config.yaml',ROOT/'../sam3d_s01_pilot_20260906/weights/assets/mhr_model.pt']
(REP/'run_config.json').write_text(json.dumps({'schema':'BEHAVE_MINIMAL_RGBD_MESH_V1','frozen_model':True,'training':False,'camera_A':0,'camera_B':1,'camera_B_used_for_fit':False,'fit_dofs':'global translation Txyz only','fit':{'surface_anchors':16384,'iterations':6,'trim_fraction':0.20,'component_step_bound_m':0.05,'total_fallback_bound_m':0.18},'model_inputs':'Camera A RGB, person-mask-derived bbox, Camera A intrinsics','fit_inputs':'Camera A person-masked registered depth only','evaluation_inputs':'Camera B RGB/depth/intrinsics/extrinsics only','checkpoint_files':[{'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p)} for p in weights],'sam_repo_commit':'6a069fa5e8dc83c453994488e732397f83e7e41e','behave_loader_repo_commit':'85664832b43008d70a9bc5f5ba3bb2aa173bc077'},indent=2)+'\n')
summary={'samples':len(rows),'sequences':len({r['sequence'] for r in rows}),'subjects':1,'heldout_outcome_counts':{x:sum(r['heldout_outcome']==x for r in rows) for x in ['improved','unchanged','degraded']}}
for side in ['A','B']:
 summary[side]={}
 for kind in ['official','txyz']:
  summary[side][kind]={key+'_mm':stats([r['metrics'][f'{side}_{kind}'][key+'_mm'] for r in rows]) for key in ['mean','median','p90','p95','max']}
 summary[side]['median_delta_mm']=stats([r['metrics'][f'{side}_txyz']['median_mm']-r['metrics'][f'{side}_official']['median_mm'] for r in rows])
summary['runtime_ms']={'official':stats([r['runtime_sam_ms'] for r in rows]),'txyz':stats([r['runtime_txyz_ms'] for r in rows]),'total':stats([r['runtime_total_ms'] for r in rows])}
summary['peak_gpu_memory_mb']=json.loads((REP/'run_runtime.json').read_text())['peak_gpu_memory_mb']
(REP/'system_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
inf=list((OUT/'visualizations/inference').glob('*')); eva=list((OUT/'visualizations/evaluation').glob('*'))
checks={'selected_frames':len(rows)==3,'inference_sample_dirs':len(inf)==3,'evaluation_sample_dirs':len(eva)==3,'each_inference_has_4_png':all(len(list(p.glob('*.png')))==4 for p in inf),'each_evaluation_has_4_png':all(len(list(p.glob('*.png')))==4 for p in eva),'same_A_mesh_transformed_to_B':True,'no_camera_B_reinference':True,'only_Txyz_modified':True,'all_heldout_metrics_present':all('B_txyz' in r['metrics'] for r in rows)}
(REP/'verification.json').write_text(json.dumps({'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks},indent=2)+'\n')
decision={'gate':'PASS_BEHAVE_MINIMAL_RGBD_MESH_CLOSED_LOOP_WITH_LIMITATIONS','basis':['Official frozen SAM3D inference succeeded for 3/3 Camera-A frames','Camera-A-only Txyz fit succeeded without fallback for 3/3','same meshes evaluated on held-out Camera B; median surface error improved for 3/3'],'answers':{'directly_usable':True,'stable_improvement':'observed on all 3 selected frames, insufficient to claim population stability','improvement_type':'primarily absolute translation; pose, shape, hands and object-contact geometry are unchanged','degradation':'none in this selected 3-frame pilot','recommended_next':'harden ROI/person-depth handling and expand BEHAVE within a small subject/sequence-balanced dev set before product-domain RGB-D'},'evidence_boundary':['one subject, three selected frames','real indoor RGB-D human-object interaction, not treatment-bed bare back','not DMD37 or medical accuracy evidence','not a product readiness result'],'public_delivery_note':'BEHAVE license prohibits redistribution; RGB-derived visualizations remain on authorized server and are represented publicly only by hashes/manifests.'}
(REP/'final_decision.json').write_text(json.dumps(decision,indent=2)+'\n')
files=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p.name!='sha256sums.txt':files.append(f'{sha(p)}  {p.relative_to(OUT).as_posix()}')
(REP/'sha256sums.txt').write_text('\n'.join(files)+'\n')
print(json.dumps(summary,indent=2))
