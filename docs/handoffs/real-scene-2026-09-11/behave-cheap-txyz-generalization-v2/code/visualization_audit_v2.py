import argparse,hashlib,json
from pathlib import Path
import cv2,numpy as np
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def montage(paths,out):
 ims=[cv2.imread(str(p)) for p in paths];ims=[cv2.resize(x,(960,263)) for x in ims]
 if ims:out.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(out),np.vstack(ims))
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=json.loads(a.manifest.read_text())['rows'];checks=[]
 inf_req=['camA_rgb_original.png','camA_official_overlay.png','camA_txyz_overlay.png','camA_triptych.png','camA_txyz_vector.png'];ev_req=['rgb_original.png','official_from_A_overlay.png','txyz_from_A_overlay.png','triptych.png','residual_official.png','residual_txyz.png','residual_comparison.png']
 for r in rows:
  sid=Path(r['subject'])/r['sequence']/r['frame'];groups={'inference':[a.root/'visualizations/inference'/sid/x for x in inf_req],'geometry_3d':[a.root/'visualizations/geometry_3d'/sid/'viewer.html'],'metrics_summary':[a.root/'visualizations/metrics_summary'/sid/'metrics_summary.png']}
  for k in ['K1','K2','K3']:groups[k]=[a.root/'visualizations/evaluation'/sid/k/x for x in ev_req]
  checks.append({'spec':r,'groups':{g:[{'path':str(x.relative_to(a.root)),'exists':x.is_file(),'bytes':x.stat().st_size if x.is_file() else None,'sha256':sha(x) if x.is_file() else None} for x in fs] for g,fs in groups.items()}})
 inf=[a.root/'visualizations/inference'/Path(r['subject'])/r['sequence']/r['frame']/'camA_triptych.png' for r in rows];montage(inf,a.root/'visualizations/montages/inference_all.png')
 for k in ['K1','K2','K3']:
  xs=[a.root/'visualizations/evaluation'/Path(r['subject'])/r['sequence']/r['frame']/k/'triptych.png' for r in rows];montage(xs,a.root/f'visualizations/montages/evaluation_{k}_all.png')
 ok=all(f['exists'] for c in checks for fs in c['groups'].values() for f in fs);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps({'status':'PASS' if ok else 'FAIL','frames':len(rows),'expected_inference_packages':len(rows),'expected_evaluation_packages_per_camera':len(rows),'expected_geometry_packages':len(rows),'checks':checks},indent=2)+'\n')
if __name__=='__main__':main()
