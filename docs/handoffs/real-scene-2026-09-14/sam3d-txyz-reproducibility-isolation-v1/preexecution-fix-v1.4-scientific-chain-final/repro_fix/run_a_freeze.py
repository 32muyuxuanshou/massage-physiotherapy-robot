import argparse,hashlib,json
from pathlib import Path
from .hashing import file_sha

def aggregate(rows,key):return hashlib.sha256(''.join(f"{x['frame_id']}\0{x[key]}\n" for x in sorted(rows,key=lambda x:x['frame_id'])).encode()).hexdigest()

def build(manifest_path):
 p=Path(manifest_path);d=json.loads(p.read_text());rows=[{'frame_id':x['frame_id'],'points_sha256':x['points_sha256'],'anchors_sha256':x['anchors_sha256']} for x in d['rows']]
 if len(rows)!=45 or len({x['frame_id'] for x in rows})!=45:raise RuntimeError('RUN_A_FREEZE_FRAME_IDENTITY_INVALID')
 return {'status':'FROZEN_RECONSTRUCTED_REPLAY_RUN_A','source_commit':'d0ce44c','manifest_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'expected_frame_count':45,'points_manifest_aggregate_sha256':aggregate(rows,'points_sha256'),'anchors_manifest_aggregate_sha256':aggregate(rows,'anchors_sha256'),'rows':rows}

def verify_manifest_contract(freeze,manifest_path):
 current=build(manifest_path)
 for key in ('manifest_sha256','points_manifest_aggregate_sha256','anchors_manifest_aggregate_sha256'):
  if freeze[key]!=current[key]:raise RuntimeError(f'RUN_A_FREEZE_VIOLATION:{key}')
 return current

def verify(freeze,manifest_path):
 """Verify both the manifest contract and all 90 actual Run A NPZ files."""
 verify_manifest_contract(freeze,manifest_path);manifest=json.loads(Path(manifest_path).read_text());frozen={x['frame_id']:x for x in freeze['rows']};observed=[];mismatches=[]
 if {x['frame_id'] for x in manifest['rows']}!=set(frozen):raise RuntimeError('RUN_A_ACTUAL_ASSET_FRAME_IDENTITY_MISMATCH')
 for row in manifest['rows']:
  fid=row['frame_id'];actual={'points_sha256':file_sha(row['points_npz']),'anchors_sha256':file_sha(row['anchors_npz'])};observed.append({'frame_id':fid,'points_npz':row['points_npz'],'anchors_npz':row['anchors_npz'],**actual})
  for kind in ('points','anchors'):
   key=f'{kind}_sha256';expected=frozen[fid][key]
   if row[key]!=expected or actual[key]!=expected:mismatches.append({'frame_id':fid,'asset':kind,'path':row[f'{kind}_npz'],'expected':expected,'manifest':row[key],'actual':actual[key]})
 if mismatches:raise RuntimeError('RUN_A_ACTUAL_ASSET_HASH_MISMATCH:'+json.dumps(mismatches,separators=(',',':')))
 return {'status':'PASS_RUN_A_ACTUAL_ASSET_FREEZE','frame_count':len(observed),'points_verified':len(observed),'anchors_verified':len(observed),'observed':observed}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
 if a.verify:print(json.dumps(verify(json.loads(a.verify.read_text()),a.manifest),indent=2))
 else:
  if not a.output:raise SystemExit('--output is required when creating a freeze')
  a.output.write_text(json.dumps(build(a.manifest),indent=2)+'\n')
if __name__=='__main__':main()
