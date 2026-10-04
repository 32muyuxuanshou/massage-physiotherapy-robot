"""Expose all eight fixed bindings from completed cache; no fitting."""
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT,METHODS,CASES,read,write,sha

def main():
    cfg=read(ROOT/'CONTRACT.json');atlas=read(ROOT/'ATLAS.json')['records'];rows=[];summary=[]
    for subject in cfg['subjects']:
        for case in CASES:
            result=read(ROOT/'runs'/subject/case/'results.json')
            for m in METHODS:
                z=np.load(ROOT/'runs'/subject/case/(m+'_probes.npz'))
                d=z['xyz_m']-z['reference_xyz_m'];signed=np.sum(d*z['reference_normals'],axis=1)
                euclidean=np.linalg.norm(d,axis=1)*1000
                tangent=np.linalg.norm(d-signed[:,None]*z['reference_normals'],axis=1)*1000
                original=next(r for r in result if r['method']==m)
                assert np.allclose(euclidean,original['probe_errors_mm'],rtol=0,atol=1e-10)
                for i,r in enumerate(atlas):
                    rows.append(dict(subject=subject,role='dev' if subject in cfg['dev'] else 'validation_consumed',case=case,method=m,
                        probe_id=r['id'],euclidean_mm=float(euclidean[i]),tangent_mm=float(tangent[i]),
                        normal_abs_mm=float(abs(signed[i])*1000),normal_signed_mm=float(signed[i]*1000),
                        normal_angle_deg=original['probe_normal_angle_deg'][i]))
    for role in ['dev','validation_consumed']:
        for case in CASES:
            for m in METHODS:
                for p in atlas:
                    selected=[r for r in rows if r['role']==role and r['case']==case and r['method']==m and r['probe_id']==p['id']]
                    summary.append(dict(role=role,case=case,method=m,probe_id=p['id'],sources=len(selected),
                        **{k:float(np.median([r[k] for r in selected])) for k in ['euclidean_mm','tangent_mm','normal_abs_mm','normal_angle_deg']}))
    assert len(rows)==1920 and len(summary)==192
    with (ROOT/'ENGINEERING_PROBE_RESULTS.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write(ROOT/'ENGINEERING_PROBE_AUDIT.json',dict(status='PASS',all_probe_rows=len(rows),per_probe_summaries=summary,
        identity=dict(script_sha256=sha(__file__),input='240 *_probes.npz and 60 results.json; cached only'),
        medical_ground_truth=False,summary='per fixed binding, subject median within each error case; all eight included'))
    fig,axes=plt.subplots(1,3,figsize=(16,5))
    x=np.arange(8);width=.24
    for col,case in enumerate(CASES):
        for j,m in enumerate(METHODS[1:]):
            rs=[next(r for r in summary if r['role']=='validation_consumed' and r['case']==case and r['method']==m and r['probe_id']==p['id']) for p in atlas]
            axes[col].bar(x+(j-1)*width,[r['euclidean_mm'] for r in rs],width,label=m)
        axes[col].set_xticks(x,[r['id'].replace('ENG_','') for r in atlas],rotation=60,ha='right',fontsize=7)
        axes[col].set_ylabel('Known binding Euclidean error (mm)');axes[col].set_title(case);axes[col].legend(fontsize=7)
    fig.suptitle('All 8 fixed engineering bindings / 16 consumed validation sources / controlled geometry only')
    fig.tight_layout();fig.savefig(ROOT/'figures/PROBE_ERROR_BREAKDOWN.png',dpi=140);plt.close(fig)
    print('CORRESPONDENCE_AUDIT_PASS',len(rows),len(summary),flush=True)

if __name__=='__main__':main()
