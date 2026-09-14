import argparse,hashlib,json
from pathlib import Path
from .hashing import file_sha

def tree_sha(root,patterns=('*.py','*.yaml')):
 root=Path(root);files=sorted({p for pattern in patterns for p in root.rglob(pattern)})
 lines=''.join(f"{file_sha(p)}  ./{p.relative_to(root).as_posix()}\n" for p in files)
 return hashlib.sha256(lines.encode()).hexdigest()
def bundle_sha(root,relative_files):
 root=Path(root);lines=''.join(f"{file_sha(root/p)}  ./{Path(p).as_posix()}\n" for p in sorted(relative_files))
 return hashlib.sha256(lines.encode()).hexdigest()
def verify_assets(paths,freeze):
 expected=freeze['assets'];observed={
  'official_checkpoint_sha256':file_sha(paths['official_checkpoint']),
  'mhr_model_sha256':file_sha(paths['mhr_model']),
  'surface_anchors_sha256':file_sha(paths['surface_anchors']),
  'surface_metrics_sha256':file_sha(paths['surface_metrics']),
  'sam3d_source_tree_sha256':tree_sha(paths['sam3d_repo']),
  'v23_helper_code_sha256':file_sha(Path(paths['v23_code'])/'behave_v2_io.py')}
 gate=freeze['formal_runtime_gate'];observed.update({
  'formal_manifest_sha256':file_sha(paths['formal_manifest']),
  'txyz_implementation_sha256':file_sha(paths['txyz_implementation']),
  'camera_calibration_bundle_sha256':bundle_sha(paths['calibration_root'],paths['calibration_relative_files'])})
 expected_all={**expected,**{k:gate[k] for k in ('formal_manifest_sha256','txyz_implementation_sha256','camera_calibration_bundle_sha256')}}
 mismatches=[{'field':k,'expected':expected_all[k],'observed':v} for k,v in observed.items() if expected_all[k]!=v]
 return {'status':'PASS_RUNTIME_ASSET_FREEZE' if not mismatches else 'ASSET_FREEZE_MISMATCH','observed':observed,'mismatches':mismatches}
def main():
 p=argparse.ArgumentParser();p.add_argument('--paths',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=verify_assets(json.loads(a.paths.read_text()),json.loads(a.freeze.read_text()));a.output.write_text(json.dumps(r,indent=2)+'\n');raise SystemExit(0 if r['status'].startswith('PASS_') else 2)
if __name__=='__main__':main()
