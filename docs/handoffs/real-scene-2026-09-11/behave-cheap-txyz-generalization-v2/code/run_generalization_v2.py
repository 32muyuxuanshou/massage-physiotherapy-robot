"""Execute the frozen V2 batch after manifest and camera-QA approval."""
import argparse,collections,csv,hashlib,json,sys,time
from pathlib import Path
import cv2,numpy as np,torch
from scipy.spatial import cKDTree
from behave_v2_io import read_camera,transform_between
from preflight_contracts import assert_qa_coverage,classify_outcome,validate_runner_manifest,verify_assets

N_ANCHORS=16384;ITER=6;TRIM=.20;STEP=.05;TOTAL=.17788820176363325
def depth_points(depth,mask,table):
 good=(depth>0)&(mask>127);r=np.dstack([table,np.ones(table.shape[:2],table.dtype)])
 return r[good].astype(float)*depth[good,None].astype(float)/1000.
def fit_txyz(points,anchors):
 t=np.zeros(3);pts=points;trace=[]
 for i in range(ITER):
  dist,near=cKDTree(anchors+t).query(pts,workers=-1);keep=dist<=np.quantile(dist,1-TRIM)
  step=np.clip(np.median(pts[keep]-(anchors+t)[near[keep]],axis=0),-STEP,STEP);t+=step;trace.append({'iteration':i+1,'step_m':step.tolist(),'t_m':t.tolist()})
 return t,trace
def sample_points(p,key,n=5000):
 if len(p)<=n:return p
 rng=np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:16],16));return p[np.sort(rng.choice(len(p),n,False))]
def summary(d):
 d=np.asarray(d)*1000
 return {'count':len(d),'mean_mm':float(d.mean()),'median_mm':float(np.median(d)),'p90_mm':float(np.percentile(d,90)),'p95_mm':float(np.percentile(d,95)),'p99_mm':float(np.percentile(d,99)),'max_mm':float(d.max()),'coverage_50mm':float(np.mean(d<50)),'above_500mm_count':int(np.sum(d>500)),'above_500mm_ratio':float(np.mean(d>500))}
def project(v,K,dist):return cv2.projectPoints(v[:,None],np.zeros(3),np.zeros(3),K,dist)[0].reshape(-1,2)
def render(rgb,v,f,K,dist):
 uv=project(v,K,dist);tri=v[f];order=np.argsort(tri[:,:,2].mean(1))[::-1];mesh=rgb.copy();H,W=rgb.shape[:2]
 n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.linalg.norm(n,axis=1,keepdims=True).clip(1e-8);shade=.62+.34*np.abs(n@np.array([-.25,-.45,-.86]))
 for i in order:
  q=np.rint(uv[f[i]]).astype(np.int32)
  if np.all((q[:,0]<0)|(q[:,0]>=W)|(q[:,1]<0)|(q[:,1]>=H)):continue
  c=int(np.clip(245*shade[i],150,245));cv2.fillConvexPoly(mesh,q,(c,c,c),cv2.LINE_AA);cv2.polylines(mesh,[q],True,(120,130,140),1,cv2.LINE_AA)
 m=np.any(mesh!=rgb,2);out=rgb.copy();out[m]=(rgb[m]*.12+mesh[m]*.88).astype(np.uint8);return out
def save(path,rgb):path.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(path),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
def panel(images,labels,footer=''):
 out=[]
 for x,l in zip(images,labels):
  x=cv2.resize(x,(640,480));cv2.rectangle(x,(0,0),(640,38),(250,250,250),-1);cv2.putText(x,l,(12,26),0,.65,(20,25,30),2,cv2.LINE_AA);out.append(x)
 z=np.hstack(out)
 if footer:
  b=np.full((45,z.shape[1],3),248,np.uint8);cv2.putText(b,footer,(15,30),0,.62,(25,35,50),2,cv2.LINE_AA);z=np.vstack([z,b])
 return z
