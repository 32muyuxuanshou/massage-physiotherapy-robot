"""Server-side spatial residual audit for already-produced V3 vertices."""
import argparse, json
from pathlib import Path
import cv2, numpy as np
from scipy.spatial import cKDTree

def cam(calibs, seq, k):
    date=seq.split('_',1)[0]; c=json.loads((calibs/'intrinsics'/str(k)/'calibration.json').read_text())['color']; e=json.loads((calibs/date/'config'/str(k)/'config.json').read_text())
    K=np.array([[c['fx'],0,c['cx']],[0,c['fy'],c['cy']],[0,0,1]],float); return K,np.array(c['opencv'][4:],float),np.array(e['rotation'],float).reshape(3,3),np.array(e['translation'],float)
def transform(v, src, dst):
    _,_,R,t=src; _,_,R2,t2=dst; w=np.asarray(v)@R.T+t; return (w-t2)@R2
def depth_points(d,m,table):
    good=(d>0)&(m>127); r=np.dstack([table,np.ones(table.shape[:2],table.dtype)]); return r[good].astype(np.float32)*d[good,None].astype(np.float32)/1000
def project(p,K,dist): return cv2.projectPoints(p.astype(np.float32),np.zeros(3),np.zeros(3),K.astype(np.float32),dist.astype(np.float32))[0].reshape(-1,2)
def dist_to_tri(points,v,faces):
    tri=v[faces]; out=np.full(len(points),np.inf); # nearest vertices is a conservative spatial proxy for region auditing
    q=cKDTree(v).query(points,workers=-1)[0]; return q
def box(mask, cond):
    y,x=np.where(mask>127); x0,x1,y0,y1=x.min(),x.max()+1,y.min(),y.max()+1; w,h=x1-x0,y1-y0; H,W=mask.shape
    if cond=='FULL': return (0,0,W,H)
    if cond=='UPPER': return (max(0,round(x0+.02*w)),max(0,y0),min(W,round(x0+.98*w)),min(H,round(y0+.72*h)))
    return (max(0,round(x0+.20*w)),max(0,round(y0+.15*h)),min(W,round(x0+.80*w)),min(H,round(y0+.72*h)))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,required=True); ap.add_argument('--sequences',type=Path,required=True); ap.add_argument('--calibs',type=Path,required=True); ap.add_argument('--table-root',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args(); out=[]
    for jp in sorted(a.root.glob('Sub*/raw/*/*/*/*.json')):
        r=json.loads(jp.read_text()); s=r['spec']; seq,fr=s['sequence'],s['frame']; src=a.sequences/seq/fr; mask=cv2.imread(str(src/'k0.person_mask.jpg'),0); b=box(mask,r['condition']); cams=[cam(a.calibs,seq,k) for k in range(4)]
        for k in (1,2,3):
            p=depth_points(cv2.imread(str(src/f'k{k}.depth.png'),-1),cv2.imread(str(src/f'k{k}.person_mask.jpg'),0),np.load(a.table_root/str(k)/'pointcloud_table.npy')); p0=transform(p,cams[k],cams[0]); uv=project(p0,cams[0][0],cams[0][1]); inside=(uv[:,0]>=b[0])&(uv[:,0]<b[2])&(uv[:,1]>=b[1])&(uv[:,1]<b[3]); sid=f"{seq}/{fr}/{r['condition']}/K{k}"; z=np.load(jp.with_name(r['condition']+'_vertices.npz')); faces=z['faces']
            for method,keyname in (('Official','Official'),('Txyz','Txyz'),('T+Pose','T_pose')):
                v=transform(z[keyname],cams[0],cams[k]); q=dist_to_tri(p,v,faces)*1000
                for region,sel in [('roi',inside),('outside_roi',~inside)]:
                    if not np.any(sel): continue
                    out.append({'subject':s['subject'],'sequence':seq,'frame':fr,'condition':r['condition'],'camera':f'K{k}','method':method,'region':region,'count':int(sel.sum()),'median_nn_mm':float(np.median(q[sel])),'p95_nn_mm':float(np.percentile(q[sel],95)),'mean_nn_mm':float(np.mean(q[sel]))})
    a.out.mkdir(parents=True,exist_ok=True); (a.out/'SPATIAL_RESIDUAL_AUDIT.json').write_text(json.dumps({'status':'COMPLETE_DESCRIPTIVE','distance':'nearest mesh vertex proxy, not point-to-triangle','region':'K0 projection inside/outside condition ROI','rows':out},indent=2)+'\n')
    print('rows',len(out))
if __name__=='__main__': main()
