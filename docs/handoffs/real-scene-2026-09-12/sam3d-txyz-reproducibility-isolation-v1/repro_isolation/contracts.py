import hashlib,json,math,statistics,numpy as np
def classify_numeric(runs,contract):
 a=np.asarray(runs,float);rng=float(a.max()-a.min());sd=float(a.std());tol=contract['absolute_tolerance'];return {'range':rng,'sd':sd,'status':'STABLE' if rng<=tol else 'CAUTION' if rng<=contract['caution_tolerance'] else 'UNSTABLE'}
def classify_bool(values,contract):
 rate=min(sum(values),len(values)-sum(values))/len(values);return {'flip_rate':rate,'status':'STABLE' if rate<=contract['max_flip_rate'] else 'UNSTABLE'}
def heldout(cameras):
 ds=[cameras[k]['txyz']['median_mm']-cameras[k]['official']['median_mm'] for k in ('K1','K2','K3')];return {'mean_delta_mm':float(np.mean(ds)),'median_delta_mm':float(np.median(ds)),'worst_camera_delta_mm':max(ds),'best_camera_delta_mm':min(ds),'number_cameras_improved':sum(x<0 for x in ds)}
def hierarchical(rows,key):
 frame=[r[key] for r in rows];seq={};sub={}
 for r in rows:seq.setdefault(r['sequence'],[]).append(r[key]);sub.setdefault(r['subject'],[]).append(r[key])
 return {'frame_level':frame,'sequence_level':{k:statistics.mean(v) for k,v in seq.items()},'subject_level':{k:statistics.mean(v) for k,v in sub.items()},'iid_inference_allowed':False}
def matched(target,rows):
 rank={'GROUP_A':0,'GROUP_B':1};c=[r for r in rows if r['subject']==target['subject'] and r['sequence']==target['sequence'] and r['group'] in rank];c.sort(key=lambda r:(rank[r['group']],abs(r['frame_index']-target['frame_index']),r['frame_index']));return c[0] if c else None
def deployment_provenance(mask_source,bbox_source):return {'mask_source':mask_source,'bbox_source':bbox_source,'deployment_ready':mask_source=='predicted' and bbox_source=='detector'}