def residual_png(sensor,mesh,mask,max_mm=100):
 common=(sensor>0)&(mesh>0)&(mask>127);e=np.zeros(sensor.shape,np.float32);e[common]=np.abs(sensor[common]-mesh[common])*1000
 h=cv2.applyColorMap(np.clip(e/max_mm*255,0,255).astype(np.uint8),cv2.COLORMAP_TURBO);h[~common]=[35,35,35];return cv2.cvtColor(h,cv2.COLOR_BGR2RGB),common
def rendered_pair(sensor,official,txyz,mask):
 valid=(sensor>0)&(mask>127);co=valid&(official>0);ct=valid&(txyz>0);common=co&ct
 def s(mesh,support):return summary(np.abs(mesh[support]-sensor[support])) if support.any() else None
 return {'official':s(official,co),'txyz':s(txyz,ct),'common_official':s(official,common),'common_txyz':s(txyz,common),'official_coverage':float(co.sum()/max(1,valid.sum())),'txyz_coverage':float(ct.sum()/max(1,valid.sum())),'common_coverage':float(common.sum()/max(1,valid.sum()))}
def undistort_depth_mask(depth,mask,K,dist):
 """Map BEHAVE's distorted registered color-domain depth to pinhole K using nearest-neighbor sampling."""
 h,w=depth.shape;mx,my=cv2.initUndistortRectifyMap(K,dist,None,K,(w,h),cv2.CV_32FC1)
 return cv2.remap(depth,mx,my,cv2.INTER_NEAREST,borderValue=0),cv2.remap(mask,mx,my,cv2.INTER_NEAREST,borderValue=0)
def viewer(path,points,vo,vc,title):
 def take(x):return x[np.linspace(0,len(x)-1,min(2500,len(x)),dtype=int)]
 p,o,c=map(take,[points,vo,vc]);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(f'''<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script><div id="v" style="width:100vw;height:96vh"></div><script>Plotly.newPlot('v',[{{name:'Depth',type:'scatter3d',mode:'markers',x:{p[:,0].tolist()},y:{p[:,1].tolist()},z:{p[:,2].tolist()},marker:{{size:1,color:'gray'}}}},{{name:'Official',type:'scatter3d',mode:'markers',x:{o[:,0].tolist()},y:{o[:,1].tolist()},z:{o[:,2].tolist()},marker:{{size:1,color:'red'}}}},{{name:'Txyz',type:'scatter3d',mode:'markers',x:{c[:,0].tolist()},y:{c[:,1].tolist()},z:{c[:,2].tolist()},marker:{{size:1,color:'blue'}}}}],{{title:{json.dumps(title)},scene:{{aspectmode:'data'}}}})</script>''')
def static_geometry(root,points,vo,vc):
 for name,(ax,ay) in {'front':(0,1),'side':(2,1),'top':(0,2)}.items():
  canvas=np.full((700,700,3),248,np.uint8);sets=[(sample_points(points,name+'p',3000),(120,120,120)),(sample_points(vo,name+'o',3000),(210,55,55)),(sample_points(vc,name+'c',3000),(45,90,220))];allp=np.vstack([x for x,_ in sets]);lo,hi=np.percentile(allp[:,[ax,ay]],[1,99],axis=0);span=np.maximum(hi-lo,1e-6)
  for xyz,color in sets:
   uv=((xyz[:,[ax,ay]]-lo)/span*620+40).astype(int);uv[:,1]=699-uv[:,1];good=np.all((uv>=0)&(uv<700),axis=1)
   for x,y in uv[good]:cv2.circle(canvas,(x,y),1,color,-1)
  save(root/f'{name}.png',canvas)
