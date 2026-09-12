"""Export frozen Txyz diagnostics from explicit per-frame NPZ inputs."""
import argparse,json
from pathlib import Path
import numpy as np
from .txyz_replay_instrumentation import replay

def export(input_manifest,output_path):
    rows=[]
    for item in json.loads(Path(input_manifest).read_text(encoding='utf-8'))['rows']:
        points=np.load(item['points_npz'])['points'];anchors=np.load(item['anchors_npz'])['anchors'];result=replay(points,anchors)
        rows.append({'frame_id':item['frame_id'],'features':result['features'],'translation_m':result['translation_m'],'fallback':result['fallback'],'trace':result['trace']})
    payload={'algorithm':'FROZEN_ALL_POINTS_CHEAP_TXYZ_V2_3','rows':rows}
    Path(output_path).write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return payload

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input-manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();export(args.input_manifest,args.output)
if __name__=='__main__':main()
