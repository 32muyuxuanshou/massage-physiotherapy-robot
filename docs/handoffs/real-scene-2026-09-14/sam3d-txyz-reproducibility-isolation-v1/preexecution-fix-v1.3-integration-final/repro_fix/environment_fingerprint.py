import argparse,json,os,platform,random,subprocess
from pathlib import Path
def apply_reproducibility_environment(seed):
 import numpy as np
 random.seed(seed);np.random.seed(seed)
 try:
  import torch;torch.manual_seed(seed)
  if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
  torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 except ImportError:pass
 return {'requested_seed':seed,'seed_applied':True,'deterministic_algorithms_requested':True}
def capture(seeds,scipy_workers,seed_applied=False,mode='CONTROLLED'):
 import cv2,numpy as np,scipy,torch
 try:import timm;timm_version=timm.__version__
 except Exception:timm_version=None
 gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None;cap=list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None
 try:driver=subprocess.check_output(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],text=True,stderr=subprocess.DEVNULL).splitlines()[0]
 except Exception:driver=os.environ.get('NVIDIA_DRIVER_VERSION')
 return {'mode':mode,'requested_seed':seeds['random'] if mode=='CONTROLLED' else None,'seed_applied':seed_applied,'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pytorch':torch.__version__,'torch_cuda':torch.version.cuda,'cuda_runtime':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),'gpu':gpu,'gpu_compute_capability':cap,'driver':driver,'opencv':cv2.__version__,'timm':timm_version,'torch_deterministic':torch.are_deterministic_algorithms_enabled(),'cudnn_benchmark':torch.backends.cudnn.benchmark,'cudnn_deterministic':torch.backends.cudnn.deterministic,'matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32,'cudnn_allow_tf32':torch.backends.cudnn.allow_tf32,'float32_matmul_precision':torch.get_float32_matmul_precision(),'cublas_workspace_config':os.environ.get('CUBLAS_WORKSPACE_CONFIG'),'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'omp_threads':os.environ.get('OMP_NUM_THREADS'),'mkl_threads':os.environ.get('MKL_NUM_THREADS'),'pythonhashseed':os.environ.get('PYTHONHASHSEED'),'random_seed':seeds['random'],'numpy_seed':seeds['numpy'],'torch_seed':seeds['torch'],'cuda_seed':seeds['cuda'],'scipy_workers':scipy_workers}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,default=20260912);p.add_argument('--mode',choices=['CONTROLLED','UNSEEDED_DIAGNOSTIC'],default='CONTROLLED');p.add_argument('--scipy-workers',type=int,default=-1);a=p.parse_args();applied=False
 if a.mode=='CONTROLLED':apply_reproducibility_environment(a.seed);applied=True
 s={k:a.seed if applied else None for k in ('random','numpy','torch','cuda')};a.output.write_text(json.dumps(capture(s,a.scipy_workers,applied,a.mode),indent=2)+'\n')
if __name__=='__main__':main()
