import argparse,json
from pathlib import Path
import numpy as np
from behave_v2_io import read_camera,local_to_world,world_to_local,transform_between

def main():
 p=argparse.ArgumentParser();p.add_argument('--calibs',type=Path,required=True);p.add_argument('--sequences',nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[]
 points=np.array([[0.,0.,1.],[.2,-.1,2.],[-.3,.25,3.]])
 for seq in a.sequences:
  cams=[read_camera(a.calibs,seq,k) for k in range(4)]
  for target in [1,2,3]:
   q=transform_between(points,cams[0],cams[target]);back=transform_between(q,cams[target],cams[0]);err=float(np.abs(back-points).max());origin=transform_between(np.zeros((1,3)),cams[0],cams[target])[0]
   rows.append({'sequence':seq,'date':cams[0]['date'],'source':'K0','target':f'K{target}','roundtrip_max_m':err,'source_origin_in_target_m':origin.tolist(),'synthetic_target_z_m':q[:,2].tolist(),'pass':err<1e-9 and np.isfinite(q).all()})
 status='PASS' if all(x['pass'] for x in rows) else 'FAIL';a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps({'status':status,'unit_contract':'camera points and translations in metres; depth PNG converted mm->m','rows':rows},indent=2)+'\n')
if __name__=='__main__':main()
