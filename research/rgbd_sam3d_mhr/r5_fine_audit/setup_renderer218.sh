#!/usr/bin/env bash
set -euo pipefail
work=/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1
runtime=/raid5/xuhd/rgbd_sam3d/runtime218
export http_proxy= https_proxy= all_proxy= HTTP_PROXY= HTTPS_PROXY= ALL_PROXY=
export NO_PROXY='*' no_proxy='*'
export PATH="$runtime/env/bin:$PATH"
export CUDA_HOME="$runtime/env"
export CXX="$runtime/env/bin/x86_64-conda-linux-gnu-g++"
export CC="$runtime/env/bin/x86_64-conda-linux-gnu-gcc"
export LD_LIBRARY_PATH="$runtime/env/lib:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST=7.5 MAX_JOBS=4
export CPATH="$(python -c 'import glob; print(":".join(glob.glob("/raid5/xuhd/rgbd_sam3d/runtime218/env/lib/python3.10/site-packages/nvidia/*/include")))')"
python -c "import zipfile; zipfile.ZipFile('$work/code/nvdiffrast_source.zip').extractall('$work/code')"
python -m pip install --no-build-isolation "$work/code/nvdiffrast-main"
CUDA_VISIBLE_DEVICES=0 python -u "$work/code/renderer_probe_218.py"
