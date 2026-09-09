"""Adaptive query-set ablation: consistency diagnostics, never ground-truth error."""
import json
from pathlib import Path
import numpy as np
from analyze_query import interpolate, project, panel, read_image, save_image

O=Path(__file__).resolve().parent
D=O.parent/'2026-09-08_SAM_NLF_DEV40'
b=json.loads((O/'binding.json').read_text())
idx=np.array([p['vertex_indices'] for p in b['points']])
w=np.array([p['barycentric'] for p in b['points']])
manifest={r['id']:r for r in json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'))}
rows=[]
for name in ['B1','B2','B3','B4','B5','N1']:
    q=np.load(O/name/'query.npz'); a=np.load(O/name/'query_anchored.npz')
    x=q['poses3d'][0,:37]; y=a['poses3d'][0,:37]
    f=interpolate(np.load(D/name/'nlf.npz')['vertices3d'][0],idx,w)
    assert np.isfinite(y).all() and (y[:,2]>0).all()
    row={'id':name,'anchored_query_count':int(a['poses3d'].shape[1])}
    for tag,p,r in [('local_vs_fitted',x,f),('anchored_vs_fitted',y,f),('local_vs_anchored',x,y)]:
        delta=p-r
        row[tag]={'mean_distance_mm':float(np.linalg.norm(delta,axis=1).mean()),
          'mean_projected_distance_px':float(np.linalg.norm(project(p,q['K'])-project(r,q['K']),axis=1).mean()),
          'centroid_delta_mm':delta.mean(0).tolist(),
          'translation_removed_mean_mm':float(np.linalg.norm(delta-delta.mean(0),axis=1).mean())}
    row['anchored_self_projection_max_px']=float(np.linalg.norm(project(y,a['K'])-a['poses2d'][0,:37],axis=1).max())
    rows.append(row)
    im=read_image(D/name/'original_display.jpg');m=manifest[name]
    panels=[panel(im,project(p,q['K']),m['width'],m['height'],title) for p,title in [(x,name+' | local 139 queries'),(y,name+' | local + whole-body anchors'),(f,name+' | fitted SMPL propagation')]]
    save_image(O/name/'anchor_comparison.jpg',np.concatenate(panels,axis=1))
(O/'anchor_analysis.json').write_text(json.dumps({'status':'ADAPTIVE_DIAGNOSTIC_NOT_ACCURACY','images':rows},indent=2))
print(json.dumps(rows,indent=2))