def main():
 p=argparse.ArgumentParser()
 for n in ['manifest','sequences','calibs','sam-repo','checkpoint','mhr','anchors','camera-qa','out']:p.add_argument('--'+n,type=Path,required=True)
 for n in ['model-config','surface-metrics','asset-freeze']:p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();qa=json.loads(a.camera_qa.read_text());assert qa['status']=='PASS';man=json.loads(a.manifest.read_text());validate_runner_manifest(man);assert_qa_coverage(man,qa);verify_assets(a)
 sys.path[:0]=[str(a.sam_repo),str(a.surface_metrics.parent)];from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator;from sam_3d_body.data.utils.prepare_batch import prepare_batch;from sam_3d_body.utils import recursive_to;from surface_metrics import point_to_triangle_distances,render_depth
 model,cfg=load_sam_3d_body(str(a.checkpoint),device='cuda',mhr_path=str(a.mhr));model.eval();est=SAM3DBodyEstimator(model,cfg);faces=model.head_pose.faces.cpu().numpy().astype(np.int64);az=np.load(a.anchors);fi,bc=az['face_index'],az['barycentric'].astype(float);rows=[];torch.cuda.reset_peak_memory_stats()
 for spec in man['rows']:
  sid=f"{spec['subject']}/{spec['sequence']}/{spec['frame']}";frame=a.sequences/spec['sequence']/spec['frame'];cams=[read_camera(a.calibs,spec['sequence'],k) for k in range(4)];rgbs=[];depths=[];masks=[];points=[]
  for k in range(4):
   rgbs.append(cv2.cvtColor(cv2.imread(str(frame/f'k{k}.color.jpg')),cv2.COLOR_BGR2RGB));depths.append(cv2.imread(str(frame/f'k{k}.depth.png'),-1));masks.append(cv2.imread(str(frame/f'k{k}.person_mask.jpg'),0));points.append(depth_points(depths[-1],masks[-1],cams[k]['pointcloud_table']))
  y,x=np.where(masks[0]>127);bbox=np.array([[max(0,x.min()-25),max(0,y.min()-25),min(rgbs[0].shape[1]-1,x.max()+25),min(rgbs[0].shape[0]-1,y.max()+25)]],np.float32);batch=recursive_to(prepare_batch(rgbs[0],est.transform,bbox,None,None),'cuda');batch['cam_int']=torch.as_tensor(cams[0]['K'][None],device='cuda').to(batch['img']);torch.cuda.synchronize();t0=time.perf_counter();model._initialize_batch(batch)
  with torch.inference_mode():pred=model.forward_step(batch,decoder_type='body')['mhr']
  torch.cuda.synchronize();sam_ms=(time.perf_counter()-t0)*1000;vo=(pred['pred_vertices']+pred['pred_cam_t'][:,None])[0].cpu().numpy();anchors=(vo[faces[fi]]*bc[:,:,None]).sum(1);t0=time.perf_counter();raw,trace=fit_txyz(points[0],anchors);t_ms=(time.perf_counter()-t0)*1000;fallback=np.linalg.norm(raw)>TOTAL;applied=np.zeros(3) if fallback else raw;vc=vo+applied
  inf=a.out/'visualizations/inference'/sid;oa,ta=render(rgbs[0],vo,faces,cams[0]['K'],cams[0]['dist']),render(rgbs[0],vc,faces,cams[0]['K'],cams[0]['dist']);footer=f"Tx={raw[0]*1000:+.1f} Ty={raw[1]*1000:+.1f} Tz={raw[2]*1000:+.1f} |T|={np.linalg.norm(raw)*1000:.1f} mm";save(inf/'camA_rgb_original.png',rgbs[0]);save(inf/'camA_official_overlay.png',oa);save(inf/'camA_txyz_overlay.png',ta);save(inf/'camA_triptych.png',panel([rgbs[0],oa,ta],['Camera A RGB','Official SAM3D','Camera-A Txyz'],footer))
  vec=np.full((340,700,3),248,np.uint8);scale=2.;colors=[(210,70,50),(50,160,70),(40,90,220)]
  for j,(label,value,color) in enumerate(zip(('Tx','Ty','Tz'),raw*1000,colors)):
   y=100+j*75;cv2.line(vec,(350,y),(350+int(value*scale),y),color,10);cv2.circle(vec,(350+int(value*scale),y),8,color,-1);cv2.putText(vec,f'{label} {value:+.1f} mm',(20,y+8),0,.65,color,2,cv2.LINE_AA)
  cv2.putText(vec,footer,(20,40),0,.65,(25,35,50),2,cv2.LINE_AA);save(inf/'camA_txyz_vector.png',vec);geo=a.out/'visualizations/geometry_3d'/sid;viewer(geo/'viewer.html',points[0],vo,vc,sid);static_geometry(geo,points[0],vo,vc)
  delta=vc-vo;translation_qa={'max_vertex_delta_deviation_m':float(np.abs(delta-delta.mean(0)).max()),'faces_identical':True,'pose_shape_scale_rotation_recomputed':False,'pass':bool(np.abs(delta-delta.mean(0)).max()<1e-7)}
  rec={'spec':spec,'Txyz_m':raw.tolist(),'applied_Txyz_m':applied.tolist(),'fallback':fallback,'translation_only_qa':translation_qa,'runtime_sam_ms':sam_ms,'runtime_txyz_ms':t_ms,'runtime_total_ms':sam_ms+t_ms,'cameras':{}}
  for k in [1,2,3]:
   ob,tb=transform_between(vo,cams[0],cams[k]),transform_between(vc,cams[0],cams[k]);po=sample_points(points[k],sid+f'K{k}');mo=summary(point_to_triangle_distances(po,ob,faces));mt=summary(point_to_triangle_distances(po,tb,faces));ud,um=undistort_depth_mask(depths[k],masks[k],cams[k]['K'],cams[k]['dist']);do=render_depth(ob,faces,cams[k]['K'],*ud.shape);dt=render_depth(tb,faces,cams[k]['K'],*ud.shape);sensor=ud/1000.;rd=rendered_pair(sensor,do,dt,um);ho,co=residual_png(sensor,do,um);ht,ct=residual_png(sensor,dt,um);ev=a.out/f'visualizations/evaluation/{sid}/K{k}';oo,tt=render(rgbs[k],ob,faces,cams[k]['K'],cams[k]['dist']),render(rgbs[k],tb,faces,cams[k]['K'],cams[k]['dist']);save(ev/'rgb_original.png',rgbs[k]);save(ev/'official_from_A_overlay.png',oo);save(ev/'txyz_from_A_overlay.png',tt);save(ev/'triptych.png',panel([rgbs[k],oo,tt],[f'Held-out K{k}',f'Official from A',f'Txyz from A']));save(ev/'residual_official.png',ho);save(ev/'residual_txyz.png',ht);save(ev/'residual_comparison.png',np.hstack([ho,ht]));rec['cameras'][f'K{k}']={'official':mo,'txyz':mt,'rendered_depth_pinhole_undistorted_sensor':rd,'median_delta_mm':mt['median_mm']-mo['median_mm']}
  deltas=[rec['cameras'][f'K{k}']['median_delta_mm'] for k in [1,2,3]];rec['multicamera_outcome']=classify_outcome(deltas,fallback);sl=[footer]+[f"K{k}: {rec['cameras'][f'K{k}']['official']['median_mm']:.1f}->{rec['cameras'][f'K{k}']['txyz']['median_mm']:.1f} mm; P95 {rec['cameras'][f'K{k}']['official']['p95_mm']:.1f}->{rec['cameras'][f'K{k}']['txyz']['p95_mm']:.1f}" for k in [1,2,3]]+[rec['multicamera_outcome']];canvas=np.full((250,1200,3),248,np.uint8)
  for j,line in enumerate(sl):cv2.putText(canvas,line,(20,42+j*42),0,.65,(25,35,50),2,cv2.LINE_AA)
  save(a.out/'visualizations/metrics_summary'/sid/'metrics_summary.png',canvas);rows.append(rec);(a.out/'raw').mkdir(parents=True,exist_ok=True);(a.out/'raw'/f"{spec['sequence']}_{spec['frame'].replace('.','_')}.json").write_text(json.dumps(rec,indent=2)+'\n');print(sid,rec['multicamera_outcome'],flush=True)
 (a.out/'report').mkdir(parents=True,exist_ok=True);(a.out/'report/per_frame_results.json').write_text(json.dumps(rows,indent=2)+'\n');(a.out/'report/runtime.json').write_text(json.dumps({'peak_cuda_allocated_mb':torch.cuda.max_memory_allocated()/2**20},indent=2)+'\n')
if __name__=='__main__':main()
