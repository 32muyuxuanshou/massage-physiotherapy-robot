import argparse,json
from pathlib import Path
from behave_v2_io import read_camera,geometry_qa,transform_between
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--calibs',type=Path,required=True);p.add_argument('--sequences',nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
rows=[]
for seq in a.sequences:
 cams=[read_camera(a.calibs,seq,k) for k in range(4)]
 for c in cams: rows.append(geometry_qa(c))
 for k in [1,2,3]:
  p0=np.array([[.1,.2,2.],[-.2,.1,3.]])
  pk=transform_between(p0,cams[0],cams[k]);back=transform_between(pk,cams[k],cams[0])
  rows.append({'date':cams[0]['date'],'path':f'K0-world-K{k}-world-K0','closure_max_m':float(np.abs(back-p0).max()),'positive_target_depth':bool(np.all(pk[:,2]>0)),'pass':bool(np.abs(back-p0).max()<1e-9)})
a.out.write_text(json.dumps({'status':'PASS' if all(x['pass'] for x in rows) else 'FAIL','checks':rows},indent=2)+'\n')
