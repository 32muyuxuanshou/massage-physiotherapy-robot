import math,numpy as np
TYPES={'DISTANCE_MM','RATIO_0_1','COUNT','BOOLEAN','VECTOR_MM','HASH_IDENTITY'}
def icc_a1(matrix):
 x=np.asarray(matrix,float);n,k=x.shape
 if n<2 or k<2:raise ValueError('ICC_REQUIRES_TWO_FRAMES_AND_RUNS')
 gm=x.mean();row=x.mean(1);col=x.mean(0);msr=k*np.sum((row-gm)**2)/(n-1);msc=n*np.sum((col-gm)**2)/(k-1);mse=np.sum((x-row[:,None]-col[None,:]+gm)**2)/((n-1)*(k-1));den=msr+(k-1)*mse+k*(msc-mse)/n
 return 1.0 if den==0 and msr==mse==0 else float((msr-mse)/den)
def continuous_stats(matrix):
 x=np.asarray(matrix,float);per=[]
 for row in x:
  med=np.median(row);per.append({'min':float(row.min()),'max':float(row.max()),'range':float(np.ptp(row)),'mean':float(row.mean()),'sd':float(row.std()),'median':float(med),'mad':float(np.median(np.abs(row-med)))})
 within=float(np.mean(np.var(x,axis=1)));between=float(np.var(np.mean(x,axis=1)));return {'within_frame':per,'between_frame_sd':between**.5,'within_between_noise_ratio':float(within/(between+1e-30)),'icc_a1':icc_a1(x)}
def classify(matrix,contract,outcomes=None):
 if outcomes is not None:raise RuntimeError('STABILITY_LEAKAGE_OUTCOME_FORBIDDEN')
 kind=contract['type'];assert kind in TYPES
 if kind=='BOOLEAN':
  x=np.asarray(matrix,bool);flip=float(np.mean(np.any(x!=x[:,:1],axis=1)));return {'boolean_flip_rate':flip,'status':'STABLE' if flip<=contract['stable']['max_flip_rate'] else 'UNSTABLE'}
 if kind=='HASH_IDENTITY':
  x=np.asarray(matrix,object);ok=all(len(set(row))==1 for row in x);return {'identity_rate':float(np.mean([len(set(row))==1 for row in x])),'status':'STABLE' if ok else 'UNSTABLE'}
 s=continuous_stats(matrix);max_range=max(x['range'] for x in s['within_frame']);rel=s['within_between_noise_ratio'];icc=s['icc_a1'];st=contract['stable'];ca=contract['caution'];s['status']='STABLE' if max_range<=st['max_abs_range'] and rel<=st['max_noise_ratio'] and icc>=st['min_icc_a1'] else 'CAUTION' if max_range<=ca['max_abs_range'] and rel<=ca['max_noise_ratio'] and icc>=ca['min_icc_a1'] else 'UNSTABLE';return s
