"""Isolated pose candidate selection; frozen Atlas and thresholds never change."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import build_qc_dataset_30 as d
b=d.b

parser=argparse.ArgumentParser()
parser.add_argument("degrees",type=float)
args=parser.parse_args()
cfg=b.read_json(d.CONFIG)
root=b.AI_ROOT/"outputs"/"BlenderMCP"/"workstreams"/"qc_dataset_30"/("elbow_candidate_"+str(args.degrees)+"_"+datetime.now().strftime("%H-%M-%S"))
root.mkdir(parents=True,exist_ok=False)
results=[]
for si,shape in enumerate(cfg["shapes"]):
    pose={"pose_id":"P3_ELBOW_CANDIDATE","overrides_degrees":{"elbow_flexion_r":args.degrees,"elbow_flexion_l":args.degrees}}
    prof=d.profile(shape,pose)
    prof_path=root/f"S{si}.json"
    b.write_json(prof_path,prof)
    native=root/f"native_S{si}"
    b.run([str(b.PYTHON),str(b.GENERATE),"--profile",str(prof_path),"--output",str(native)])
    for ci,camera in enumerate(cfg["cameras"]):
        tag=f"S{si}_C{ci}"
        contract=b.read_json(b.CONTRACT)
        contract["camera_matrix_world"]=camera["matrix_world"]
        cp=root/f"C{ci}.json"
        b.write_json(cp,contract)
        snapshot=root/(tag+".blend")
        prep=root/(tag+"_prepare.json")
        d.bj(b.PREPARE,b.CANONICAL,["--snapshot",snapshot,"--result",prep,"--native-pose-dir",native,"--pose-profile",prof_path,"--fixed-scene-contract",cp,"--width",1280,"--height",1024],"ACU_PREPARE_PRONE_SCENE=PASS")
        sample=root/tag
        d.bj(b.EXPORT,snapshot,["--fixture",d.ATLAS,"--output",sample,"--result",root/(tag+"_export.json"),"--width",1280,"--height",1024],"ACU_EXPORT_PRONE_SAMPLE=PASS")
        result=d.strict_qc(sample,b.read_json(d.ATLAS),prof,cfg)
        result["case"]=tag
        result["clearance_m"]=b.read_json(prep)["body_bounds_world_m"]["min"][2]
        result["passed"] &= 0 <= result["clearance_m"] <= .03
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k not in ("checks","points")}),flush=True)
b.write_json(root/"candidate_report.json",{"passed":all(r["passed"] for r in results),"results":results,"notice":"Selection evidence only; final frozen dataset must be independently re-generated and verified."})
print(str(root))
