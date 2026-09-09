from pathlib import Path
import json,hashlib,collections
old=Path(__file__).resolve().parent.parent/'2026-09-08_COCO20_MHR_COMPARISON/prepare.py'
ns={'__file__':str(old)}
exec(old.read_text(encoding='utf-8').split('used=set();selected=[];groups={}')[0],ns)
rows=ns['candidates']; O=Path(__file__).resolve().parent
seen=set()
for name in ['2026-09-08_COCO20_MHR_COMPARISON/selection.json','2026-09-08_SAM_NLF_DEV40/manifest.json']:
 for r in json.loads((O.parent/name).read_text(encoding='utf-8-sig')):
  text=json.dumps(r)
  import re
  seen.update(re.findall(r'COCO_train2014_\d+\.jpg',text))
groups=collections.defaultdict(list)
for r in rows:groups[r['source_sha256']].append(r)
unseen=[s for s,rr in groups.items() if not any(r['image'] in seen for r in rr)]
unseen.sort(key=lambda s:hashlib.sha256(('20260908:'+s).encode()).hexdigest())
val=set(unseen[:round(len(groups)*.2)])
for r in rows:
 r['split']='validation' if r['source_sha256'] in val else 'train'
 r['id']=str(r['image_id'])+'_'+str(r['subject_idx'])
summary={'status':'FROZEN_BEFORE_SCALEUP','seed':20260908,'total_images':len(groups),'total_people':len(rows),'split_unit':'image SHA; not verified identity','pretraining_overlap':'COCO training source potentially used in SAM pretraining; fine-tuning holdout only','prior_viewed_images_excluded_from_validation':True,'epochs':2,'accumulation':8,'lr':1e-5,'weight_decay':0,'initialization':'original official SAM, not nine-image prototype','supervision':'same normalized fitted 2D + pelvis-relative fitted 3D joint loss as prototype; no contour loss','selection':'same existing validity/bbox/COCO matching filter; no model-score filtering'}
for split in ['train','validation']:
 rr=[r for r in rows if r['split']==split]
 summary[split]={'images':len(set(r['source_sha256'] for r in rr)),'people':len(rr),'tags':dict(collections.Counter(t for r in rr for t in r['tags']))}
(O/'samples.json').write_text(json.dumps(rows),encoding='utf-8')
(O/'protocol.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
