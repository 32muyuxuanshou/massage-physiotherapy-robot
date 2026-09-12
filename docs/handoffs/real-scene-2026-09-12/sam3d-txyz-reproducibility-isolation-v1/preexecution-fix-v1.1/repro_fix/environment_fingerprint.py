import argparse,json,os,platform,random
from pathlib import Path
def capture(seeds,scipy_workers):
 import cv2,numpy as np,scipy,torch
 try:import timm;timm_version=timm.__version__
 except Exception:timm_version=None
 gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None;cap=list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None
 return {'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'pytorch':torch.__version__,'torch_cuda':torch.version.cuda,'cuda_runtime':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),'gpu':gpu,'gpu_compute_capability':cap,'driver':os.environ.get('NVIDIA_DRIVER_VERSION'),'opencv':cv2.__version__,'timm':timm_version,'torch_deterministic':torch.are_deterministic_algorithms_enabled(),'cudnn_benchmark':torch.backends.cudnn.benchmark,'cudnn_deterministic':torch.backends.cudnn.deterministic,'matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32,'cudnn_allow_tf32':torch.backends.cudnn.allow_tf32,'float32_matmul_precision':torch.get_float32_matmul_precision(),'cublas_workspace_config':os.environ.get('CUBLAS_WORKSPACE_CONFIG'),'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'omp_threads':os.environ.get('OMP_NUM_THREADS'),'mkl_threads':os.environ.get('MKL_NUM_THREADS'),'pythonhashseed':os.environ.get('PYTHONHASHSEED'),'random_seed':seeds['random'],'numpy_seed':seeds['numpy'],'torch_seed':seeds['torch'],'cuda_seed':seeds['cuda'],'scipy_workers':scipy_workers}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,default=20260912);p.add_argument('--scipy-workers',type=int,default=-1);a=p.parse_args();s={k:a.seed for k in ('random','numpy','torch','cuda')};a.output.write_text(json.dumps(capture(s,a.scipy_workers),indent=2)+'\n')
if __name__=='__main__':main()
