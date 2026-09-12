import hashlib,json
from pathlib import Path
from .io_v23 import sha256

CALIBRATION_FILES=[f'intrinsics/{k}/{name}' for k in range(4) for name in ('calibration.json','pointcloud_table.npy')]+[f'{date}/config/{k}/config.json' for date in ('Date03','Date05','Date06') for k in range(4)]

def calibration_bundle_sha(root):
    root=Path(root);items=[]
    for relative in sorted(CALIBRATION_FILES):
        path=root/relative
        if not path.is_file():raise FileNotFoundError(path)
        items.append(f'{sha256(path)}  ./{relative}\n')
    return hashlib.sha256(''.join(items).encode()).hexdigest()

def verify(requirements_path,formal_manifest,txyz_source,anchors,calibs):
    expected=json.loads(Path(requirements_path).read_text(encoding='utf-8'))['formal_runtime_gate']
    actual={'formal_manifest_sha256':sha256(formal_manifest),'txyz_implementation_sha256':sha256(txyz_source),'surface_anchors_sha256':sha256(anchors),'camera_calibration_bundle_sha256':calibration_bundle_sha(calibs)}
    mismatches={name:{'expected':expected.get(name),'actual':value} for name,value in actual.items() if expected.get(name)!=value}
    if mismatches:raise RuntimeError('ASSET_FREEZE_MISMATCH '+json.dumps(mismatches))
    return {'status':'PASS_RUNTIME_ASSET_REVERIFICATION','actual':actual,'calibration_file_count':len(CALIBRATION_FILES)}
