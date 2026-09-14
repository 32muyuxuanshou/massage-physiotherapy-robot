import argparse,json
from pathlib import Path
from .formal_identity import load_formal_rows,ids_aggregate
from .hashing import file_sha

def expected_paths(row,sequences_root,calibration_root):
 frame=Path(sequences_root)/row['sequence']/row['frame'];calibration_root=Path(calibration_root)
 return {'depth':frame/'k0.depth.png','mask':frame/'k0.person_mask.jpg','pointcloud_table':calibration_root/'intrinsics'/'0'/'pointcloud_table.npy','calibration':calibration_root/'intrinsics'/'0'/'calibration.json'}

def build(formal_manifest,sequences_root,calibration_root):
 rows=[]
 for fid,spec in load_formal_rows(formal_manifest):
  paths=expected_paths(spec,sequences_root,calibration_root);rows.append({'frame_id':fid,**{key:str(path.resolve()) for key,path in paths.items()},**{f'{key}_sha256':file_sha(path) for key,path in paths.items()}})
 return {'status':'FROZEN_POINTCLOUD_MANIFEST_FROM_FORMAL_45','formal_manifest':str(Path(formal_manifest).resolve()),'formal_manifest_sha256':file_sha(formal_manifest),'frame_count':len(rows),'frame_ids_sha256':ids_aggregate([row['frame_id'] for row in rows]),'rows':rows}

def verify(snapshot,formal_manifest,sequences_root,calibration_root):
 current=build(formal_manifest,sequences_root,calibration_root);mismatches=[]
 for key in ('formal_manifest_sha256','frame_count','frame_ids_sha256'):
  if snapshot.get(key)!=current[key]:mismatches.append({'field':key,'expected':snapshot.get(key),'observed':current[key]})
 old={row['frame_id']:row for row in snapshot.get('rows',[])};new={row['frame_id']:row for row in current['rows']}
 if set(old)!=set(new):mismatches.append({'field':'frame_ids','expected':sorted(old),'observed':sorted(new)})
 for fid in sorted(set(old)&set(new)):
  for key in ('depth','mask','pointcloud_table','calibration','depth_sha256','mask_sha256','pointcloud_table_sha256','calibration_sha256'):
   if old[fid].get(key)!=new[fid][key]:mismatches.append({'frame_id':fid,'field':key,'expected':old[fid].get(key),'observed':new[fid][key]})
 if mismatches:raise RuntimeError('POINTCLOUD_FORMAL_BINDING_MISMATCH:'+json.dumps(mismatches,separators=(',',':')))
 return {'status':'PASS_POINTCLOUD_FORMAL_BINDING','frame_count':len(new),'path_identity_fields':['depth','mask','pointcloud_table','calibration'],'hash_identity_fields':['depth_sha256','mask_sha256','pointcloud_table_sha256','calibration_sha256']}

def main():
 p=argparse.ArgumentParser();p.add_argument('--formal-manifest',type=Path,required=True);p.add_argument('--sequences-root',type=Path,required=True);p.add_argument('--calibration-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(build(a.formal_manifest,a.sequences_root,a.calibration_root),indent=2)+'\n')
if __name__=='__main__':main()
