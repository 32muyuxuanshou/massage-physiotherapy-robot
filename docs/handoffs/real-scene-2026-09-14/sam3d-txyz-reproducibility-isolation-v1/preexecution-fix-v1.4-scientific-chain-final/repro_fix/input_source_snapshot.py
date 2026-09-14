import argparse,json
from pathlib import Path
from .hashing import file_sha
from .formal_identity import load_formal_rows,ids_aggregate
def build(manifest,sequences_root):
 rows=[]
 for fid,spec in load_formal_rows(manifest):
  frame=Path(sequences_root)/spec['sequence']/spec['frame'];rgb=frame/'k0.color.jpg';mask=frame/'k0.person_mask.jpg';rows.append({'frame_id':fid,'raw_rgb_path':str(rgb.resolve()),'raw_rgb_file_sha256':file_sha(rgb),'raw_mask_path':str(mask.resolve()),'raw_mask_file_sha256':file_sha(mask)})
 return {'status':'FROZEN_AT_FORMAL_EXECUTION_START','historical_v23_raw_hashes_available':False,'scope':'new controlled cohort input identity','formal_manifest_sha256':file_sha(manifest),'frame_ids_sha256':ids_aggregate([x['frame_id'] for x in rows]),'rows':rows}
def verify(snapshot,manifest,sequences_root):
 current=build(manifest,sequences_root)
 if snapshot!=current:raise RuntimeError('CONTROLLED_INPUT_SNAPSHOT_INTEGRITY_MISMATCH')
 return {'status':'PASS_CONTROLLED_INPUT_SNAPSHOT_INTEGRITY','frame_count':len(current['rows'])}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--sequences-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(build(a.manifest,a.sequences_root),indent=2)+'\n')
if __name__=='__main__':main()
