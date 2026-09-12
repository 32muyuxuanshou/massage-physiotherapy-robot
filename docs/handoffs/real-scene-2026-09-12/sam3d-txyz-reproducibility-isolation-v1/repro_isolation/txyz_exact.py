import hashlib,numpy as np
from scipy.spatial import cKDTree
ITER=6;TRIM=.20;STEP=.05;TOTAL=.17788820176363325
def digest(a):return hashlib.sha256(np.ascontiguousarray(a).view(np.uint8)).hexdigest()
def fit(points,anchors,workers=-1):
 t=np.zeros(3,dtype=np.float64);trace=[]
 for i in range(ITER):
  dist,near=cKDTree(anchors+t).query(points,workers=workers);threshold=float(np.quantile(dist,.8));keep=dist<=threshold;res=points[keep]-(anchors+t)[near[keep]];step=np.clip(np.median(res,axis=0),-STEP,STEP);norm=np.linalg.norm(res,axis=1);med=float(np.median(norm));t+=step;trace.append({'iteration':i+1,'nearest_hash':digest(near),'keep_hash':digest(keep),'trim_threshold_m':threshold,'step_m':step.tolist(),'step_norm_m':float(np.linalg.norm(step)),'retained_count':int(keep.sum()),'raw_correspondence_count':int(len(dist)),'residual_median_m':med,'residual_mad_m':float(np.median(np.abs(norm-med))),'residual_p90_m':float(np.percentile(norm,90)),'residual_p95_m':float(np.percentile(norm,95))})
 return {'translation_m':t.tolist(),'fallback':bool(np.linalg.norm(t)>TOTAL),'trace':trace,'points_meta':meta(points),'anchors_meta':meta(anchors)}
def meta(a):return {'dtype':str(a.dtype),'shape':list(a.shape),'strides':list(a.strides),'c_contiguous':bool(a.flags.c_contiguous),'f_contiguous':bool(a.flags.f_contiguous),'sha256':digest(a)}
def repeat(points,anchors,n=20,workers=-1):return [fit(points,anchors,workers) for _ in range(n)]
def bitwise_equal(runs):return len({repr(x) for x in runs})==1
