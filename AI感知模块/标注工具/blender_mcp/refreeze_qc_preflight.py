"""Reuse immutable geometry when ONLY the independent edge checker changed."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import json
import build_qc_dataset_30 as d
b=d.b

parser=argparse.ArgumentParser()
parser.add_argument("old_root",type=Path)
args=parser.parse_args()
old=args.old_root.resolve()
if b.AI_ROOT.resolve() not in old.parents:
    raise ValueError("Source must be project local")
report=b.read_json(old/"preflight_report.json")
if not report["passed"]:
    raise ValueError("Geometry preflight was not passed")
before=b.read_json(old/"source_hashes.json")
after=d.source_hashes()
changed={path for path in set(before)|set(after) if before.get(path)!=after.get(path)}
if changed != {str(d.EDGES)}:
    raise ValueError("Expected only edge checker change, got "+repr(changed))
index=b.read_json(old/"dataset_index.json")
if len(index)!=30 or b.read_json(old/"dataset_config_v1.json")!=b.read_json(d.CONFIG) or b.sha256(old/d.ATLAS.name)!=b.read_json(d.CONFIG)["atlas_sha256"]:
    raise ValueError("Geometry inputs changed")
for row in index:
    if b.sha256(old/row["snapshot"])!=row["snapshot_sha256"] or b.sha256(old/row["profile"])!=row["profile_sha256"]:
        raise ValueError("Immutable geometry/profile changed")
root=b.AI_ROOT/"outputs"/"交付文件"/datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
root.mkdir(parents=True,exist_ok=False)
for directory in ("snapshots","profiles","camera_contracts"):
    shutil.copytree(old/directory,root/directory)
for directory in ("samples","qc_reports","preflight"):
    (root/directory).mkdir()
for source in (old/"preflight").iterdir():
    if source.is_file() and source.suffix in (".json",".png"):
        shutil.copy2(source,root/"preflight"/source.name)
for name in ("dataset_config_v1.json","dataset_index.json",d.ATLAS.name,"preflight_pose_camera_montage.png"):
    shutil.copy2(old/name,root/name)
b.write_json(root/"source_hashes.json",after)
b.write_json(root/"preflight_source_hashes_original.json",before)
report["reuse_provenance"]={"source":str(old),"changed_code_only":list(changed),"all_30_snapshot_and_profile_hashes_rechecked":True,
    "reason":"Edge verifier now casts the declared camera K, while separately checking float32 projection consistency; geometry, camera, Atlas and generator unchanged.",
    "fresh_sample_generation_required":True}
b.write_json(root/"preflight_report.json",report)
b.write_json(root/"NOT_RELEASED.json",{"reason":"Reused immutable geometry only; all samples need fresh generation and QC."})
print(json.dumps({"root":str(root),"passed_preflight":True},ensure_ascii=False))
