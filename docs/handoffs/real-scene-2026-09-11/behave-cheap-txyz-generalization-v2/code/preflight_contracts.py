"""Dependency-light preflight contracts shared by runner and synthetic tests."""
import collections, hashlib, json
from pathlib import Path

def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def source_tree_sha(root):
    paths=sorted([*Path(root).rglob('*.py'),*Path(root).rglob('*.yaml')])
    lines=[f"{file_sha(path)}  ./{path.relative_to(root).as_posix()}\n" for path in paths]
    return hashlib.sha256(''.join(lines).encode()).hexdigest()
def verify_assets(args):
    freeze=json.loads(args.asset_freeze.read_text())['assets']
    actual={'official_checkpoint':file_sha(args.checkpoint),'model_config':file_sha(args.model_config),'mhr_model':file_sha(args.mhr),'surface_anchors':file_sha(args.anchors),'surface_metrics_py':file_sha(args.surface_metrics),'sam3d_source':source_tree_sha(args.sam_repo)}
    expected={key:(freeze[key].get('sha256') or freeze[key].get('python_yaml_tree_hash')) for key in actual}
    bad={key:{'expected':expected[key],'actual':value} for key,value in actual.items() if value!=expected[key]}
    if bad:raise RuntimeError('ASSET_FREEZE_MISMATCH '+json.dumps(bad))
def assert_qa_coverage(manifest,qa):
    grouped=collections.defaultdict(list)
    for row in qa['rows']:grouped[row['sequence']].append(row)
    for sequence in {row['sequence'] for row in manifest['rows']}:
        rows=grouped.get(sequence,[]);targets={row['target'] for row in rows if row.get('target') and row.get('pass')};overlap=any(row.get('world_person_cloud_overlap') and row.get('pass') for row in rows)
        if targets!={'K1','K2','K3'} or not overlap:raise RuntimeError(f'CAMERA_QA_COVERAGE_MISSING {sequence}: targets={targets}, overlap={overlap}')
def validate_runner_manifest(manifest):
    if manifest.get('status')!='FROZEN_BEFORE_MODEL_RUN':raise RuntimeError('MANIFEST_NOT_FROZEN')
    if manifest.get('role') not in {'CONSUMED_SMOKE_ONLY','FRESH_FORMAL_GENERALIZATION'}:raise RuntimeError('MANIFEST_ROLE_INVALID')
def classify_outcome(deltas,fallback,epsilon=1e-9):
    if fallback:return 'FALLBACK_OFFICIAL'
    signs=[-1 if value < -epsilon else (1 if value > epsilon else 0) for value in deltas];improved=signs.count(-1);degraded=signs.count(1)
    if improved==3:return 'ALL_3_IMPROVED'
    if degraded==3:return 'ALL_3_DEGRADED'
    if improved==0 and degraded==0:return 'ALL_3_UNCHANGED'
    return f'{improved}_IMPROVED_{signs.count(0)}_UNCHANGED_{degraded}_DEGRADED'
