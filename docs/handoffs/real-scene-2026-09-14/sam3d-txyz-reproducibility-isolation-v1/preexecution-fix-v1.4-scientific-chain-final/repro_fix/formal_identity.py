import hashlib,json
from pathlib import Path

EXPECTED_FORMAL_FRAMES=45

def frame_id(row):
 return row.get('frame_id') or '/'.join(row[key] for key in ('subject','sequence','frame'))

def load_formal_rows(manifest):
 rows=json.loads(Path(manifest).read_text())['rows'];ids=[frame_id(row) for row in rows]
 if len(rows)!=EXPECTED_FORMAL_FRAMES or len(set(ids))!=EXPECTED_FORMAL_FRAMES:raise RuntimeError('FORMAL_45_FRAME_IDENTITY_INVALID')
 return [(fid,row) for fid,row in zip(ids,rows)]

def ids_aggregate(ids):
 return hashlib.sha256(''.join(f'{fid}\n' for fid in sorted(ids)).encode()).hexdigest()
