#!/usr/bin/env bash
set -euo pipefail
runtime=/raid5/xuhd/rgbd_sam3d/runtime218
mkdir -p "$runtime/downloads" "$runtime/tools"
export http_proxy= https_proxy= all_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY=
export NO_PROXY='*' no_proxy='*'
if [ ! -x "$runtime/tools/bin/micromamba" ]; then
  curl --noproxy '*' --fail --location https://micro.mamba.pm/api/micromamba/linux-64/1.5.8 -o "$runtime/downloads/micromamba.tar.bz2"
  tar -xjf "$runtime/downloads/micromamba.tar.bz2" -C "$runtime/tools" bin/micromamba
fi
"$runtime/tools/bin/micromamba" create -y -r "$runtime/mamba" -p "$runtime/env" \
  -c conda-forge -c nvidia/label/cuda-11.8.0 \
  python=3.10 pip numpy=1.26.4 scipy=1.14 matplotlib-base=3.9 ninja \
  gcc_linux-64=11 gxx_linux-64=11 cuda-nvcc=11.8 cuda-cudart-dev=11.8 cuda-driver-dev=11.8
"$runtime/env/bin/python" -m pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu118
"$runtime/env/bin/python" -m pip install --no-cache-dir roma==1.5.3
CUDA_VISIBLE_DEVICES=0 "$runtime/env/bin/python" -u -c 'import torch; print("TORCH",torch.__version__,"CUDA",torch.version.cuda,"GPU",torch.cuda.get_device_name()); x=torch.randn(128,128,device="cuda"); print("CUDA_MATMUL_PASS",(x@x.T).isfinite().all().item())'
echo GPU218_BASE_READY
