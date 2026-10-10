"""Package the executed geometry audit, hash actual inputs, and retain old results."""
import argparse
import csv
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import scipy
from run_r41_txyz import sha


def dump(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def main(a):
    work=a.work;g=json.loads((work/'GEOMETRY_AUDIT.json').read_text())
    raw=json.loads((work/'RAW_SENSOR_QA.json').read_text())
    inputs=json.loads((a.previous/'POST_EXECUTION_INTEGRITY.json').read_text())['actual_inputs']
    assets=a.source/'assets';checked=[]
    for row in inputs:
        for field,path in [('compact',assets/'original_assets/inputs'),
                           ('official',assets/'original_assets/official'),
                           ('heldout',assets/'datasets/heldout/humman_r3_k1_v1')]:
            p=path/(row['key']+'.npz');actual=sha(p)
            assert actual==row[field+'_sha256']
            checked.append(dict(file=str(p),sha256=actual))
    for row in g['detailed_27_frames']:
        for m in row['methods']:
            cell,stage=m['cell'],m['stage']
            if cell=='official':folder=assets/'original_assets/official' if stage=='before' else a.source/'corrected/official'
            elif cell.startswith('g1_seed'):folder=assets/f'r4/formal/{cell}/real' if stage=='before' else a.source/f'corrected/{cell}'
            else:folder=a.previous/('raw' if stage=='before' else 'corrected')/cell
            path=folder/(row['key']+'.npz');assert sha(path)==m['mesh_sha256']
    integrity=dict(status='PASS',actual_historical_input_hashes=len(checked),
        actual_native_output_hashes=sum(len(r['methods']) for r in g['detailed_27_frames']),
        independent_triangle_controls=64,raw_sensor_views=len(raw['views']),
        raw_replay_max_mm=max(r['nearest_replayed_point_max_mm'] for r in raw['views']),
        original_RESULTS_not_rewritten=True,all_seeds=[11,23,37],
        no_Txyz_refit=True,no_new_model_inference=True,no_new_training=True,
        no_camera_B_fitting=True,test_read=False,
        physical_registration_status=raw['registration_status'],
        physical_sync_status=raw['synchronization_status'],
        checked_inputs=checked)
    dump(work/'POST_EXECUTION_INTEGRITY.json',integrity)
    with (work/'A_DEPTH_DIAGNOSTICS.csv').open('w',encoding='utf-8',newline='') as out:
        names=['key','identity','role','cell','stage','A_surface_median_mm','A_surface_p95_mm',
               'ray_hits','ray_count','signed_z_median_mm','absolute_z_median_mm',
               'absolute_z_p95_mm','all_method_common_hits','common_hit_absolute_z_median_mm']
        writer=csv.DictWriter(out,fieldnames=names);writer.writeheader()
        for r in g['detailed_27_frames']:
            for m in r['methods']:
                writer.writerow(dict(key=r['key'],identity=r['identity'],role=r['role'],cell=m['cell'],stage=m['stage'],
                    A_surface_median_mm=m['A_observed_to_mesh']['median_mm'],
                    A_surface_p95_mm=m['A_observed_to_mesh']['p95_mm'],
                    ray_hits=m['A_ray']['hits'],ray_count=m['A_ray']['point_count'],
                    **{k:m['A_ray'][k] for k in names[9:]}))
    original_results=json.loads((a.previous/'ALL_RESULTS.json').read_text())
    B={(r['key'],r['cell']):r for r in original_results['records']}
    lines=['# 四个预先固定样本的逐seed诊断','',
        'A射线差为 predicted Z − observed Z；正数代表预测更远。A表面与B表面均是观测点到面，单位mm。以下是诊断例，不替代232帧身份等权汇总。','',
        '|帧|方法|A表面median|A射线signed median|A射线命中率|B表面median/P95|',
        '|---|---|---:|---:|---:|---:|']
    fixed=['p001195_a000053_000037','p001196_a000388_000040',
           'p001194_a000062_000005','p100069_a005191_000006']
    for key in fixed:
        row=next(r for r in g['detailed_27_frames'] if r['key']==key)
        for m in row['methods']:
            b=B[key,m['cell']]['triangle_'+m['stage']]
            label=m['cell']+(' +Txyz' if m['stage']=='after' else '')
            lines.append(f"|{key}|{label}|{m['A_observed_to_mesh']['median_mm']:.2f}|{m['A_ray']['signed_z_median_mm']:.2f}|{100*m['A_ray']['hit_fraction']:.1f}%|{b['median_mm']:.2f}/{b['p95_mm']:.2f}|")
    (work/'CASE_TABLE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    env=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,opencv=cv2.__version__,platform=platform.platform())
    events=[]
    for filename,action in [('OFFICIAL_SOURCE_RECEIPT.json','download official calibration/toolbox sources'),
        ('export.log','first export failed: VISUAL_SELECTION dict read as list'),
        ('export_fixed.log','correct records field, export 54 raw sensor views and sequential RGB fixtures'),
        ('GEOMETRY_AUDIT.json','232 calibration checks, 27x14 A audits and 64 independent B controls'),
        ('RAW_SENSOR_QA.json','54 original depth replay and 8 temporal checks'),
        ('visualizations/RAW_MANIFEST.json','four fixed raw sensor visualizations'),
        ('POST_EXECUTION_INTEGRITY.json','verify original 696 inputs and 378 native outputs')]:
        p=work/filename;events.append(dict(action=action,artifact=filename,
            artifact_mtime_utc=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),
            timestamp_kind='artifact mtime; not claimed exact execution start'))
    dump(work/'EXECUTION_LEDGER.json',dict(scope='R4.2 independent geometry supplement; prior swaps and CPU pilot reused',
        source_commit='4ac1f4133c34ef5d39889de8a799ed6466a5bea8',environment=env,
        local_geometry_seconds=g['seconds'],events=events,
        first_export_failure='TypeError from iterating top-level dict; fixed records lookup, full exporter rerun',
        first_local_audit_failure='selection length assertion for same dict/list issue; corrected records lookup and full audit rerun',
        remote_mode='existing AutoDL no-GPU, cpu.max=50000 100000, memory.max=2147483648',
        new_scientific_training_runs=0,new_SAM_inference_runs=0,prior_CPU_pilot_retrained=False,
        unchanged_primary_evaluation='fixed 2048 B points, exact triangle distances, frame->sequence->identity',
        completed_utc=datetime.now(timezone.utc).isoformat()))
    a.delivery.mkdir(parents=True,exist_ok=True)
    for name in ['GEOMETRY_AUDIT.json','RAW_SENSOR_QA.json','OFFICIAL_SOURCE_RECEIPT.json',
                 'POST_EXECUTION_INTEGRITY.json','A_DEPTH_DIAGNOSTICS.csv','CASE_TABLE.md','EXECUTION_LEDGER.json',
                 'export.log','export_fixed.log']:
        shutil.copy2(work/name,a.delivery/name)
    shutil.copy2(work/'raw/RAW_EXPORT_RECEIPT.json',a.delivery/'RAW_EXPORT_RECEIPT.json')
    shutil.copy2(a.previous/'VISUAL_SELECTION.json',a.delivery/'VISUAL_SELECTION.json')
    shutil.copytree(work/'visualizations',a.delivery/'visualizations',dirs_exist_ok=True)
    code=a.delivery/'code';code.mkdir(exist_ok=True)
    current=Path(__file__).parent
    names=['export_r42_geometry_raw.py','audit_r42_geometry.py','audit_r42_raw.py',
           'visualize_r42_geometry.py','visualize_r42_raw.py','closeout_r42_geometry.py',
           'run_r41_txyz.py','visualize_r41_txyz.py']
    for name in names:shutil.copy2(current/name,code/name)
    for name in ['diagnose_r31.py','evaluate_r3_humman.py','humman_geometry.py','surface_metrics.py']:
        shutil.copy2(a.source/'code'/name,code/name)
    (code/'.gitattributes').write_text('*.py -text diff\n',encoding='utf-8')
    (code/'requirements-cpu.txt').write_text('numpy=='+np.__version__+'\nscipy=='+scipy.__version__+'\nopencv-python=='+cv2.__version__+'\nPillow\nmatplotlib\n',encoding='utf-8')
    dump(a.delivery/'CODE_SOURCE_SHA.json',dict(files=[dict(file=p.name,sha256=sha(p)) for p in sorted(code.glob('*.py'))],
        baseline_numerical_functions_unchanged=True,official_functions_source_receipt='OFFICIAL_SOURCE_RECEIPT.json'))
    print('PACKAGE_PASS',len(checked),'historical inputs;',integrity['actual_native_output_hashes'],'native meshes;',len(list((a.delivery/'visualizations').glob('*.jpg'))),'images')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True);p.add_argument('--delivery',type=Path,required=True);main(p.parse_args())
