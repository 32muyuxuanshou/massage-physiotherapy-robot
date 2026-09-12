import argparse,json,subprocess,sys
from pathlib import Path
import cv2,numpy as np
from .hashing import array_record,file_sha
def reconstruct(depth_path,mask_path,table_path,calibration_path=None):
 depth=cv2.imread(str(depth_path),-1);mask=cv2.imread(str(mask_path),0);table=np.load(table_path);good=(depth>0)&(mask>127);r=np.dstack([table,np.ones(table.shape[:2],table.dtype)]);points=r[good].astype(float)*depth[good,None].astype(float)/1000.
 return {'raw_depth_sha256':file_sha(depth_path),'decoded_depth':array_record(depth),'raw_mask_sha256':file_sha(mask_path),'decoded_mask':array_record(mask),'pointcloud_table_file_sha256':file_sha(table_path),'pointcloud_table':array_record(table),'calibration_file_sha256':file_sha(calibration_path) if calibration_path else None,'points':{**array_record(points),'order':'C'}}
def coordinator(manifest,output,runs=5):
 rows=[]
 for i in range(runs):
  p=Path(output).with_suffix(f'.run{i}.json');subprocess.run([sys.executable,'-m','repro_fix.pointcloud_repro_runner','--worker','--manifest',str(manifest),'--output',str(p)],check=True);rows.append(json.loads(p.read_text()));p.unlink()
 hashes=[[x['points']['sha256'] for x in run['rows']] for run in rows];status='PASS_POINTCLOUD_BYTE_IDENTITY' if all(x==hashes[0] for x in hashes) else 'POINTCLOUD_RECONSTRUCTION_NONDETERMINISTIC';payload={'status':status,'fresh_processes':runs,'runs':rows};Path(output).write_text(json.dumps(payload,indent=2)+'\n');return payload
def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--runs',type=int,default=5);a=p.parse_args()
 if a.worker:a.output.write_text(json.dumps({'rows':[{'frame_id':x['frame_id'],**reconstruct(x['depth'],x['mask'],x['pointcloud_table'],x.get('calibration'))} for x in json.loads(a.manifest.read_text())['rows']]},indent=2)+'\n')
 else:coordinator(a.manifest,a.output,a.runs)
if __name__=='__main__':main()
