import argparse,json,subprocess,sys
from pathlib import Path
import cv2,numpy as np
from .hashing import array_record,file_sha
def prepared_tensor_record(tensor):return {**array_record(tensor.detach().cpu().contiguous().numpy()),'device':str(tensor.device)}
def output_records(vertices,cam_t,anchors):return {'pred_vertices':array_record(vertices),'pred_cam_t':{**array_record(cam_t),'values':np.asarray(cam_t).tolist()},'anchors':array_record(anchors)}
def worker(a):
 import torch
 sys.path[:0]=[str(a.sam_repo),str(a.v23_code)];from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator;from sam_3d_body.data.utils.prepare_batch import prepare_batch;from sam_3d_body.utils import recursive_to;from behave_v2_io import read_camera
 model,cfg=load_sam_3d_body(str(a.checkpoint),device='cuda',mhr_path=str(a.mhr));model.eval();est=SAM3DBodyEstimator(model,cfg);faces=model.head_pose.faces.cpu().numpy().astype(np.int64);z=np.load(a.anchor_asset);fi,bc=z['face_index'],z['barycentric'].astype(float);rows=[]
 for spec in json.loads(a.manifest.read_text())['rows']:
  frame=a.sequences/spec['sequence']/spec['frame'];rgb_path=frame/'k0.color.jpg';mask_path=frame/'k0.person_mask.jpg';bgr=cv2.imread(str(rgb_path));rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);mask=cv2.imread(str(mask_path),0);y,x=np.where(mask>127);bbox=np.array([[max(0,x.min()-25),max(0,y.min()-25),min(rgb.shape[1]-1,x.max()+25),min(rgb.shape[0]-1,y.max()+25)]],np.float32);batch=recursive_to(prepare_batch(rgb,est.transform,bbox,None,None),'cuda');cam=read_camera(a.calibs,spec['sequence'],0);batch['cam_int']=torch.as_tensor(cam['K'][None],device='cuda').to(batch['img']);model._initialize_batch(batch)
  with torch.inference_mode():pred=model.forward_step(batch,decoder_type='body')['mhr']
  vertices=(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].cpu().numpy();cam_t=pred['pred_cam_t'][0].cpu().numpy();anchors=(vertices[faces[fi]]*bc[:,:,None]).sum(1);fid='/'.join(spec[k] for k in ('subject','sequence','frame'));rows.append({'frame_id':fid,'raw_rgb_file_sha256':file_sha(rgb_path),'decoded_rgb':array_record(rgb),'raw_mask_file_sha256':file_sha(mask_path),'decoded_mask':array_record(mask),'bbox_values':bbox.tolist(),'bbox':array_record(bbox),'prepared_tensor':prepared_tensor_record(batch['img']),**output_records(vertices,cam_t,anchors)})
 a.output.write_text(json.dumps({'run_id':a.run_id,'fresh_process':True,'rows':rows},indent=2)+'\n')
def coordinator(a):
 outputs=[]
 for run_id in ('RUN_B','RUN_C','RUN_D','RUN_E'):
  out=a.output.parent/f'{run_id}.json';cmd=[sys.executable,'-m','repro_fix.sam_repro_runner','--worker','--run-id',run_id]
  for name in ('manifest','sequences','calibs','sam-repo','checkpoint','mhr','anchor-asset','v23-code'):cmd += ['--'+name,str(getattr(a,name.replace('-','_')))]
  cmd += ['--output',str(out)];subprocess.run(cmd,check=True);outputs.append(str(out))
 a.output.write_text(json.dumps({'canonical':'RECONSTRUCTED_REPLAY_RUN_A','fresh_process_runs':outputs,'canonical_reselection_prohibited':True},indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--run-id',default='COORDINATOR')
 for n in ('manifest','sequences','calibs','sam-repo','checkpoint','mhr','anchor-asset','v23-code','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();worker(a) if a.worker else coordinator(a)
if __name__=='__main__':main()
