import os,platform
REQUIRED=('python','pytorch','cuda','cudnn','gpu','driver','numpy','scipy','opencv','timm','torch_deterministic','cudnn_benchmark','tf32','omp_threads','mkl_threads','pythonhashseed','random_seed','numpy_seed','torch_seed','cuda_seed')
def validate(x):
 missing=[k for k in REQUIRED if k not in x]
 if missing:raise ValueError('ENVIRONMENT_FINGERPRINT_INCOMPLETE '+repr(missing))
 return True
def classify_missing(names,parameters,buffers):
 return {n:('TRAINABLE_PARAMETER' if n in parameters else 'BUFFER' if n in buffers else 'STATIC_MHR_ASSET' if '.mhr.' in n or 'character_torch' in n else 'OTHER') for n in names}
