import csv,json
from pathlib import Path
from .back_region import load_frozen
from .failure_bundle import build
from .frame_outcomes import classify_frame
from .io_v23 import assert_unchanged,load_json,snapshot
from .k0_feature_extractor import extract_existing
from .leakage_audit import assert_no_leakage
from .residual_summary import describe

def execute(v23_root,output_root,schema_path,back_region_path=None):
    before=snapshot(v23_root);schema=load_json(schema_path)['features'];assert_no_leakage(schema);rows=load_json(Path(v23_root)/'formal/report/per_frame_results.json');features=[extract_existing(row,schema) for row in rows];bundles=[build(row,schema) for row in rows];root=Path(output_root);(root/'report').mkdir(parents=True,exist_ok=True);(root/'tables').mkdir(exist_ok=True);(root/'failure_cases').mkdir(exist_ok=True)
    groups={name:[] for name in ('GROUP_A','GROUP_B','GROUP_C','GROUP_D')}
    for row,bundle in zip(rows,bundles):groups[classify_frame(row)['frame_outcome_class']].append(bundle)
    for name,items in groups.items():
        with (root/'tables'/f'{name}.csv').open('w',newline='',encoding='utf-8') as handle:
            writer=csv.writer(handle);writer.writerow(['frame_id','n_improved']);writer.writerows((item['frame_id'],item['heldout_outcome']['n_improved']) for item in items)
    (root/'report'/'per_frame_audit.json').write_text(json.dumps(bundles,indent=2)+'\n');(root/'report'/'frame_group_summary.json').write_text(json.dumps(describe(rows,features),indent=2)+'\n');(root/'report'/'leakage_audit.json').write_text(json.dumps(assert_no_leakage(schema),indent=2)+'\n');(root/'report'/'back_specific_summary.json').write_text(json.dumps(load_frozen(back_region_path),indent=2)+'\n');assert_unchanged(before)
    return {'status':'FORMAL_AUDIT_COMPLETE_DESCRIPTIVE_ONLY','frames':len(rows),'classifier_trained':False,'txyz_parameters_changed':False}
