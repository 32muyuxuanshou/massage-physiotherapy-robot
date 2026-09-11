"""Create model-smoke rows only from the previously consumed Sub01."""
import argparse, json
from pathlib import Path
from prepare_frozen_manifest import valid_frames

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--sequences",type=Path,required=True); parser.add_argument("--out",type=Path,required=True); args=parser.parse_args(); rows=[]
    for action in ("backpack_back","stool_sit"):
        hits=sorted(args.sequences.glob(f"Date01_Sub01_{action}"))
        if len(hits)!=1: raise RuntimeError(f"expected one consumed Sub01 smoke sequence for {action}; got {hits}")
        frames=valid_frames(hits[0]); rows.append({"subject":"Sub01","date":"Date01","sequence":hits[0].name,"action":action,"frame":frames[len(frames)//2],"role":"CONSUMED_SMOKE_ONLY"})
    args.out.write_text(json.dumps({"formal_generalization":False,"must_not_enter_fresh_aggregation":True,"rows":rows},indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
