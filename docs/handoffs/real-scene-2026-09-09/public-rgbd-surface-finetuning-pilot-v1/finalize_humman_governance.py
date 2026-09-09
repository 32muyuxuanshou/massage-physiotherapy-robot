"""Audit historical subject mentions and emit standard candidate governance JSONs."""
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[3]


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    inventory = read('humman_local_inventory.json')
    records = inventory['packed_coverage']['sequence_records']
    known = {r['subject'] for r in records}
    command = ['rg', '-l', '-uu', 'p[0-9]{6}', '.', '-g', '!**/.git/**',
               '-g', '!**/public-rgbd-surface-finetuning-pilot-v1/**']
    for extension in ('json', 'md', 'py', 'txt', 'csv', 'log', 'yaml', 'yml'):
        command.extend(['-g', '*.' + extension])
    command.extend(['-g', '!**/.git/**', '-g', '!**/public-rgbd-surface-finetuning-pilot-v1/**'])
    result = subprocess.run(command, cwd=PROJECT, capture_output=True, encoding='utf-8')
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    evidence = defaultdict(list)
    for relative in result.stdout.splitlines():
        path = PROJECT / relative
        if path.resolve().is_relative_to(OUT):
            continue
        for line_no, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            for subject in set(re.findall(r'p\d{6}', line)) & known:
                evidence[subject].append({'path': str(path.relative_to(PROJECT)), 'line': line_no,
                    'line_sha256': hashlib.sha256(line.encode()).hexdigest(),
                    'classification': 'prior_text_reference_conservatively_exposed'})
    # Raw files/calibration directory names are an availability inventory, not
    # evidence that a human/model viewed each person's RGB. List this separately.
    raw = Path(inventory['source_root'])
    metadata_subjects = sorted({p.parent.name.split('_')[0] for p in (raw / 'humman_meta/extracted').rglob('cameras.json')})
    extracted_subjects = sorted({r['subject'] for r in inventory['extracted_coverage']['sequence_records']})
    for subject in extracted_subjects:
        evidence[subject].append({'path': str(raw / 'humman_subset'), 'line': None,
             'classification': 'previously_extracted_RGBD_subject'})
    exposed = sorted(evidence)
    usable = sorted({r['subject'] for r in records if r['structurally_usable']})
    clean = [s for s in usable if s not in exposed]
    seed = 'humman-pilot-v1-20260909'
    clean.sort(key=lambda s: hashlib.sha256((seed + ':' + s).encode()).hexdigest())
    candidates = {'DEV': sorted(set(exposed) & set(usable)), 'TRAIN': clean[10:25],
                  'VAL': clean[5:10], 'SEALED': clean[:5], 'UNASSIGNED_RESERVE': clean[25:]}
    assert not ((set(candidates['VAL']) | set(candidates['SEALED'])) & set(exposed))
    assert len(sum(candidates.values(), [])) == len(set(sum(candidates.values(), [])))
    audit = {'status': 'REPOSITORY_TEXT_AND_EXTRACTED_DATA_AUDIT_COMPLETE_WITH_LIMITS',
        'command': command, 'searched_root': str(PROJECT),
        'matching_text_files': len(result.stdout.splitlines()), 'exposed_subjects': exposed,
        'evidence': dict(evidence), 'metadata_directory_subjects_not_equated_to_RGB_exposure': metadata_subjects,
        'exclusion': 'Current pilot handoff excluded to avoid self-contamination from ID-only inventory/candidate lists',
        'conservative_policy': 'Any historical text reference to a known HuMMan ID is excluded from VAL/SEALED, including third-party README examples.',
        'limits': ['Cannot detect images viewed without recorded subject IDs, deleted history, remote-only experiment records, or external human exposure.',
                   'Subject IDs in raw metadata directory names establish availability, not image-content exposure.']}
    write('HUMMAN_EXPOSURE_AUDIT_V1.json', audit)
    write('HUMMAN_EXISTING_ARCHIVE_INVENTORY_V1.json', inventory)
    pool = {'status': 'STRUCTURAL_CANDIDATE_POOL_NOT_GEOMETRIC_READINESS',
            'metadata_unique_subjects': len(known), 'structurally_usable_subjects': usable,
            'structurally_usable_count': len(usable), 'unexposed_usable_subjects': clean,
            'unexposed_usable_count': len(clean), 'exposed_subjects': exposed,
            'exposure_evidence_file': 'HUMMAN_EXPOSURE_AUDIT_V1.json',
            'subject_records': [{'subject': s, 'sequences': [r['sequence'] for r in records if r['subject']==s and r['structurally_usable']],
                'exposed': s in exposed} for s in usable]}
    write('HUMMAN_SUBJECT_POOL_V1.json', pool)
    split = {'status': 'SELECTION_RULE_FROZEN_FINAL_SPLIT_NOT_FROZEN',
        'rule_frozen': True, 'final_split_frozen': False, 'seed': seed,
        'rule': 'Remove all exposed subjects to DEV; sort remaining structural pool by SHA256(seed + colon + subject); first 5 SEALED, next 5 VAL, next 15 TRAIN; all others UNASSIGNED_RESERVE.',
        'subject_disjoint': True, 'all_sequences_actions_frames_cameras_follow_subject': True,
        'candidate_subjects': candidates, 'candidate_counts': {k:len(v) for k,v in candidates.items()},
        'final_freeze_preconditions': ['Server archive migration and checksum manifest complete.',
            'Reconcile server-only exposure records with repository audit; exclude any newly exposed subjects.',
            'Freeze final subject list and manifest hashes before training; do not use SEALED pixels/results for selection or tuning.'],
        'initial_budget': 'Approximately 30 subjects including DEV5; 1 sequence per subject, sparse frame sampling.',
        'frame_sampling_rule': 'After server metadata verification, use up to 3 synchronized frames per chosen sequence at 25/50/75 percent of the usable frame range, deduplicated; freeze frame IDs before training.',
        'exposure_audit': 'HUMMAN_EXPOSURE_AUDIT_V1.json'}
    old = read('humman_subject_split_candidates.json')['subjects']
    split['exposed_subjects_removed_from_val_and_sealed'] = sorted(set(exposed) & (set(old['VAL']) | set(old['SEALED'])))
    action_use = defaultdict(int)
    preferred = {}
    for group in ('DEV', 'TRAIN', 'VAL', 'SEALED'):
        for subject in candidates[group]:
            options = [r for r in records if r['subject']==subject and r['structurally_usable']]
            options.sort(key=lambda r: (action_use[r['action']], hashlib.sha256((seed+':'+r['sequence']).encode()).hexdigest()))
            chosen = options[0]
            preferred[subject] = {'sequence': chosen['sequence'], 'action': chosen['action'], 'action_name': chosen['action_name'], 'split': group}
            action_use[chosen['action']] += 1
    split['one_sequence_per_subject_candidates'] = preferred
    split['sequence_selection_rule'] = 'In DEV/TRAIN/VAL/SEALED order, prefer least-used action among each subject\'s structurally complete sequences; SHA256(seed:sequence) breaks ties. Metadata only; no image inspection.'
    write('HUMMAN_SUBJECT_SPLIT_V1.json', split)
    plan = read('humman_minimum_download_plan.json')
    plan.update({'server_first_policy': {'download_new_data_to': 'server_only',
        'local_new_dataset_downloads_allowed': False, 'local_archives': 'Retain historical files; migrate or copy to server, verify checksums before using server copy.',
        'extraction': 'Server only for new subject RGB/depth/mask payloads; select sequences rather than full expansion.',
        'local_artifacts': 'Code, JSON audit reports and compact review outputs only.'},
        'storage_constraint': {'reported_remaining_server_bytes': 1800000000000,
            'reported_remaining_display': '1.8 TB', 'measurement_source': 'Current task constraint; not independently measured by this local worker',
            'known_archive_payload_bytes': sum(a['bytes'] for a in inventory['archives']),
            'known_archive_share_of_reported_free': sum(a['bytes'] for a in inventory['archives']) / 1800000000000,
            'required_preflight': 'Measure current free disk on destination server; account for existing files, transfers, selective decompression, processed targets, caches and checkpoints.',
            'uncompressed_selected_payload_bytes': 'unknown_until_selected archive-entry sizes are budgeted',
            'execution_gate': 'Do not schedule downloads/extraction whose projected peak disk usage exceeds measured available space; retain operating headroom.',
            'avoid_full_expansion': True},
        'selection_rule_frozen': True, 'final_split_frozen': False})
    write('HUMMAN_INCREMENTAL_DOWNLOAD_PLAN_V1.json', plan)
    print(json.dumps({'exposed': exposed, 'counts': split['candidate_counts'],
                      'removed': split['exposed_subjects_removed_from_val_and_sealed']}))


if __name__ == '__main__':
    main()
