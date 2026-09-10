import argparse, hashlib, json
from pathlib import Path
import numpy as np

def fit(rows, allowed_train_subjects):
    used={str(r['subject_id']) for r in rows}
    if not used or not used <= set(map(str, allowed_train_subjects)):
        raise ValueError('Txyz fit rows must be nonempty and TRAIN-only')
    delta=np.asarray([r['oracle_translation_m'] for r in rows],dtype=np.float64)
    return delta.mean(0)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--fit-rows',type=Path,required=True); p.add_argument('--train-subjects',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    rows=json.loads(a.fit_rows.read_text())['rows']; subjects=json.loads(a.train_subjects.read_text())['subject_ids']
    bias=fit(rows,subjects)
    payload={'status':'FITTED_FROM_TRAIN_ONLY','bias_xyz_m':bias.tolist(),'fit_subject_ids':sorted({r['subject_id'] for r in rows}),'fit_row_count':len(rows),'fit_rows_sha256':hashlib.sha256(a.fit_rows.read_bytes()).hexdigest()}
    a.out.write_text(json.dumps(payload,indent=2)+'\n')
if __name__=='__main__': main()
