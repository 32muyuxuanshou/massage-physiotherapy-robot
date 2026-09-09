from pathlib import Path
import json,ast,numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;D=O.parent/'2026-09-08_SCALEUP_MHR'
meta=O.parents[3]/'AI感知模块/研究资料/真实场景关键点定位_2026-09-06/local/sam-3d-body/sam_3d_body/metadata/__init__.py'
v={}
for n in ast.parse(meta.read_text(encoding='utf-8')).body:
 if isinstance(n,ast.Assign):
  for t in n.targets:
   if isinstance(t,ast.Name) and t.id in ['MHR70_TO_OPENPOSE','OPENPOSE_TO_COCO']:v[t.id]=ast.literal_eval(n.value)
m=[v['MHR70_TO_OPENPOSE'][i] for i in v['OPENPOSE_TO_COCO']][5:17]
anns=json.loads((O.parent/'2026-09-08_COCO2014_DATASET/subset_annotations/person_keypoints_train2014.json').read_text());by={}
for a in anns['annotations']:
 if not a['iscrowd'] and a['num_keypoints']>=6:by.setdefault(a['image_id'],[]).append(a)
rows=json.loads((D/'samples.json').read_text());changes=[];proposals=[]
for r in rows:
 p2=np.array(r['keypoints_2d'])[m,:2];scores=[]
 for a in by[r['image_id']]:
  gt=np.array(a['keypoints']).reshape(17,3)[5:];vis=gt[:,2]>0
  if not vis.any():continue
  cost=float(np.linalg.norm(p2[vis]-gt[vis,:2],axis=1).mean()/np.sqrt(a['bbox'][2]*a['bbox'][3]));scores.append((cost,a))
 scores.sort(key=lambda z:z[0]);best,a=scores[0];gap=scores[1][0]-best if len(scores)>1 else 999
 old=r['coco_annotation'];r['old_coco_annotation_id']=old['id'];r['association_cost']=best;r['association_gap']=gap
 r['manual_eligible']=best<.15 and gap>.05
 if a['id']!=old['id']:
  changes.append(dict(id=r['id'],split=r['split'],old=old['id'],new=a['id'],best=best,gap=gap,eligible=r['manual_eligible']))
  im=Image.open(O.parent/'2026-09-08_COCO2014_DATASET/images/train2014'/r['image']).convert('RGB');im.thumbnail((640,540));sc=np.array(im.size)/np.array(r['original_hw'][::-1]);panels=[]
  for title,ann in [('OLD',old),('PROPOSED',a)]:
   canvas=im.copy();draw=ImageDraw.Draw(canvas);draw.text((5,5),r['id']+' '+title,fill='yellow')
   for xy in p2*sc:draw.ellipse((xy[0]-2,xy[1]-2,xy[0]+2,xy[1]+2),fill='cyan')
   for pt in np.array(ann['keypoints']).reshape(17,3)[5:]:
    if pt[2]>0:
     x,y=pt[:2]*sc;draw.ellipse((x-3,y-3,x+3,y+3),outline='red',width=2)
   panels.append(canvas)
  board=Image.new('RGB',(im.width*2,im.height));board.paste(panels[0]);board.paste(panels[1],(im.width,0));board.save(O/(r['id']+'_association.jpg'))
 r['coco_annotation']=a;proposals.append(r)
# Conflicting assignments are not allowed to contribute manual loss.
groups={}
for r in proposals:groups.setdefault((r['image_id'],r['coco_annotation']['id']),[]).append(r)
for rr in groups.values():
 if len(rr)>1:
  for r in rr:r['manual_eligible']=False
(O/'association_proposals.json').write_text(json.dumps(proposals))
summary=dict(changes=changes,total=len(rows),eligible=sum(r['manual_eligible'] for r in proposals),unresolved=[r['id'] for r in proposals if not r['manual_eligible']],method='label-to-label nearest correspondence with distinct alternative gap; no predicted mesh used; original split retained; proposals require visual verification')
(O/'association_audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
