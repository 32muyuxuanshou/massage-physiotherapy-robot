"""Export frozen Txyz diagnostics from explicit per-frame NPZ inputs."""
import argparse,json
from pathlib import Path
import numpy as np
from .txyz_replay_instrumentation import replay
from .io_v23 import sha256

def verify_provenance(item):
    required={'points_npz','points_sha256','anchors_npz','anchors_sha256','points_source','anchors_source'}
    if not required.issubset(item):raise RuntimeError('REPLAY_INPUT_PROVENANCE_INCOMPLETE')
    if sha256(item['points_npz'])!=item['points_sha256'] or sha256(item['anchors_npz'])!=item['anchors_sha256']:raise RuntimeError('REPLAY_INPUT_HASH_MISMATCH')
    if item['points_source'].get('camera')!='K0':raise RuntimeError('REPLAY_POINTS_MUST_BE_K0')
    if not {'depth','mask','calibration'}.issubset(item['points_source']) or not {'system','surface_anchor_hash','source_mesh_provenance'}.issubset(item['anchors_source']):raise RuntimeError('REPLAY_INPUT_PROVENANCE_INCOMPLETE')
    return {key:item[key] for key in required}

def export(input_manifest,output_path):
    rows=[]
    for item in json.loads(Path(input_manifest).read_text(encoding='utf-8'))['rows']:
        if 'frame_id' not in item:raise RuntimeError('REPLAY_INPUT_PROVENANCE_INCOMPLETE')
        provenance=verify_provenance(item)
        points=np.load(item['points_npz'])['points'];anchors=np.load(item['anchors_npz'])['anchors'];result=replay(points,anchors)
        rows.append({'frame_id':item['frame_id'],'input_provenance':provenance,'features':result['features'],'translation_m':result['translation_m'],'fallback':result['fallback'],'trace':result['trace']})
    payload={'algorithm':'FROZEN_ALL_POINTS_CHEAP_TXYZ_V2_3','rows':rows}
    Path(output_path).write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return payload

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input-manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();export(args.input_manifest,args.output)
if __name__=='__main__':main()
