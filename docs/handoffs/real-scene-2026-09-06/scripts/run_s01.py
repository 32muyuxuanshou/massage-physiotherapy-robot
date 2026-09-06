"""Single-photo body-only SAM pilot. No Atlas/acupoint claims; original input preserved."""
import argparse,hashlib,importlib.util,json,pathlib,sys,time

HERE=pathlib.Path(__file__).resolve().parent
DEFAULT_REPO=HERE/'sam-3d-body'
if not DEFAULT_REPO.is_dir():
    DEFAULT_REPO=HERE.parents[3]/'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/sam-3d-body'

def write_status(data):
    (HERE/'run_status.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=pathlib.Path,default=DEFAULT_REPO)
    ap.add_argument('--weights',type=pathlib.Path,default=HERE/'weights')
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args()
    image_path=HERE/'input/S01.png'
    required=[args.weights/'model.ckpt',args.weights/'model_config.yaml',args.weights/'assets/mhr_model.pt',args.repo/'sam_3d_body/__init__.py',image_path]
    missing=[str(p) for p in required if not p.is_file()]
    modules=['torch','torchvision','numpy','cv2','yacs','timm','einops','pytorch_lightning','pyrender','omegaconf']
    absent=[m for m in modules if importlib.util.find_spec(m) is None]
    cuda=False
    if 'torch' not in absent:
        import torch
        cuda=torch.cuda.is_available()
    status=dict(stage='PREFLIGHT',missing_files=missing,missing_modules=absent,cuda_available=cuda,inference_completed=False,atlas_mapping_completed=False)
    if missing or absent or not cuda:
        status['stage']='BLOCKED_BEFORE_MODEL_LOAD'
        status['cuda_note']='Pinned upstream estimator sends batches directly to cuda; this runner does not claim untested CPU compatibility.'
        write_status(status);print(json.dumps(status,ensure_ascii=False,indent=2));return 2
    if args.check_only:
        status['stage']='PREFLIGHT_PASSED_NOT_INFERRED';write_status(status);print(status['stage']);return 0
    sys.path.insert(0,str(args.repo.resolve()))
    import cv2,numpy as np
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    raw=np.fromfile(image_path,dtype=np.uint8);bgr=cv2.imdecode(raw,cv2.IMREAD_COLOR)
    assert bgr is not None
    assert bgr.shape[:2]==(1080,1920),'S01 original pixel coordinate contract changed'
    bbox=np.array([[0,500,1920,1080]],dtype=np.float32)
    status.update(stage='MODEL_LOADING',input_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),bbox_xyxy=bbox.tolist(),camera='upstream default FOV, uncalibrated',inference_type='body',device='cuda')
    write_status(status)
    model,cfg=load_sam_3d_body(str(args.weights/'model.ckpt'),device='cuda',mhr_path=str(args.weights/'assets/mhr_model.pt'))
    estimator=SAM3DBodyEstimator(model,cfg)
    started=time.perf_counter()
    outputs=estimator.process_one_image(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB),bboxes=bbox,inference_type='body')
    torch.cuda.synchronize()
    assert len(outputs)==1,'Expected one person from the supplied ROI'
    pred=outputs[0]
    out=HERE/'result';out.mkdir(exist_ok=True)
    arrays={k:np.asarray(v) for k,v in pred.items() if v is not None}
    np.savez_compressed(out/'prediction.npz',faces=estimator.faces,**arrays)
    status.update(stage='INFERENCE_SAVED_RENDER_PENDING',inference_completed=True,inference_seconds=time.perf_counter()-started)
    write_status(status)
    from sam_3d_body.visualization.renderer import Renderer
    renderer=Renderer(focal_length=pred['focal_length'],faces=estimator.faces)
    overlay=(renderer(pred['pred_vertices'],pred['pred_cam_t'],bgr.copy(),mesh_base_color=(0.65,0.74,0.86),scene_bg_color=(1,1,1))*255).clip(0,255).astype(np.uint8)
    for name,img in [('mesh_overlay.png',overlay),('original_vs_mesh.png',np.concatenate([bgr,overlay],axis=1))]:
        (out/name).write_bytes(cv2.imencode('.png',img)[1].tobytes())
    status.update(stage='INFERENCE_AND_RENDER_COMPLETE_NOT_ACUPOINT_VALIDATED',render_completed=True)
    write_status(status);print(json.dumps(status,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':
    raise SystemExit(main())
