"""Record the actual runtime and derived nested anchor identities."""
import json,os,platform,sys,time
from importlib.metadata import version
import numpy as np
import torch
from common import W,G,sha,dump
from projection import nested_ids


def main():
    ids=nested_ids();p=W/'ANCHOR_SUBSETS.npz'
    np.savez_compressed(p,**{'indices_%d'%n:a for n,a in ids.items()})
    dump(W/'ANCHOR_SUBSETS.json',dict(status='DERIVED_FROM_PRERUN_FROZEN_FUNCTION',npz_sha256=sha(p),
        source_anchor_sha256=sha(G/'assets/anchors.npz'),indices={str(n):a.tolist() for n,a in ids.items()},
        nested_256_in_1024=bool(np.isin(ids[256],ids[1024]).all()),nested_1024_in_4096=bool(np.isin(ids[1024],ids[4096]).all())))
    dump(W/'RUNTIME.json',dict(time_unix=time.time(),platform=platform.platform(),python=sys.version,
        torch=torch.__version__,cuda=torch.version.cuda,numpy=np.__version__,scipy=version('scipy'),nvdiffrast=version('nvdiffrast'),
        cpu_count=os.cpu_count(),gpu_names=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        fit_GPU_indices=[0,1,2],extra_cache_QA_GPU_index=3,evaluation_CPU_workers=32,
        execution_freeze_mtime_unix=(W/'EXECUTION_FREEZE.json').stat().st_mtime))


if __name__=='__main__':main()
