"""Original perspective rasterizer: visible axial-Z + per-image silhouette.

The Body is fixed Official RGB output; scan labels supervise surface only.
"""
import json
import numpy as np
import torch
from torch.nn import functional as F
from render_losses import MeshRenderer


class ScanTable:
    def __init__(self, compact, source, anchors_path=None, roles=('TRAIN',)):
        manifest = json.loads((compact/'MANIFEST.json').read_text())
        assert manifest['status'] == 'COMPLETE' and len(manifest['records']) == 3072
        self.rows = [r for r in manifest['records'] if r['role'] in roles]
        assert all(r['role'] in ['TRAIN','VAL'] for r in self.rows)
        self.faces = np.load(compact/'faces.npy')
        self.renderer = MeshRenderer(torch.from_numpy(self.faces),480,640)
        keys = ['rgb','metric','original_camera','K','bbox_center','bbox_scale','available']
        values = {k:[] for k in keys}
        bodies, depths, masks = [], [], []
        for r in self.rows:
            with np.load(compact/r['compact_file']) as z:
                for k in keys: values[k].append(z[k])
                bodies.append(z['official_pred_vertices'].reshape(-1,3))
            with np.load(source/(r['sample_id']+'.npz')) as z:
                depths.append(z['depth_clean_m'])
                masks.append(z['mask'].astype(bool))
        self.data = {k:torch.as_tensor(np.stack(v)) for k,v in values.items()}
        self.body = torch.from_numpy(np.stack(bodies))
        self.depth = torch.from_numpy(np.stack(depths))
        self.mask = torch.from_numpy(np.stack(masks))
        self.groups = {}
        for i,r in enumerate(self.rows):
            self.groups.setdefault(r['identity'],{}).setdefault(r['asset_id'],{}).setdefault(r['view']['group'],[]).append(i)

    def sample(self,rng,count=4):
        chosen=[]
        for _ in range(count):
            scans=self.groups[rng.choice(sorted(self.groups))]
            groups=scans[rng.choice(sorted(scans))]
            chosen.append(int(rng.choice(groups[rng.choice(sorted(groups))])))
        return np.asarray(chosen)

    def components(self,camera,indices):
        body=self.body[indices].to(camera.device)
        depth=self.depth[indices].to(camera.device)
        mask=self.mask[indices].to(camera.device)
        K=self.data['K'][indices].to(camera.device)
        rendered,silhouette=self.renderer(body+camera[:,None],K)
        loss=F.smooth_l1_loss(rendered,depth,beta=.02,reduction='none')
        lz=(loss*mask).sum((1,2))/mask.sum((1,2))
        intersection=(silhouette*mask).sum((1,2))
        union=(silhouette+mask-silhouette*mask).sum((1,2))
        ls=1-intersection/union.clamp_min(1)
        hit=((rendered>0)&mask).sum((1,2))/mask.sum((1,2))
        return lz,ls,hit

    def loss(self,camera,indices,weights):
        lz,ls,_=self.components(camera,indices)
        return weights['depth']*lz.mean()+weights['silhouette']*ls.mean()


def output_gradient(camera,loss):
    return torch.autograd.grad(loss.sum(),camera,retain_graph=True)[0].detach().cpu().numpy()


def renderer_qa():
    # Large oblique triangle: exact pinhole ray intersection at selected integer centres.
    vertices=torch.tensor([[[-.8,-.7,1.1],[.9,-.6,1.8],[0.,.9,1.4]]],device='cuda',requires_grad=True)
    K=torch.tensor([[[100.,0.,63.5],[0.,100.,63.5],[0.,0.,1.]]],device='cuda')
    render=MeshRenderer(torch.tensor([[0,1,2]]),128,128)
    depth,mask=render(vertices,K)
    v,u=torch.nonzero(depth[0]>0,as_tuple=True)
    pick=torch.linspace(0,len(u)-1,64,device='cuda').long();u,v=u[pick],v[pick]
    rays=torch.stack(((u-K[0,0,2])/100,(v-K[0,1,2])/100,torch.ones_like(u)),1)
    normal=torch.cross(vertices[0,1]-vertices[0,0],vertices[0,2]-vertices[0,0],dim=0)
    true_z=(normal@vertices[0,0])/(rays@normal)
    error=float((depth[0,v,u]-true_z).abs().max())
    assert error<1e-5
    loss=depth[0,v,u].mean()+mask.mean()
    loss.backward()
    gradient=float(vertices.grad.norm())
    assert gradient>0 and np.isfinite(gradient)
    return dict(status='PASS',oblique_triangle_axial_Z_max_error_m=error,gradient_norm=gradient,
                integer_pixel_centres=True,perspective_not_orthographic=True)
