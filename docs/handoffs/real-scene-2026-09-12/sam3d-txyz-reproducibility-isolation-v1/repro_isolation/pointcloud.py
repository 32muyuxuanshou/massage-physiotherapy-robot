import hashlib,numpy as np
def sha(a):return hashlib.sha256(np.ascontiguousarray(a).view(np.uint8)).hexdigest()
def reconstruct(depth,mask,table):
 good=(depth>0)&(mask>127);r=np.dstack([table,np.ones(table.shape[:2],table.dtype)]);points=r[good].astype(float)*depth[good,None].astype(float)/1000.
 return points,{'shape':list(points.shape),'dtype':str(points.dtype),'order':'C' if points.flags.c_contiguous else 'OTHER','sha256':sha(points)}
