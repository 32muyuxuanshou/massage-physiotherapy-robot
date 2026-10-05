"""Assign source roles from author metadata before V3 model results exist."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OLD = HERE.parent / 'ct-anatomical-query-pilot-v1' / 'CASE_MANIFEST.json'


def main():
    metadata = list(csv.DictReader((HERE / 'V3_META.csv').open(encoding='utf-8-sig'), delimiter=';'))
    old = {r['subject']: r for r in json.loads(OLD.read_text())}
    rows = []
    for item in metadata:
        case = item['image_id']
        age = float(item['age']) if item['age'] else None
        if age is None:
            role = 'AGE_UNKNOWN_SOURCE_SUPPORT_ONLY'
        elif age < 18:
            role = 'PEDIATRIC_SOURCE_SUPPORT_ONLY'
        elif case in old:
            role = 'TRAIN' if old[case]['role'] == 'train' else 'CONSUMED_' + old[case]['role'].upper()
        elif item['split'] == 'test':
            role = 'AUTHOR_TEST_UNCONSUMED_IMAGE'
        else:
            bucket = int(hashlib.sha256(('V3_SPLIT_20261005:' + case).encode()).hexdigest()[:8], 16) % 10
            role = 'DEVELOPMENT' if bucket == 0 else 'TRAIN'
        rows.append(dict(case=case, role=role, author_split=item['split'], age_years=age,
                         institute=item['institute'], study_type=item['study_type'],
                         previously_consumed_CT_v2=case in old,
                         old_role=old[case]['role'] if case in old else None))
    assert len({r['case'] for r in rows}) == len(rows) == 1939
    assert not any(r['role'] == 'TRAIN' and r['author_split'] == 'test' for r in rows)
    result = dict(status='PRE_MODEL_SOURCE_ROLE_FREEZE', rows=rows,
                  role_counts=dict(Counter(r['role'] for r in rows)),
                  metadata_sha256=hashlib.sha256((HERE/'V3_META.csv').read_bytes()).hexdigest(),
                  old_manifest_sha256=hashlib.sha256(OLD.read_bytes()).hexdigest(),
                  old_cases_present=sum(r['previously_consumed_CT_v2'] for r in rows),
                  ages_policy='adult >=18 primary; pediatric/unknown support only, no current training',
                  source_unit='CT image_id, NOT certified independent patient_id',
                  grouping_limit='public metadata has no patient identifier; image-ID disjointness does not prove patient disjointness',
                  source_orientation='CT acquisitions not certified prone',
                  eligibility_after_role_freeze='C7/T1-T12/L1-L5: at least 3 nonclipped ordered label proxies with valid skin projection; no model-result selection',
                  new_dev_rule='author train, new adult image: SHA256(V3_SPLIT_20261005:ID) first8 hex mod10 ==0',
                  train_count_is_before_geometric_qualification=True,
                  clinical_acupoint_ground_truth=False)
    (HERE/'SOURCE_ROLE_FREEZE.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}, indent=2))


if __name__ == '__main__':
    main()
