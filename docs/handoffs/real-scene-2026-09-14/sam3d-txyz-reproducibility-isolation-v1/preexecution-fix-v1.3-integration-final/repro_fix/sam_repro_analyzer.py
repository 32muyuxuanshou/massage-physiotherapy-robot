import numpy as np

def distribution(values):
 x=np.asarray(values,float);return {'mean_mm':float(x.mean()),'median_mm':float(np.median(x)),'p90_mm':float(np.percentile(x,90)),'p95_mm':float(np.percentile(x,95)),'max_mm':float(x.max())}
def compare_arrays(a,b):
 va,ca,aa=a['vertices'],a['cam_t'],a['anchors'];vb,cb,ab=b['vertices'],b['cam_t'],b['anchors']
 vertex=np.linalg.norm(va-vb,axis=-1)*1000;anchor=np.linalg.norm(aa-ab,axis=-1)*1000;delta=(cb-ca)*1000
 return {'vertices':distribution(vertex),'anchors':distribution(anchor),'cam_t':{'dx_mm':float(delta[0]),'dy_mm':float(delta[1]),'dz_mm':float(delta[2]),'norm_mm':float(np.linalg.norm(delta))}}
def analyze(*_args,**_kwargs):
 raise RuntimeError('HISTORICAL_RUN_A_COMPLETE_SCHEMA_FORBIDDEN_USE_SAM_REPRO_ANALYZER_V2')
