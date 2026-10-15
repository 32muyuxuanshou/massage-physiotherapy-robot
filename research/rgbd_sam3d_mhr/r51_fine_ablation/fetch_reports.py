"""Download public metrics and three explicitly selected review cases."""
from pathlib import Path
import json,os
import paramiko

OUT=Path('output/r51_fine_supervision_ablation_v1')
REMOTE='/raid5/xuhd/rgbd_sam3d/r51_fine_supervision_ablation_v1'


def main():
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect('172.18.6.218',port=436,username='xuhd',password=os.environ['ROBOT_SSH_PASSWORD'],timeout=25,look_for_keys=False,allow_agent=False)
    s=c.open_sftp();report=OUT/'reports';report.mkdir(exist_ok=True)
    for name in s.listdir(REMOTE+'/reports'):
        if name.endswith(('.json','.csv')):s.get(REMOTE+'/reports/'+name,str(report/name))
    for name in ['PREFLIGHT.json','FULL_FORWARD_REINSERTION_QA.json','REAL_EVALUATION_COMPLETE.json','REAL_EVALUATOR_PILOT.json','REAL_EVALUATION_INDEX.json','DATA_RESTORE_RECEIPT.json','SCAN_TRANSFER_RECEIPT.json']:
        s.get(REMOTE+'/'+name,str(OUT/name))
    jobs=json.loads((report/'REAL_JOBS.json').read_text(encoding='utf-8'))
    index=json.loads((OUT/'REAL_EVALUATION_INDEX.json').read_text(encoding='utf-8'))
    names={'Parent':'parent_s11_e00'}
    for arm in ['E0','E1_half','E1_zero','E2_l2']:names[arm]=next(r['job'] for r in index['links'] if r['arm']==arm and r['seed']==11 and r['selection']=='last')
    parent=jobs[names['Parent']]['records'];keys=[]
    for identity in ['p001195','p001196']:keys.append(dict(key=next(r['key'] for r in parent if r['identity']==identity),reason='预先已知失败身份的首帧 '+identity))
    zero={r['key']:r for r in jobs[names['E1_zero']]['records'] if r['dataset']=='real' and r['role']=='VAL'}
    e0={r['key']:r for r in jobs[names['E0']]['records'] if r['dataset']=='real' and r['role']=='VAL'}
    worst=max(zero,key=lambda k:zero[k]['metrics']['median_mm']-e0[k]['metrics']['median_mm'])
    keys.append(dict(key=worst,reason='seed11 VAL中移除Camera相对E0的median退化最大帧'))
    dest=OUT/'visual_inputs';dest.mkdir(exist_ok=True)
    for item in keys:
        for arm,name in names.items():
            for remote in [REMOTE+'/real_evaluation/'+name+'/real_'+item['key']+'.npz',REMOTE+'/real_evaluation/'+name+'/metrics/real_'+item['key']+'.npz']:
                suffix='_distances.npz' if '/metrics/' in remote else '_mesh.npz'
                s.get(remote,str(dest/(arm+'_'+item['key']+suffix)))
    (OUT/'FIGURE_SELECTION.json').write_text(json.dumps(dict(seed=11,selection='last',cases=keys,jobs=names,criteria='Two pre-known identities plus worst degradation, no filtering of evaluation data'),indent=2,ensure_ascii=False),encoding='utf-8')
    s.close();c.close();print('REPORTS_AND_REVIEW_CASES_DOWNLOADED',flush=True)


if __name__=='__main__':main()
