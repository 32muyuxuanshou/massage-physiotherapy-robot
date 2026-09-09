from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
source=ROOT/'docs/handoffs/real-scene-2026-09-06/reviewed-dmd37-2026-09-07/reviewed_points.json'
bridge=ROOT/'AI感知模块/模型资源/SMPL-X_SKEL_v2.2_internal/alignment/mapping_male.npz'
fp=O.parent/'2026-09-08_SAM_NLF_DEV40/nlf_smpl_faces.npy'
v=np.load(O/'canonical_smpl.npy');f=np.load(fp);b=np.load(bridge)
assert np.array_equal(f,b['skel_skin_faces'])
points=json.loads(source.read_text(encoding='utf8'))['points'];rows=[]
assert v.shape==(6890,3) and len(points)==37
for p in points:
    ids=np.array(p['vertex_indices']);weights=np.array(p['barycentric'],float)
    assert np.array_equal(f[p['face_index']],ids)
    assert np.isclose(weights.sum(),1,atol=1e-6) and (weights>=0).all()
    rows.append(dict(point_id=p['point_id'],reference_code=p['reference_code'],side=p['side'],
        face_index=p['face_index'],vertex_indices=ids.tolist(),barycentric=weights.tolist(),
        canonical_xyz=(v[ids]*weights[:,None]).sum(0).tolist()))
unique,inverse=np.unique(np.array([r['vertex_indices'] for r in rows]).reshape(-1),return_inverse=True)
query=np.concatenate([np.array([r['canonical_xyz'] for r in rows]),v[unique]])
np.save(O/'query_canonical.npy',query.astype(np.float32));np.save(O/'faces.npy',f)
payload=dict(status='EXACT_FACE_INDEX_BINDING_NOT_POSITION_VALIDATION',points=rows,
    face_arrays_identical=True,faces_shape=list(f.shape),canonical_shape=list(v.shape),
    unique_support_vertices=unique.tolist(),support_query_indices=(inverse.reshape(37,3)+37).tolist(),
    query_order='first 37 original barycentric points, then unique supporting vertex queries',
    query_count=len(query),axis_transform='none: canonical coordinates from official NLF template',
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,bridge,fp,O/'canonical_smpl.npy']},
    caveat='Same topology preserves surface indexing, not patient anatomy or medical accuracy. No nearest-neighbor bridge used. Original Atlas untouched.')
(O/'binding.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
# Canonical reference only, use same face indices and show both sides without inferring orientation.
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
board=Image.new('RGB',(1400,1000),(28,28,32))
for col,sign in enumerate([1,-1]):
    tri=v[f];order=np.argsort(tri[:,:,2].mean(1)*sign)
    uv=np.column_stack([350+sign*v[:,0]*500,550-v[:,1]*500])
    im=Image.new('RGB',(700,950),(35,38,44));d=ImageDraw.Draw(im)
    for j in order:
        t=tri[j];n=np.cross(t[1]-t[0],t[2]-t[0]);shade=int(115+65*abs(n[2])/(np.linalg.norm(n)+1e-10))
        d.polygon([tuple(x) for x in uv[f[j]]],fill=(shade,shade,shade))
    for r in rows:
        q=r['canonical_xyz'];x=350+sign*q[0]*500;y=550-q[1]*500
        d.ellipse((x-3,y-3,x+3,y+3),fill='yellow');d.text((x+4,y-7),r['point_id'][-2:],font=font,fill='yellow')
    board.paste(im,(col*700,40));ImageDraw.Draw(board).text((col*700+10,10),f'NLF canonical view {col+1}; all points shown, no occlusion filtering',font=font,fill='white')
board.save(O/'canonical_binding.jpg',quality=94)
print(json.dumps(dict(points=len(rows),queries=len(query),canonical_min=v.min(0).tolist(),canonical_max=v.max(0).tolist(),faces_identical=True)))
