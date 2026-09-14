import argparse,json,subprocess,sys
from pathlib import Path
def validate(spec):
 ids=[x['frame_id'] for x in spec['sentinels']]
 if len(ids)!=7 or len(set(ids))!=7:raise RuntimeError('FRAME_ORDER_SENTINELS_NOT_7_UNIQUE')
 return ids
def build_orders(ids,seed):
 import random
 x=list(ids);y=list(reversed(ids));z=list(ids);random.Random(seed).shuffle(z);return {'ORDER_ORIGINAL':x,'ORDER_REVERSED':y,'ORDER_RANDOM_FIXED_SEED':z}
def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=json.loads(a.spec.read_text());a.output.write_text(json.dumps({'orders':build_orders(validate(s),s['seed']),'comparison_fields':['prepared_tensor.sha256','model_state_sha256','pred_vertices','pred_cam_t','anchors'],'failure_status':'FRAME_ORDER_DEPENDENCE'},indent=2)+'\n')
if __name__=='__main__':main()
