"""Snapshot existing algorithms; preserve all historical experiment directories."""
from pathlib import Path
import hashlib, json, shutil

DELIVERY = Path(__file__).resolve().parents[1]
PROJECT = DELIVERY.parents[3]
OLD = PROJECT/'output/pressurepose_prone_review'
CODE = DELIVERY/'code'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    sources = [('run_pressurepose_three_methods.py','baseline_v1.py'),
               ('surface_metrics.py','surface_metrics.py'),
               ('l1_fit/l1_fit.py','l1_fit.py'), ('l1_fit/bed_io.py','bed_io.py')]
    snap = []
    for src, dst in sources:
        p=OLD/src; out=CODE/dst
        shutil.copyfile(p,out)
        snap.append(dict(original=str(p), copy=dst, sha256=sha(p)))
    # Only correct the old ray evaluator and inaccurate module description; D/rigid unchanged.
    p=CODE/'l1_fit.py'; text=p.read_text(encoding='utf8')
    start=text.index('"""'); end=text.index('"""',start+3)+3
    text='"""Historical Rigid/D algorithms, unchanged. D is a 3D vector displacement\nwith soft tangential penalty and graph-Laplacian regularization; not strict normal-only.\nRay evaluation is replaced by the independently tested metrics_v2 implementation.\n"""'+text[end:]
    text=text[:text.index('def ray_depth_residual(')]+'from metrics_v2 import ray_depth_residual\n'
    p.write_text(text,encoding='utf8')
    for src,dst in [('preview/geometry_qa/pressurepose_k0_calibration_qa.json','CALIBRATION_INPUT.json'),
                    ('preview/geometry_qa/person_bbox_manifest.json','BBOX_INPUT.json'),
                    ('preview/extraction_manifest.json','RAW_INPUT_IDENTITY.json')]:
        shutil.copyfile(OLD/src,DELIVERY/dst)
    posterior=PROJECT/'docs/handoffs/real-scene-2026-09-21/posterior-torso-v1/candidate_posterior_mask.json'
    shutil.copyfile(posterior,DELIVERY/'POSTERIOR_FACE_MASK.json')
    (DELIVERY/'ALGORITHM_SNAPSHOT.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(delivery=str(DELIVERY), snapshots=len(snap))))

if __name__=='__main__': main()
