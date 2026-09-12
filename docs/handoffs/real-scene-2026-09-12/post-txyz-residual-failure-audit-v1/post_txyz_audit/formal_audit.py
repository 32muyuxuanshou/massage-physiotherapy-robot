import csv,json
from pathlib import Path
from .back_region import load_frozen
from .failure_bundle import build
from .frame_outcomes import classify_frame
from .io_v23 import assert_tree_unchanged,load_json,snapshot_tree
from .k0_feature_extractor import extract_existing
from .k0_data_features import extract as extract_k0_data
from .data_locator import resolve_k0
from .leakage_audit import assert_no_leakage
from .residual_summary import describe
from .visualization_spec import paths as visualization_paths
from .replay_parity import compare,assert_all
from .runtime_assets import verify as verify_runtime_assets
from .replay_feature_export import verify_provenance

def execute(v23_root,output_root,schema_path,manifest_path,sequence_root,replay_features_path,asset_requirements,txyz_source,anchors,calibs,back_region_path=None,no_visuals=False):
    before=snapshot_tree(v23_root);assets=verify_runtime_assets(asset_requirements,manifest_path,txyz_source,anchors,calibs);schema=load_json(schema_path)['features'];assert_no_leakage(schema);rows=load_json(Path(v23_root)/'formal/report/per_frame_results.json')
    replay=load_json(replay_features_path);replay_by_id={item['frame_id']:item for item in replay['rows']};expected={"/".join((r['spec']['subject'],r['spec']['sequence'],r['spec']['frame'])) for r in rows};manifest_rows=load_json(manifest_path)['rows'];manifest_by_id={"/".join((r['subject'],r['sequence'],r['frame'])):r for r in manifest_rows}
    if len(replay['rows'])!=len(expected) or set(replay_by_id)!=expected:raise RuntimeError('REPLAY_FEATURE_FRAME_IDENTITY_MISMATCH')
    if len(manifest_rows)!=len(expected) or set(manifest_by_id)!=expected:raise RuntimeError('FORMAL_MANIFEST_FRAME_IDENTITY_MISMATCH')
    for item in replay['rows']:verify_provenance(item.get('input_provenance',{}))
    parity=assert_all([compare(frame_id,replay_by_id[frame_id],row) for row in rows for frame_id in ["/".join((row['spec']['subject'],row['spec']['sequence'],row['spec']['frame']))]])
    bundles=[];features=[]
    for row in rows:
        frame_id="/".join((row['spec']['subject'],row['spec']['sequence'],row['spec']['frame']));sources=resolve_k0(sequence_root,row['spec'],manifest_by_id[frame_id]['k0_file_ids']);values=extract_k0_data(sources['depth'],sources['mask']);values.update(replay_by_id[frame_id]['features']);bundle=build(row,schema,sources,values);bundles.append(bundle);features.append(bundle['k0_features'])
    required={f['name'] for f in schema if f['availability_status'] in ('REQUIRES_K0_DATA_READ','REQUIRES_TXYZ_REPLAY')}
    if any(required-{name for name,item in bundle['k0_features'].items() if item['value'] is not None} for bundle in bundles):raise RuntimeError('FORMAL_DIAGNOSTIC_FEATURES_INCOMPLETE')
    root=Path(output_root);(root/'report').mkdir(parents=True,exist_ok=True);(root/'tables').mkdir(exist_ok=True);(root/'failure_cases').mkdir(exist_ok=True)
    groups={name:[] for name in ('GROUP_A','GROUP_B','GROUP_C','GROUP_D')}
    for row,bundle in zip(rows,bundles):groups[classify_frame(row)['frame_outcome_class']].append(bundle)
    for name,items in groups.items():
        with (root/'tables'/f'{name}.csv').open('w',newline='',encoding='utf-8') as handle:
            writer=csv.writer(handle);writer.writerow(['frame_id','n_improved']);writer.writerows((item['frame_id'],item['heldout_outcome']['n_improved']) for item in items)
    visualization_plan=[] if no_visuals else [{'frame_id':bundle['frame_id'],**visualization_paths(bundle['frame_id'])} for bundle in bundles]
    (root/'report'/'per_frame_audit.json').write_text(json.dumps(bundles,indent=2)+'\n');(root/'report'/'frame_group_summary.json').write_text(json.dumps(describe(rows,features),indent=2)+'\n');(root/'report'/'TXYZ_REPLAY_PARITY_GATE.json').write_text(json.dumps(parity,indent=2)+'\n');(root/'report'/'runtime_asset_reverification.json').write_text(json.dumps(assets,indent=2)+'\n');(root/'report'/'leakage_audit.json').write_text(json.dumps(assert_no_leakage(schema),indent=2)+'\n');(root/'report'/'back_specific_summary.json').write_text(json.dumps(load_frozen(back_region_path),indent=2)+'\n');(root/'report'/'visualization_plan.json').write_text(json.dumps({'enabled':not no_visuals,'rows':visualization_plan},indent=2)+'\n');assert_tree_unchanged(v23_root,before)
    return {'status':'FORMAL_AUDIT_COMPLETE_DESCRIPTIVE_ONLY','frames':len(rows),'classifier_trained':False,'txyz_parameters_changed':False,'visuals_enabled':not no_visuals}
