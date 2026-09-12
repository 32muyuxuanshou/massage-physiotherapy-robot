import hashlib,numpy as np
def array_record(value):
 a=np.asarray(value);raw=np.ascontiguousarray(a).tobytes();return {'dtype':str(a.dtype),'shape':list(a.shape),'strides':list(a.strides),'c_contiguous':bool(a.flags.c_contiguous),'f_contiguous':bool(a.flags.f_contiguous),'sha256':hashlib.sha256(raw).hexdigest()}
def file_sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()
def aggregate(records):return hashlib.sha256(''.join(f"{x['key']}\0{x['sha256']}\n" for x in sorted(records,key=lambda x:x['key'])).encode()).hexdigest()
