"""Merge server nonsealed geometry QA into the precommitted V2 subject protocol."""
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--handoff',type=Path,required=True); ap.add_argument('--server-qa',type=Path,required=True); a=ap.parse_args()
    qa_path=a.handoff/'HUMMAN_V2_SUBJECT_QA_V1.json'; split_path=a.handoff/'HUMMAN_V2_SUBJECT_SPLIT_V1.json'
    qa,split,server=read(qa_path),read(split_path),read(a.server_qa)
    if server['status'] != 'AUTO_QA_COMPLETE_VISUAL_REVIEW_PENDING': raise RuntimeError(server['status'])
    rows=defaultdict(list)
    for r in server['results']: rows[r['subject']].append(r)
    passed=sorted(s for s,rs in rows.items() if len(rs)==3 and all(r['usable'] for r in rs))
    failed=sorted(set(rows)-set(passed))
    planned={r['subject'] for r in qa['new_nonsealed_qa_plan'] if r['split'] != 'TRAIN_HISTORICAL'}
    if set(rows)!=planned: raise RuntimeError({'missing':sorted(planned-set(rows)),'extra':sorted(set(rows)-planned)})
    details=[]
    for s in sorted(rows):
        rs=rows[s]
        details.append({'subject':s,'split':rs[0]['split'],'result':'PASS' if s in passed else 'FAIL',
                        'observations':len(rs),'usable_observations':sum(r['usable'] for r in rs),
                        'failure_reasons':sorted({x for r in rs for x in r['auto_gate_reasons']})})
    qa.update(status='GEOMETRY_QA_PASS' if not failed else 'GEOMETRY_QA_HAS_FAILURES',
              server_geometry_qa_sha256=sha(a.server_qa), new_pixel_geometry_qa_passed=len(passed),
              new_pixel_geometry_qa_failed=len(failed), new_subject_geometry_results=details)
    qa['counts']['new_pixel_geometry_qa_passed']=len(passed)
    qa['readiness_effect']='PASS_FOR_SUBJECT_POOL' if not failed else 'NOT_READY_REQUIRES_PRECOMMITTED_ALTERNATE_REPLACEMENT'
    split['status']='V2_SUBJECT_SPLIT_FROZEN_GEOMETRY_QA_PASS' if not failed else 'V2_SUBJECT_SPLIT_BLOCKED_BY_GEOMETRY_QA_FAILURES'
    split['new_nonsealed_geometry_qa']={'passed_subjects':passed,'failed_subjects':failed,'server_qa_sha256':sha(a.server_qa)}
    write(qa_path,qa); write(split_path,split)
    print(json.dumps({'status':qa['status'],'passed':len(passed),'failed':failed},indent=2))
if __name__=='__main__': main()
