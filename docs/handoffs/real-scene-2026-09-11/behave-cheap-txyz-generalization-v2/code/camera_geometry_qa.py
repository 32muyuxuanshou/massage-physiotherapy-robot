import argparse,json,sys
from pathlib import Path
import numpy as np
import cv2
from scipy.spatial import cKDTree
from behave_v2_io import read_camera,local_to_world,world_to_local,transform_between

def main():
 p=argparse.ArgumentParser();p.add_argument('--calibs',type=Path,required=True);p.add_argument('--sequence-roots',type=Path,nargs='+',required=True);p.add_argument('--behave-repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=[];sys.path.insert(0,str(a.behave_repo));from data.kinect_transform import KinectTransform
 points=np.array([[0.,0.,1.],[.2,-.1,2.],[-.3,.25,3.]])
 for seqroot in a.sequence_roots:
  seq=seqroot.name
  cams=[read_camera(a.calibs,seq,k) for k in range(4)]
  official=KinectTransform(str(seqroot))
  for target in [1,2,3]:
   q=transform_between(points,cams[0],cams[target]);back=transform_between(q,cams[target],cams[0]);err=float(np.abs(back-points).max());origin=transform_between(np.zeros((1,3)),cams[0],cams[target])[0];official_q=official.world2local(official.local2world(points,0),target);official_err=float(np.abs(q-official_q).max())
   rows.append({'sequence':seq,'date':cams[0]['date'],'source':'K0','target':f'K{target}','roundtrip_max_m':err,'vs_official_KinectTransform_max_m':official_err,'source_origin_in_target_m':origin.tolist(),'synthetic_target_z_m':q[:,2].tolist(),'pass':err<1e-9 and official_err<1e-9 and np.isfinite(q).all()})
  frames=sorted(seqroot.glob('t*'));frame=frames[len(frames)//2];world=[]
  for k in range(4):
   dep=cv2.imread(str(frame/f'k{k}.depth.png'),-1);mask=cv2.imread(str(frame/f'k{k}.person_mask.jpg'),0);good=(dep>0)&(mask>127);ray=np.dstack([cams[k]['pointcloud_table'],np.ones(dep.shape)]);pc=ray[good]*dep[good,None]/1000.;pc=pc[::max(1,len(pc)//5000)][:5000];world.append(local_to_world(pc,cams[k]))
  overlaps=[]
  for k in [1,2,3]:overlaps.append({'pair':f'K0-K{k}','symmetric_median_m':float((np.median(cKDTree(world[k]).query(world[0])[0])+np.median(cKDTree(world[0]).query(world[k])[0]))/2)})
  rows.append({'sequence':seq,'frame':frame.name,'world_person_cloud_overlap':overlaps,'pass':all(x['symmetric_median_m']<.20 for x in overlaps),'threshold_note':'0.20 m is a broad calibration sanity gate, not an accuracy metric'})
 status='PASS' if all(x['pass'] for x in rows) else 'FAIL';a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps({'status':status,'unit_contract':'camera points and translations in metres; depth PNG converted mm->m','rows':rows},indent=2)+'\n')
if __name__=='__main__':main()
