"""Deterministic Camera A -> world -> Camera B transform QA."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np

def cam_to_world(p,R,T): return (p-T.reshape(1,3))@R
def world_to_cam(p,R,T): return p@R.T+T.reshape(1,3)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 with np.load(a.cache) as z:
  Ra,Ta,Rb,Tb=[z[k].astype(np.float64) for k in ('R_a','T_a','R_b','T_b')];pb=z['points_a'].astype(np.float64)
 synthetic=np.array([[0,0,1],[.25,-.1,2],[-.4,.3,3.5]],np.float64)
 center_a=cam_to_world(np.zeros((1,3)),Ra,Ta);center_back=world_to_cam(center_a,Ra,Ta)
 syn_back=world_to_cam(cam_to_world(synthetic,Ra,Ta),Ra,Ta)
 real=pb[np.linspace(0,len(pb)-1,min(1024,len(pb)),dtype=int)];real_back=world_to_cam(cam_to_world(real,Ra,Ta),Ra,Ta)
 ab=world_to_cam(cam_to_world(real,Ra,Ta),Rb,Tb);aba=world_to_cam(cam_to_world(ab,Rb,Tb),Ra,Ta)
 metrics={'synthetic_roundtrip_max_m':float(np.max(np.abs(syn_back-synthetic))),'camera_center_to_origin_max_m':float(np.max(np.abs(center_back))),'known_depth_point_roundtrip_max_m':float(np.max(np.abs(real_back-real))),'a_world_b_world_a_max_m':float(np.max(np.abs(aba-real))),'rotation_a_orthonormal_max':float(np.max(np.abs(Ra@Ra.T-np.eye(3)))),'rotation_b_orthonormal_max':float(np.max(np.abs(Rb@Rb.T-np.eye(3))))}
 tolerance_m=1e-6 # source camera matrices are stored as float32
 passed=max(metrics.values())<tolerance_m
 out={'status':'PASS' if passed else 'FAIL','contract':'OpenCV world2cam p_cam=p_world@R.T+T; inverse p_world=(p_cam-T)@R','tolerance_m':tolerance_m,'source_cache':str(a.cache),'tests':metrics,'camera_b_model_inference':False}
 a.out.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
