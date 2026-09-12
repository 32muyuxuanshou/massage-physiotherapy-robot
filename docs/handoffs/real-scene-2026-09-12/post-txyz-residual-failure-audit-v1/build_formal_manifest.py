import argparse,hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--v23-root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();source=args.v23_root/'report/BEHAVE_V2_FROZEN_TEST_MANIFEST.json';data=json.loads(source.read_text());rows=[{'subject':r['subject'],'sequence':r['sequence'],'frame':r['frame'],'cameras':['K0','K1','K2','K3'],'k0_role':'DEPLOYMENT_FEATURE_SOURCE','heldout_role':'OFFLINE_AUDIT_LABEL_ONLY'} for r in data['rows']]
    payload={'status':'PREEXECUTION_MANIFEST_ONLY','source_manifest':str(source),'source_sha256':sha(source),'rows':rows,'frame_count':len(rows),'subject_count':len({r['subject'] for r in rows}),'sequence_count':len({r['sequence'] for r in rows}),'known_zero_of_three_retained':['Sub07','Date06_Sub07_stool_sit','t0038.000'] in [[r['subject'],r['sequence'],r['frame']] for r in rows]};args.out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
