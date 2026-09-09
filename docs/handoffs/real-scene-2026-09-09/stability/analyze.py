import json,csv,sys
from pathlib import Path
import numpy as np
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'2026-09-08_NLF_ATLAS_QUERY'))
from analyze_query import read_image,save_image
import cv2
D=O.parent/'2026-09-08_SAM_NLF_DEV40'
manifest={r['id']:r for r in json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'))}
rows=[];all_dist={};pictures=[]
run_meta={(r['id'],r['variant']):r for r in json.loads((O/'sam_results.json').read_text())}
for name in ['B1','B2','B3','B4','B5','N1']:
    panels=[]
    for model in ['sam','nlf']:
        base=np.load(O/name/'original'/(model+'.npz'))
        for variant in ['pad_shift','crop']:
            q=np.load(O/name/variant/(model+'.npz'))
            dp=np.linalg.norm(q['original_uv']-base['original_uv'],axis=1)
            dm=np.linalg.norm(q['xyz_mm']-base['xyz_mm'],axis=1)
            assert np.isfinite(dp).all() and np.isfinite(dm).all()
            row=dict(id=name,model=model,variant=variant,mean_px=float(dp.mean()),p95_px=float(np.percentile(dp,95)),max_px=float(dp.max()),mean_mm=float(dm.mean()),p95_mm=float(np.percentile(dm,95)))
            rows.append(row);all_dist.setdefault(model+'_'+variant,[]).append((dp,dm))
            meta=run_meta[(name,variant)]
            changed=meta['shape']!=run_meta[(name,'original')]['shape'] or not np.array_equal(meta['A'],np.eye(3))
            if variant=='crop' and changed:all_dist.setdefault(model+'_effective_crop',[]).append((dp,dm))
            im=read_image(D/name/'original_display.jpg');h,w=im.shape[:2];r=manifest[name];scale=np.array([w/r['width'],h/r['height']])
            for p,t in zip(base['original_uv']*scale,q['original_uv']*scale):
                p=tuple(np.round(p).astype(int));t=tuple(np.round(t).astype(int))
                cv2.line(im,p,t,(0,0,255),1);cv2.circle(im,p,3,(0,255,0),-1);cv2.circle(im,t,2,(255,0,255),-1)
            im=cv2.copyMakeBorder(im,40,0,0,0,cv2.BORDER_CONSTANT,value=(25,25,25))
            cv2.putText(im,f'{name} {model} {variant}: {dp.mean():.2f}px',(10,26),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
            panels.append(im)
    board=np.concatenate([np.concatenate(panels[:2],1),np.concatenate(panels[2:],1)],0)
    save_image(O/name/'comparison.jpg',board)
    pictures.append(cv2.resize(board,(900,int(board.shape[0]*900/board.shape[1]))))
summary={}
for key,parts in all_dist.items():
    p=np.concatenate([v[0] for v in parts]);m=np.concatenate([v[1] for v in parts])
    summary[key]=dict(points=len(p),mean_px=float(p.mean()),p95_px=float(np.percentile(p,95)),max_px=float(p.max()),mean_mm=float(m.mean()),p95_mm=float(np.percentile(m,95)))
(O/'summary.json').write_text(json.dumps(dict(status='INPUT_EQUIVARIANCE_NOT_ACCURACY',aggregate=summary,per_image=rows),indent=2))
with (O/'metrics.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save_image(O/'overview.jpg',np.concatenate(pictures,0))
print(json.dumps(summary,indent=2))
