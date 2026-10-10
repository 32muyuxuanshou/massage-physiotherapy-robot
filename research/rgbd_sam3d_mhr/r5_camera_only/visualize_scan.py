"""Actual cached MHR surfaces, perspective z-buffer shading over original RGB."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import torch
import nvdiffrast.torch as dr
from camera_head import CameraHead
from train_camera import forward


def shading(ctx,vertices,faces,K,h,w):
    v=torch.from_numpy(vertices[None]).float().cuda();K=torch.from_numpy(K[None]).float().cuda()
    x,y,z=v.unbind(-1);near,far=.05,20.
    clip=torch.stack((2*K[:,0,0,None]/w*x+(2*(K[:,0,2,None]+.5)/w-1)*z,
        -2*K[:,1,1,None]/h*y+(1-2*(K[:,1,2,None]+.5)/h)*z,
        (far+near)/(far-near)*z-2*far*near/(far-near),z),-1).contiguous()
    f=torch.from_numpy(faces).int().cuda().contiguous()
    triangles=v[0,f.long()];normal=torch.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0],dim=1)
    normal=normal/normal.norm(dim=1,keepdim=True).clamp_min(1e-12)
    light=torch.tensor([.3,-.4,-.866],device='cuda')
    intensities=.35+.65*(normal@light).abs()
    rast,_=dr.rasterize(ctx,clip,f,resolution=[h,w],grad_db=False)
    ids=rast[0,:,:,3].long().flip(0)-1;hit=ids>=0
    intensity=intensities[ids.clamp_min(0)]
    return hit.cpu().numpy(),intensity.cpu().numpy()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();torch.set_num_threads(2)
    rows=json.loads((a.root/'assets/visual_inputs/MANIFEST.json').read_text())['records']
    ctx=dr.RasterizeCudaContext();faces=np.load(a.root/'assets/compact_scan/faces.npy')
    models={}
    for name in ['native_only','mixed']:
        state=torch.load(a.root/f'continuation/{name}_s11/best.pt',map_location='cpu',weights_only=False)
        m=CameraHead(state['head']['metric_mean'],state['head']['metric_std'],'metric_xyz')
        m.load_state_dict(state['head']);m.eval();models[name]=m
    out=a.root/'visualizations';out.mkdir(exist_ok=True)
    manifest=[]
    for row in rows:
        z=np.load(a.root/'assets/visual_inputs'/(row['sample_id']+'.npz'))
        rgb=z['image_rgb'];h,w=rgb.shape[:2];body=z['official_pred_vertices'].reshape(-1,3)
        data={k:torch.from_numpy(np.asarray(z[k])[None]) for k in
              ['rgb','metric','original_camera','K','bbox_center','bbox_scale','available']}
        # rgb in the head table is the cached 1280 feature; image_rgb is displayed.
        cameras={'Official':z['original_camera']}
        with torch.no_grad():
            for name,m in models.items():cameras[name]=forward(m,data,np.asarray([0]),'cpu').numpy()[0]
        panels=[Image.fromarray(rgb)]
        for name,camera in cameras.items():
            hit,intensity=shading(ctx,body+camera,faces,z['K'],h,w)
            color=intensity[:,:,None]*np.array([65,185,235])[None,None]
            overlay=rgb.astype(float).copy();overlay[hit]=.2*overlay[hit]+.8*color[hit]
            panels.append(Image.fromarray(np.uint8(np.clip(overlay,0,255))))
        canvas=Image.new('RGB',(w*4,h+44),'white');draw=ImageDraw.Draw(canvas)
        for i,(panel,label) in enumerate(zip(panels,['RGB','Official','Native-only continuation','Scan-mixed continuation'])):
            canvas.paste(panel,(i*w,44));draw.text((i*w+8,7),label,fill='black')
        draw.text((8,25),row['sample_id']+' | seed11 | '+row['view']['group'],fill='black')
        file=out/(row['sample_id']+'.jpg');canvas.save(file,quality=94)
        manifest.append(dict(row,file=file.name,camera_xyz_m={k:v.tolist() for k,v in cameras.items()},
                             rendering='original perspective K, nvdiffrast visible triangles, fixed normal shading'))
    (out/'VISUALIZATION_MANIFEST.json').write_text(json.dumps(dict(records=manifest,selection='fixed before full result interpretation; no best-seed selection'),indent=2))
