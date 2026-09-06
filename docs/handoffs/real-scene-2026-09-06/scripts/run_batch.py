"""Fixed real-frame pilot; rendered pictures are QA only, never training inputs."""
import argparse, hashlib, json, pathlib, sys, time

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pilot',type=pathlib.Path,required=True)
    args=ap.parse_args()
    root=pathlib.Path(__file__).resolve().parent
    pilot=args.pilot.resolve()
    sys.path.insert(0,str(pilot/'sam-3d-body'))
    import numpy as np, cv2, torch
    from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
    from sam_3d_body.visualization.renderer import Renderer
    rows=json.loads((root/'input_manifest.json').read_text('utf-8-sig'))['images']
    model,cfg=load_sam_3d_body(str(pilot/'weights/model.ckpt'),device='cuda',mhr_path=str(pilot/'weights/assets/mhr_model.pt'))
    estimator=SAM3DBodyEstimator(model,cfg)
    records=[]
    for row in rows:
        sid=row['selection_id']; started=time.perf_counter()
        raw=(root/'input'/f'{sid}.png').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row['sha256']
        img=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        print('START',sid,flush=True)
        torch.cuda.reset_peak_memory_stats()
        if sid=='S01':
            with np.load(pilot/'result/prediction.npz') as previous:
                pred={k:previous[k].copy() for k in previous.files if k!='faces'}
                faces=previous['faces'].copy()
            inference_seconds=None
        else:
            t=time.perf_counter()
            outputs=estimator.process_one_image(cv2.cvtColor(img,cv2.COLOR_BGR2RGB),bboxes=np.array([row['bbox_xyxy']],np.float32),inference_type='body')
            torch.cuda.synchronize()
            inference_seconds=time.perf_counter()-t
            assert len(outputs)==1
            pred={k:np.asarray(v) for k,v in outputs[0].items() if v is not None}
            faces=estimator.faces
        assert all(np.isfinite(v).all() for v in pred.values() if np.issubdtype(v.dtype,np.number))
        dest=root/'result'/sid; dest.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(dest/'prediction.npz',faces=faces,**pred)
        render=Renderer(focal_length=float(pred['focal_length']),faces=faces)
        rgba=render(pred['pred_vertices'],pred['pred_cam_t'],img.copy(),mesh_base_color=(0.65,0.74,0.86),return_rgba=True)
        alpha=rgba[:,:,3:4]; rgb=rgba[:,:,:3]*255
        opaque=(rgb*alpha+img*(1-alpha)).clip(0,255).astype(np.uint8)
        blend=(rgb*alpha*.4+img*(1-alpha*.4)).clip(0,255).astype(np.uint8)
        contour=img.copy()
        contours,_=cv2.findContours((alpha[:,:,0]>.5).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(contour,contours,-1,(0,200,255),2)
        x1,y1,x2,y2=row['bbox_xyxy'];cv2.rectangle(contour,(x1,y1),(x2-1,y2-1),(255,180,0),2)
        for name,picture in [('opaque',opaque),('alpha40',blend),('contour_roi',contour)]:
            (dest/f'{name}.png').write_bytes(cv2.imencode('.png',picture)[1].tobytes())
        panels=[]
        for label,picture in [('ORIGINAL',img),('MESH 40% | NOT LABELS',blend),('PROJECTED OUTLINE + ROI',contour)]:
            panel=cv2.resize(picture,(640,360));cv2.rectangle(panel,(0,0),(640,30),(20,20,20),-1)
            cv2.putText(panel,sid+' '+label,(8,21),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1,cv2.LINE_AA);panels.append(panel)
        (dest/'qa.jpg').write_bytes(cv2.imencode('.jpg',np.concatenate(panels,axis=1),[cv2.IMWRITE_JPEG_QUALITY,92])[1].tobytes())
        record=dict(id=sid,input_sha256=row['sha256'],bbox_xyxy=row['bbox_xyxy'],inference_seconds=inference_seconds,reused_s01=sid=='S01',total_seconds=time.perf_counter()-started,peak_gpu_mb=torch.cuda.max_memory_allocated()/2**20,finite=True,vertices=len(pred['pred_vertices']),camera='default FOV, uncalibrated',external_occlusion_modeled=False,medical_labels=False)
        records.append(record)
        (root/'batch_status.json').write_text(json.dumps(dict(stage='COMPLETE' if len(records)==len(rows) else 'RUNNING',records=records),indent=2),'utf-8')
        print('DONE',json.dumps(record),flush=True)
    gallery=np.concatenate([cv2.imread(str(root/'result'/r['selection_id']/'qa.jpg')) for r in rows],axis=0)
    (root/'qa_all.jpg').write_bytes(cv2.imencode('.jpg',gallery,[cv2.IMWRITE_JPEG_QUALITY,92])[1].tobytes())

if __name__=='__main__':
    main()
