"""Run frozen Official SAM3D + Cheap Txyz on one registered custom RGB-D frame."""
import argparse,json,sys,time
from pathlib import Path
import cv2,numpy as np,torch
from run_cheap_txyz_demo import robust_translation,surface_anchors,write_obj,TOTAL_BOUND_M

def load_k(path):
 return np.load(path).astype(float) if path.suffix.lower()=='.npy' else np.asarray(json.loads(path.read_text()),float)
def main():
 ap=argparse.ArgumentParser()
 for n in ('rgb','depth','intrinsics','person-mask','sam-repo','official','mhr','anchors','output-dir'):ap.add_argument('--'+n,type=Path,required=True)
 ap.add_argument('--depth-unit',choices=('mm','m'),required=True);a=ap.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
 rgb=cv2.cvtColor(cv2.imread(str(a.rgb)),cv2.COLOR_BGR2RGB);depth=cv2.imread(str(a.depth),cv2.IMREAD_UNCHANGED);mask=cv2.imread(str(a.person_mask),cv2.IMREAD_GRAYSCALE)>0;K=load_k(a.intrinsics)
 if rgb is None or depth is None or rgb.shape[:2]!=depth.shape[:2] or depth.shape!=mask.shape or K.shape!=(3,3):raise ValueError('RGB/depth/mask/K violate CUSTOM_RGBD_INPUT_CONTRACT_V1')
 z=depth.astype(float)*(0.001 if a.depth_unit=='mm' else 1.0);valid=mask&np.isfinite(z)&(z>0);y,x=np.nonzero(valid);Z=z[valid];points=np.c_[(x-K[0,2])*Z/K[0,0],(y-K[1,2])*Z/K[1,1],Z]
 if len(points)<100:raise ValueError('INSUFFICIENT_VALID_POINTS')
 yy,xx=np.nonzero(mask);bbox=np.array([xx.min(),yy.min(),xx.max(),yy.max()],np.float32)
 sys.path.insert(0,str(a.sam_repo));from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
 from sam_3d_body.data.utils.prepare_batch import prepare_batch
 from sam_3d_body.utils import recursive_to
 model,cfg=load_sam_3d_body(str(a.official),device='cuda',mhr_path=str(a.mhr));model.eval();est=SAM3DBodyEstimator(model,cfg);faces=model.head_pose.faces.cpu().numpy().astype(np.int64)
 with torch.inference_mode():
  b=recursive_to(prepare_batch(rgb,est.transform,bbox[None],None,None),'cuda');b['cam_int']=torch.as_tensor(K[None],device='cuda').to(b['img']);model._initialize_batch(b);pred=model.forward_step(b,decoder_type='body')['mhr'];vo=(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].cpu().numpy()
 spec=np.load(a.anchors);anchors=surface_anchors(vo,faces,spec['face_index'],spec['barycentric'].astype(float));st=time.perf_counter();raw,trace=robust_translation(points,anchors);ms=(time.perf_counter()-st)*1000;fallback=np.linalg.norm(raw)>TOTAL_BOUND_M;applied=np.zeros(3) if fallback else raw;vc=vo+applied
 write_obj(a.output_dir/'official_mesh.obj',vo,faces);write_obj(a.output_dir/'corrected_mesh.obj',vc,faces)
 result={'status':'FALLBACK' if fallback else 'CORRECTED','Txyz_m':raw.tolist(),'applied_Txyz_m':applied.tolist(),'Tnorm_mm':float(np.linalg.norm(raw)*1000),'valid_depth_points':len(points),'fallback_reason':'CORRECTION_OUT_OF_RANGE' if fallback else None,'runtime_txyz_ms':ms,'iterations':trace,'formula':'V_corrected = V_official + applied_Txyz'};(a.output_dir/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
