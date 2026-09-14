import argparse,json
from pathlib import Path
from .hashing import file_sha
def build(manifest,sequences_root):
 rows=[]
 for spec in json.loads(Path(manifest).read_text())['rows']:
  fid=spec.get('frame_id') or '/'.join(spec[k] for k in ('subject','sequence','frame'));frame=Path(sequences_root)/spec['sequence']/spec['frame'];rgb=frame/'k0.color.jpg';mask=frame/'k0.person_mask.jpg';rows.append({'frame_id':fid,'raw_rgb_file_sha256':file_sha(rgb),'raw_mask_file_sha256':file_sha(mask)})
 return {'status':'FROZEN_AT_FORMAL_EXECUTION_START','historical_v23_raw_hashes_available':False,'scope':'new controlled cohort input identity','rows':rows}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--sequences-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(build(a.manifest,a.sequences_root),indent=2)+'\n')
if __name__=='__main__':main()
