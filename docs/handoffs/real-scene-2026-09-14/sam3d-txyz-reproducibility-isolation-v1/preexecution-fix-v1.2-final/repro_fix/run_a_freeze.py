import argparse,hashlib,json
from pathlib import Path
def aggregate(rows,key):return hashlib.sha256(''.join(f"{x['frame_id']}\0{x[key]}\n" for x in sorted(rows,key=lambda x:x['frame_id'])).encode()).hexdigest()
def build(manifest_path):
 p=Path(manifest_path);d=json.loads(p.read_text());rows=[{'frame_id':x['frame_id'],'points_sha256':x['points_sha256'],'anchors_sha256':x['anchors_sha256']} for x in d['rows']]
 if len(rows)!=45 or len({x['frame_id'] for x in rows})!=45:raise RuntimeError('RUN_A_FREEZE_FRAME_IDENTITY_INVALID')
 return {'status':'FROZEN_RECONSTRUCTED_REPLAY_RUN_A','source_commit':'d0ce44c','manifest_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'expected_frame_count':45,'points_manifest_aggregate_sha256':aggregate(rows,'points_sha256'),'anchors_manifest_aggregate_sha256':aggregate(rows,'anchors_sha256'),'rows':rows}
def verify(freeze,manifest_path):
 current=build(manifest_path)
 for k in ('manifest_sha256','points_manifest_aggregate_sha256','anchors_manifest_aggregate_sha256'):
  if freeze[k]!=current[k]:raise RuntimeError('RUN_A_FREEZE_VIOLATION')
 return True
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
 if a.verify:verify(json.loads(a.verify.read_text()),a.manifest);print('PASS_RUN_A_FREEZE_VERIFICATION')
 else:
  if not a.output:raise SystemExit('--output is required when creating a freeze')
  a.output.write_text(json.dumps(build(a.manifest),indent=2)+'\n')
if __name__=='__main__':main()
