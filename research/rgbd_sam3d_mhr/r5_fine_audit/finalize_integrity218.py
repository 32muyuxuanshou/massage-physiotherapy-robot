"""Rehash completed diagnostic outputs and unchanged frozen scientific assets."""
import hashlib
import json
from pathlib import Path

WORK=Path('/raid5/xuhd/rgbd_sam3d/r5_fine_negative_update_audit_v1')
EXPECTED={
    'code/frozen_model.py':'2d4cfe42e77951f2d86b4b19cada3d81f560585fbc2ba9fbb74efcf60e75876f',
    'code/frozen_render_losses.py':'94c133ac7b6afbc22d2c3e050f6276e28a4c7022d7cacd17cf50c16ab4f04e2a',
    'previous/geometry/assets/faces.npy':'38a54991de6de3f9b9399e17f265dbda47da25b23fc5cb967276536803374841',
    'previous/geometry/assets/anchors.npz':'e227a6a1d20a4fd285b08f1dfdec06deae9d542f251c7a8ce6138aa34ee406da',
    '../r5_complete_comparison_v1/checkpoints/full_s11_e50_last.pt':'c4b141ede98c8405804e920401ebac982c874cf8f0e542a6e496f09dccdfc750',
    '../r5_complete_comparison_v1/checkpoints/full_s23_e50_last.pt':'2cb095cf3cfb594e97d8ce589e621b432b6009a8a5c68ba10dae69b99fc4577c',
    '../r5_complete_comparison_v1/checkpoints/full_s37_e50_last.pt':'a76926323b1d54d7840cff68f6af1f7fec47f9683614fa940438c23550c3bf2c'}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    assets=[]
    for name,expected in EXPECTED.items():
        p=(WORK/name).resolve();actual=sha(p);assert actual==expected,str(p)
        assets.append(dict(path=str(p),bytes=p.stat().st_size,sha256=actual))
    outputs=[]
    for seed in [11,23,37]:
        result=json.loads((WORK/'query_replay_frozen_coarse'/('s%d'%seed)/'RESULTS.json').read_text())
        assert result['status']=='QUERY_REPLAY_COMPLETE' and len(result['records'])==902
        for r in result['records']:
            p=Path(r['output_file']);actual=sha(p);assert actual==r['output_sha256'],str(p)
            outputs.append(dict(path=str(p.relative_to(WORK)),bytes=p.stat().st_size,sha256=actual))
        surface=json.loads((WORK/'native_surface_tradeoff'/('s%d.json'%seed)).read_text())
        assert surface['status']=='COMPLETE' and len(surface['records'])==400
    result=dict(status='PASS',frozen_assets=assets,query_outputs_verified=len(outputs),
        query_output_manifest=outputs,native_surface_records_verified=1200,
        migration_cache_count=json.loads((WORK/'MIGRATION_RECEIPT.json').read_text())['input_groups'],
        model_weights_unchanged=True,original_primary_scores_unchanged=True,new_training=False)
    (WORK/'POST_INTEGRITY.json').write_text(json.dumps(result,indent=2))
    print('POST_INTEGRITY_PASS',len(assets),len(outputs),1200,flush=True)


if __name__=='__main__':main()
