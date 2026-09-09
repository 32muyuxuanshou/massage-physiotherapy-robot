from pathlib import Path
import json,numpy as np
p=Path(__file__).resolve().parent
ns={'__file__':str(p/'audit_association.py')};s=(p/'audit_association.py').read_text(encoding='utf-8');exec(s[:s.index('anns=json.loads')],ns);mapping=ns['m']
rows=[r for r in json.loads((p/'association_proposals.json').read_text()) if r['split']=='validation'];pred=json.loads((p/'keypoints.json').read_text());results=[]
assert all(r['manual_eligible'] for r in rows)
for r in rows:
 a=r['coco_annotation'];gt=np.array(a['keypoints']).reshape(17,3)[5:];valid=gt[:,2]>0
 for tag in ['baseline','epoch2','epoch10']:
  xy=np.array(pred[r['id']+'/'+tag+'.npz'])[mapping];dd=np.linalg.norm(xy[valid]-gt[valid,:2],axis=1)/np.sqrt(a['bbox'][2]*a['bbox'][3])
  results.append(dict(id=r['id'],image=r['image'],tag=tag,nme=float(dd.mean()),pck05=float((dd<.05).mean())))
summary={}
for tag in ['baseline','epoch2','epoch10']:
 gr={}
 for r in results:
  if r['tag']==tag:gr.setdefault(r['image'],[]).append(r)
 summary[tag]={k:float(np.mean([np.mean([r[k] for r in rr]) for rr in gr.values()])) for k in ['nme','pck05']}
(p/'corrected_metrics.json').write_text(json.dumps(dict(summary=summary,rows=results,corrections='Three validation person associations corrected in two images; all 69 images/82 persons retained; no weights changed'),indent=2));print(json.dumps(summary,indent=2))
