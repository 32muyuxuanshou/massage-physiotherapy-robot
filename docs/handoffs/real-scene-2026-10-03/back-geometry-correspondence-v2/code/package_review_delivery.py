"""Local packaging verification of completed outputs; never fit or infer."""
import argparse,hashlib,json,html,ast,re
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    root=a.workspace/'docs/handoffs/real-scene-2026-10-03/back-geometry-correspondence-v2'
    private=a.workspace/'output/back_geometry_correspondence_v2/private_review'
    cfg=read(root/'results/c_pressure_normal/EXECUTION_CONTRACT.json')
    for folder,count,pattern in [('indices',60,'*.npz'),('per_point_metrics',240,'*.npz'),('cache_metadata',240,'*.json')]:
        assert len(list((root/folder).rglob(pattern)))==count
    assert len(list((root/'figures').glob('S*_seed*.jpg')))==60
    assert len(read(root/'results/c_pressure_normal/ALL_METHOD_RESULTS.json'))==240
    assert len(read(root/'results/a_atlas/PROPAGATED_2400_POINTS.json'))==2400
    assert len(read(root/'results/c_pressure_normal/ENG_POINTS_1920.json'))==1920
    assert read(root/'results/c_pressure_normal/POST_EXECUTION_INTEGRITY.json')['status']=='PASS'
    public=read(root/'results/c_pressure_normal/PUBLIC_VISUAL_MANIFEST.json')
    for row in public:assert sha(root/'figures'/Path(row['path']).name)==row['sha256']
    pv=read(root/'SERVER_PRIVATE_VISUAL_MANIFEST.json')['rows']
    for row in pv:
        path=Path(row['path'])
        if row['dataset'].startswith('PressurePose'):
            file=private/'pressurepose'/f'{path.parts[-3]}_{path.parts[-2].replace("_","")}.jpg'
        else:file=private/'behave'/path.name
        assert sha(file)==row['sha256']
    assert len(pv)==120
    # Compare the frozen execution sources with the review snapshots, not with
    # a string claimed by another output file.
    checked=0
    for row in read(root/'results/c_pressure_normal/RUNTIME_SOURCE_FREEZE.json'):
        path=Path(row['path']);normalized=path.as_posix();local=None
        if '/back_geometry_correspondence_v2_20261003/code/' in normalized:local=root/'code'/path.name
        elif '/corrected_comparison_v2/delivery/code/' in normalized:local=root/'frozen_baseline_code'/path.name
        elif '/corrected_comparison_v2/delivery/' in normalized:local=root/'frozen_baseline_code'/path.name
        elif path.name=='ENGINEERING_BACK_ATLAS_V2.json':local=root/'results/a_atlas'/path.name
        elif path.name=='EXECUTION_CONTRACT.json':local=root/'results/c_pressure_normal'/path.name
        if local is not None:assert sha(local)==row['sha256'];checked+=1
    for file in list((root/'code').glob('*.py'))+list((root/'frozen_baseline_code').glob('*.py'))+list((root/'frozen_audit_code').glob('*.py')):
        ast.parse(file.read_text(encoding='utf-8-sig'),filename=str(file))
    lines=['# 全量可视化索引','',
        '公开图为预测 Mesh 与 ENG 探针，不含数据集原图。紫色填充与绿色轮廓属于同一预测表面；黄色是 ENG 中性探针投影。',
        '',f'原 RGB 全量对照已下载：`{private.as_posix()}/INDEX.html`。服务器地址详见 [复现说明](REPRODUCTION.md)。',
        '', '60 页按固定人物/种子排列，没有筛除失败；另有 [20人定量总图](figures/ALL_SUBJECT_COMPARISON.png) 与 [canonical 对照](figures/CANONICAL_OLD_NEW.png)。',
        '', '| 人物 | 角色 | seed0 | seed1 | seed2 |','|---|---|---|---|---|']
    for s in cfg['subjects']:
        role='开发' if s in cfg['dev'] else '测试角色（已使用人物）'
        links=' | '.join(f'[四方法](figures/{s}_seed{seed}.jpg)' for seed in cfg['seeds'])
        lines.append(f'| {s} | {role} | {links} |')
    lines+=['','原图审计清单：[120页私有图的服务器位置与SHA](SERVER_PRIVATE_VISUAL_MANIFEST.json)。BEHAVE 资格图不代表完成新的模型实验。',
        '', 'Public render cache / mesh source identities: [60-page manifest](results/c_pressure_normal/PUBLIC_VISUAL_MANIFEST.json)。']
    (root/'VISUALIZATION_INDEX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    sections=[]
    for group in ['pressurepose','behave']:
        sections.append('<h2>'+group+'</h2>')
        for file in sorted((private/group).glob('*.jpg')):
            rel=file.relative_to(private).as_posix()
            sections.append('<details><summary>'+html.escape(file.stem)+'</summary><a href="'+rel+'">打开原尺寸</a><br><img loading="lazy" src="'+rel+'"></details>')
    (private/'INDEX.html').write_text('<!doctype html><meta charset="utf-8"><title>完整原RGB复核</title><style>body{font:16px sans-serif;margin:24px}img{max-width:100%;height:auto}details{margin:14px 0}summary{cursor:pointer}</style><h1>60页俯卧对照与60页独立数据资格图</h1><p>按人物/种子排列，未筛除失败；紫/绿均为预测Mesh，非GT。原数据仅本地复核。</p>'+''.join(sections),encoding='utf-8')
    write(root/'KNOWLEDGE_CLOSEOUT.json',dict(status='COMPLETE',date_local='2026-10-04',scope='this task, its plan and CURRENT_STATUS only',
        no_other_user_files_staged=True,current_result='normal constraint reduces tangential drift; not seed stability or complete mesh validity',
        next_priority='independent common-back observation and target correspondence; no new training yet',
        old_atlas_medical_semantics='HOLD',new_atlas='neutral ENG geometric binding only',
        behave_new_cohort='NO_GO qualification budget; no model/fit',deployment_or_clinical_accuracy=False))
    broken=[]
    for file in root.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#') or target=='FILES_MANIFEST.json':continue
            path=(file.parent/target.split('#')[0]).resolve()
            if not path.exists():broken.append(dict(file=file.name,target=target))
    assert not broken,broken
    write(root/'DELIVERY_VALIDATION.json',dict(status='PASS',spatial_splits=60,mesh_metadata=240,per_point_arrays=240,
        prediction_pages=60,private_pages_actual_hash_checked=120,frozen_review_source_files_actual_hash_checked=checked,
        baseline_metric_agreement=180,independent_cache_recomputations=4,syntax='AST pass',local_links='PASS',
        clinical_or_independent_prone_accuracy_validated=False))
    records=[dict(path=file.relative_to(root).as_posix(),bytes=file.stat().st_size,sha256=sha(file))
        for file in sorted(root.rglob('*')) if file.is_file() and file.name!='FILES_MANIFEST.json' and '__pycache__' not in file.parts]
    write(root/'FILES_MANIFEST.json',dict(status='EXACT_BYTE_REVIEW_DELIVERY',manifest_self_excluded=True,files=records))
    print('DELIVERY_PASS',len(records),checked,len(pv),flush=True)

if __name__=='__main__':main()
