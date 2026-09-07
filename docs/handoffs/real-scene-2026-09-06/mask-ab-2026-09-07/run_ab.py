import pathlib,sys,json,time,hashlib
import numpy as np,torch,cv2
r=pathlib.Path(__file__).resolve().parent;p=r.parent
sys.path.insert(0,str(p/'sam-3d-body'))
from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
from sam_3d_body.visualization.renderer import Renderer
im=cv2.imread(str(p/'real8/input/S05.png')); mask=(cv2.imread(str(r/'person_mask.png'),0)>0).astype(np.uint8)
model,cfg=load_sam_3d_body(str(p/'weights/model.ckpt'),device='cuda',mhr_path=str(p/'weights/assets/mhr_model.pt'))
est=SAM3DBodyEstimator(model,cfg);rows=[];saved={}
for name in ['baseline','mask']:
    torch.manual_seed(17);torch.cuda.manual_seed_all(17)
    start=time.perf_counter()
    out=est.process_one_image(cv2.cvtColor(im,cv2.COLOR_BGR2RGB),bboxes=np.array([[0,450,1920,1080]],np.float32),inference_type='body',**({'masks':mask[None]} if name=='mask' else {}))[0]
    torch.cuda.synchronize();elapsed=time.perf_counter()-start
    pred={k:np.asarray(v) for k,v in out.items() if v is not None};saved[name]=pred
    assert all(np.isfinite(v).all() for v in pred.values() if np.issubdtype(v.dtype,np.number))
    np.savez_compressed(r/f'{name}.npz',faces=est.faces,**pred)
    renderer=Renderer(focal_length=float(pred['focal_length']),faces=est.faces)
    rgba=renderer(pred['pred_vertices'],pred['pred_cam_t'],im.copy(),return_rgba=True)
    alpha=rgba[:,:,3:4]*.4;preview=(rgba[:,:,:3]*255*alpha+im*(1-alpha)).clip(0,255).astype(np.uint8)
    cv2.imwrite(str(r/f'{name}.png'),preview)
    rows.append(dict(condition=name,seconds=elapsed,finite=True));print('DONE',name,flush=True)
old=np.load(p/'real8/result/S05/prediction.npz')
status=dict(stage='AB_INFERENCE_COMPLETE',conditions=rows,changed_variable='external manually traced person mask only',image_sha256=hashlib.sha256((p/'real8/input/S05.png').read_bytes()).hexdigest(),mask_sha256=hashlib.sha256((r/'person_mask.png').read_bytes()).hexdigest(),bbox=[0,450,1920,1080],camera='unchanged default FOV',inference_type='body',baseline_vs_original_max_keypoint_shift_px=float(np.linalg.norm(saved['baseline']['pred_keypoints_2d']-old['pred_keypoints_2d'],axis=-1).max()),mask_vs_baseline_mean_keypoint_shift_px=float(np.linalg.norm(saved['mask']['pred_keypoints_2d']-saved['baseline']['pred_keypoints_2d'],axis=-1).mean()),independent_target_accuracy_measured=False)
(r/'run_status.json').write_text(json.dumps(status,indent=2)+'\n','utf-8');print(json.dumps(status),flush=True)
