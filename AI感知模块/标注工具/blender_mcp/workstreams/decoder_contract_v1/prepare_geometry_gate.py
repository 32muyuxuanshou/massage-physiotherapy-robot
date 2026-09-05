from __future__ import annotations

import argparse,hashlib,json,shutil,sys,tempfile
from pathlib import Path


HERE=Path(__file__).resolve().parent
RECON_WS=HERE.parent/"cross_gate_reconciliation_v1"
sys.path.insert(0,str(RECON_WS))
import run_cross_gate_reconciliation as reconcile  # noqa:E402

RECON_ROOT=reconcile.AI_ROOT/"outputs"/"内部工程证据"/"2026-08-31_17-27-40_CROSS_GATE_RECONCILIATION_V1"
DESIGN=HERE/"profile_design_v1.json";CAMERAS=HERE/"camera_design_v1.json"


def read(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8-sig"))
def write(path:Path,value:dict)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()


def interpolate(a:dict,b:dict,t:float,item:dict)->dict:
    def mix(x:float,y:float)->float:return float(x+(y-x)*t)
    keys=sorted(set(a["pose_degrees"])|set(b["pose_degrees"]))
    pose={key:mix(float(a["pose_degrees"].get(key,0.0)),float(b["pose_degrees"].get(key,0.0))) for key in keys}
    return {
        "schema":"controlled-skel-shape-pose-profile-v1","profile_id":item["profile_id"],"medical_truth":False,
        "description":"Decoder-contract engineering interpolation probe; not a qualified continuous parameter range.",
        "betas":[mix(float(x),float(y)) for x,y in zip(a["betas"],b["betas"])],
        "pose_degrees":pose,"pose_vector_degrees":[mix(float(x),float(y)) for x,y in zip(a["pose_vector_degrees"],b["pose_vector_degrees"])],
        "source_kind":"frozen_parent_interpolation","parent_a":item["parent_a"],"parent_b":item["parent_b"],"interpolation_t":t,
        "shape_profile_id":item["profile_id"]+"_SHAPE","pose_profile_id":item["profile_id"]+"_POSE","split":item["split"],
        "medical_validated":False,"cross_validation_scope":"fixed-prone decoder-contract gate only",
        "limitations":["Engineering interpolation only","No medical, soft-tissue or continuous-space claim"]}


def prepare(root:Path)->list[dict]:
    reconcile.prepare(root);shutil.copy2(DESIGN,root/DESIGN.name);shutil.copy2(CAMERAS,root/CAMERAS.name)
    design=read(DESIGN);cells=[]
    for item in design["profiles"]:
        pa=read(RECON_ROOT/"profiles"/f"{item['parent_a']}.json");pb=read(RECON_ROOT/"profiles"/f"{item['parent_b']}.json")
        profile=interpolate(pa,pb,float(item["t"]),item);path=root/"profiles"/f"{item['profile_id']}.json";write(path,profile)
        cells.append({"case_id":item["profile_id"],"shape_id":profile["shape_profile_id"],"pose_id":profile["pose_profile_id"],"kind":"decoder_contract_"+item["split"].lower(),"split":item["split"],"parent_a":item["parent_a"],"parent_b":item["parent_b"]})
    checks={
        "eight_profiles":len(cells)==8,"split_4_4":sum(x["split"]=="VALIDATION" for x in cells)==4 and sum(x["split"]=="UNTOUCHED_TEST" for x in cells)==4,
        "unique_case_ids":len({x["case_id"] for x in cells})==8,
        "unique_parameter_vectors":len({json.dumps([read(root/"profiles"/f"{x['case_id']}.json")[k] for k in ("betas","pose_vector_degrees")]) for x in cells})==8,
        "parent_pairs_disjoint":not ({(x["parent_a"],x["parent_b"]) for x in cells if x["split"]=="VALIDATION"}&{(x["parent_a"],x["parent_b"]) for x in cells if x["split"]=="UNTOUCHED_TEST"}),
    }
    payload={"schema":"decoder-contract-geometry-input-v1","passed":all(checks.values()),"checks":checks,"cells":cells,"design_sha256":sha(DESIGN),"camera_design_sha256":sha(CAMERAS)};write(root/"new_geometry_manifest.json",payload)
    if not payload["passed"]:raise SystemExit(2)
    return cells


def run_geometry(root:Path,phase:str)->list[dict]:
    manifest=read(root/"new_geometry_manifest.json");results=[]
    with tempfile.TemporaryDirectory(prefix=f"acu_decoder_{phase}_") as temp:
        for index,cell in enumerate(manifest["cells"],1):
            meta=reconcile.run_case(root,phase,cell,cell["case_id"],Path(temp));narrow=read(root/phase/"narrow"/f"{cell['case_id']}.json")
            references=[]
            for parent in (cell["parent_a"],cell["parent_b"]):references.extend(read(RECON_ROOT/"search"/"narrow"/f"{parent}.json")["clusters"])
            gate=reconcile.evaluate_against_references(meta,narrow,references)
            record={**cell,"status":gate["status"],"passed":gate["status"]=="CROSS_QUALIFIED","bed_clearance_m":meta["bed_clearance_m"],"gate":gate,"probe_sha256":sha(root/phase/"probes"/f"{cell['case_id']}.json"),"narrow_sha256":sha(root/phase/"narrow"/f"{cell['case_id']}.json")};results.append(record);print(f"{phase} {index}/8 {cell['case_id']} {record['status']}",flush=True)
    write(root/f"{phase}_report.json",{"schema":"decoder-contract-new-geometry-gate-v1","passed":all(x["passed"] for x in results),"phase":phase,"cells":results})
    if not all(x["passed"] for x in results):raise SystemExit(3)
    return results


def verify_repeat(root:Path)->None:
    a=read(root/"geometry_primary_report.json");b=read(root/"geometry_repeat_report.json");by={x["case_id"]:x for x in b["cells"]};rows=[]
    for x in a["cells"]:
        y=by[x["case_id"]];rows.append({"case_id":x["case_id"],"status_equal":x["status"]==y["status"],"bed_clearance_equal":x["bed_clearance_m"]==y["bed_clearance_m"],"probe_equal":x["probe_sha256"]==y["probe_sha256"],"narrow_equal":x["narrow_sha256"]==y["narrow_sha256"]})
    passed=all(all(v for k,v in r.items() if k!="case_id") for r in rows);write(root/"geometry_determinism.json",{"schema":"decoder-contract-geometry-determinism-v1","passed":passed,"rows":rows})
    if not passed:raise SystemExit(4)


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=("prepare","geometry","repeat","verify"));parser.add_argument("--root",type=Path,required=True);args=parser.parse_args();root=args.root.resolve()
    if args.mode=="prepare":prepare(root)
    elif args.mode=="geometry":run_geometry(root,"geometry_primary")
    elif args.mode=="repeat":run_geometry(root,"geometry_repeat")
    else:verify_repeat(root)


if __name__=="__main__":main()
