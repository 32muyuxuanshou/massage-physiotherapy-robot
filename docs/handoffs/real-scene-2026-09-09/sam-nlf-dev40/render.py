import os
os.environ['PYOPENGL_PLATFORM']='egl'
import sys,json
from pathlib import Path
import numpy as np,cv2
P=Path('/raid5/xuhd/sam3d_s01_pilot_20260906');O=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'sam-3d-body'))
from sam_3d_body.visualization.renderer import Renderer
for row in json.loads((O/'manifest.json').read_text()):
    dest=O/row['id'];im=cv2.imread(str(O/row['input_relative']))
    h,w=im.shape[:2];scale=min(1.,1200/max(h,w));nw,nh=round(w*scale),round(h*scale)
    im=cv2.resize(im,(nw,nh));K=np.array(row['K'],np.float64);K[0]*=nw/w;K[1]*=nh/h
    # Renderer accepts one focal length: input images share square-pixel K;
    # use isotropic exact scale and tolerate subpixel image resize rounding.
    K=np.array(row['K'],np.float64)*scale;K[2]=[0,0,1]
    for name in ['sam','nlf']:
        p=np.load(dest/f'{name}.npz')
        v=p['vertices_camera'] if name=='sam' else p['vertices3d'][0]/1000
        faces=np.load(O/('sam_faces.npy' if name=='sam' else 'nlf_smpl_faces.npy'))
        renderer=Renderer(focal_length=float(K[0,0]),faces=faces)
        rgba=renderer(v,np.zeros(3),im.copy(),mesh_base_color=(.65,.75,.9),return_rgba=True,camera_center=K[:2,2])
        a=rgba[:,:,3:4];overlay=(rgba[:,:,:3]*255*a*.65+im*(1-a*.65)).clip(0,255).astype(np.uint8)
        cv2.imwrite(str(dest/f'{name}_overlay.jpg'),overlay)
    cv2.imwrite(str(dest/'original_display.jpg'),im)
    print('RENDERED',row['id'],flush=True)
print('RENDER_COMPLETE',flush=True)
