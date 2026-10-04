"""Read-only server readiness check; no SAM inference and no depth optimization."""
import argparse,sys
from pathlib import Path
from data_v2 import load_json,save_json,sha
from run_comparison import delivery_identity,runtime_assets,assert_baseline_constants,DELIVERY


def main():
    p=argparse.ArgumentParser()
    for key in ['raw','sam-repo','checkpoint','mhr','anchors']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    contract=load_json(DELIVERY/'EXPERIMENT_CONTRACT.json');identity=delivery_identity();assets=runtime_assets(a,contract)
    import torch,baseline_v1
    assert torch.cuda.is_available(),'CUDA is not available in this existing environment'
    assert_baseline_constants(baseline_v1,contract)
    sys.path.insert(0,str(a.sam_repo))
    from sam_3d_body import load_sam_3d_body,SAM3DBodyEstimator
    raw={r['subject']:r['raw_pickle_sha256'] for r in load_json(DELIVERY/'RAW_INPUT_IDENTITY.json')['entries']}
    files=[]
    for s in contract['subjects']:
        path=a.raw/s/'p_select.p';actual=sha(path);assert actual==raw[s]
        files.append(dict(subject=s,path=str(path),sha256=actual))
    save_json(a.report,dict(status='SERVER_PREINFERENCE_READY',delivery_manifest_sha256=identity,
        runtime_assets=assets,raw_files=files,torch=torch.__version__,cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name(),inference_executed=False,
        pending='full MHR loading/parameter roundtrip and four-subject dev stage'))
    print('Read-only server preflight PASS; no model inference performed')


if __name__=='__main__':main()
