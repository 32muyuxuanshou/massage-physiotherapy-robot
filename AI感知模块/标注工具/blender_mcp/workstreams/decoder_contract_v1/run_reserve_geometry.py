from __future__ import annotations

import argparse,json,shutil,sys,tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));from prepare_geometry_gate import RECON_ROOT,interpolate,read,write,sha  # noqa:E402
RECON_WS=HERE.parent/"cross_gate_reconciliation_v1";sys.path.insert(0,str(RECON_WS));import run_cross_gate_reconciliation as reconcile  # noqa:E402
DESIGN=HERE/"profile_design_reserve_v1.json"


def build(root:Path)->list[dict]:
    shutil.copy2(DESIGN,root/DESIGN.name);cells=[]
    for item in read(DESIGN)["profiles"]:
        a=read(RECON_ROOT/"profiles"/f"{item['parent_a']}.json");b=read(RECON_ROOT/"profiles"/f"{item['parent_b']}.json");profile=interpolate(a,b,float(item["t"]),item);write(root/"profiles"/f"{item['profile_id']}.json",profile)
        cells.append({"case_id":item["profile_id"],"shape_id":profile["shape_profile_id"],"pose_id":profile["pose_profile_id"],"kind":"decoder_contract_reserve_"+item["split"].lower(),"split":item["split"],"parent_a":item["parent_a"],"parent_b":item["parent_b"]})
    write(root/"reserve_geometry_manifest.json",{"schema":"decoder-contract-reserve-geometry-input-v1","design_sha256":sha(DESIGN),"cells":cells});return cells


def run(root:Path,phase:str)->None:
    cells=read(root/"reserve_geometry_manifest.json")["cells"] if (root/"reserve_geometry_manifest.json").is_file() else build(root);results=[]
    with tempfile.TemporaryDirectory(prefix="acu_decoder_reserve_") as temp:
        for index,cell in enumerate(cells,1):
            meta=reconcile.run_case(root,phase,cell,cell["case_id"],Path(temp));narrow=read(root/phase/"narrow"/f"{cell['case_id']}.json");refs=[]
            for parent in (cell["parent_a"],cell["parent_b"]):refs.extend(read(RECON_ROOT/"search"/"narrow"/f"{parent}.json")["clusters"])
            gate=reconcile.evaluate_against_references(meta,narrow,refs);row={**cell,"status":gate["status"],"passed":gate["status"]=="CROSS_QUALIFIED","bed_clearance_m":meta["bed_clearance_m"],"gate":gate,"probe_sha256":sha(root/phase/"probes"/f"{cell['case_id']}.json"),"narrow_sha256":sha(root/phase/"narrow"/f"{cell['case_id']}.json")};results.append(row);print(index,cell["case_id"],row["status"],flush=True)
    write(root/f"{phase}_report.json",{"schema":"decoder-contract-reserve-geometry-gate-v1","phase":phase,"cells":results,"qualified_count":sum(x["passed"] for x in results)})


def freeze_selection(root:Path)->None:
    rows=read(root/"geometry_primary_report.json")["cells"]+read(root/"reserve_geometry_report.json")["cells"]
    validation=[x for x in rows if x["split"]=="VALIDATION" and x["passed"]][:4];test=[x for x in rows if x["split"]=="UNTOUCHED_TEST" and x["passed"]][:4]
    checks={"validation_four":len(validation)==4,"test_four":len(test)==4,"case_disjoint":not({x["case_id"] for x in validation}&{x["case_id"] for x in test}),"parameter_ids_disjoint":not({(x["shape_id"],x["pose_id"]) for x in validation}&{(x["shape_id"],x["pose_id"]) for x in test})}
    payload={"schema":"qualified-new-geometry-selection-v1","passed":all(checks.values()),"checks":checks,"validation":validation,"untouched_test":test,"rejected_or_caution":[x for x in rows if not x["passed"]],"selection_policy":"First four passing cells per predeclared split; no decoder result existed at selection time."};write(root/"qualified_new_geometry.json",payload)
    if not payload["passed"]:raise SystemExit(3)


def main()->None:
    p=argparse.ArgumentParser();p.add_argument("mode",choices=("build-run","freeze"));p.add_argument("--root",type=Path,required=True);a=p.parse_args();root=a.root.resolve();run(root,"reserve_geometry") if a.mode=="build-run" else freeze_selection(root)


if __name__=="__main__":main()
