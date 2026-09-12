import json
from pathlib import Path
from .back_region import load_frozen
from .config import EXPECTED_FRAMES,EXPECTED_SEQUENCES,EXPECTED_SUBJECTS,HELDOUT_CAMERAS,KNOWN_ZERO_OF_THREE
from .io_v23 import assert_unchanged,load_json,snapshot
from .k0_feature_schema import validate_feature
from .leakage_audit import assert_no_leakage

def run(v23_root,schema_path,manifest_path,back_region_path=None):
    before=snapshot(v23_root);schema=load_json(schema_path)["features"]
    for feature in schema:validate_feature(feature)
    leakage=assert_no_leakage(schema);manifest=load_json(manifest_path);rows=manifest["rows"];ids={(r["subject"],r["sequence"],r["frame"]) for r in rows}
    checks={"rows_45":len(rows)==EXPECTED_FRAMES==len(ids),"subjects_5":{r['subject'] for r in rows}==EXPECTED_SUBJECTS,"sequences_15":len({r['sequence'] for r in rows})==EXPECTED_SEQUENCES,"all_cameras":all(tuple(r['cameras'])==('K0',*HELDOUT_CAMERAS) for r in rows),"known_failure_retained":KNOWN_ZERO_OF_THREE in ids,"v23_final_gate":load_json(Path(v23_root)/'formal/report/final_decision_v2.json')['gate']=='PASS_BEHAVE_CHEAP_TXYZ_GENERALIZATION_V2'}
    back=load_frozen(back_region_path);assert_unchanged(before)
    return {"status":"PURE_CODE_POST_TXYZ_AUDIT_PREFLIGHT_PASS" if all(checks.values()) else "FAIL_PREEXECUTION","formal_audit_executed":False,"checks":checks,"leakage_audit":leakage,"back_region":back,"v23_read_only_verified":True,"v23_assets":before}
