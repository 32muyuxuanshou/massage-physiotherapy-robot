"""Read frozen meshes; audit units and diagnose topology-seed propagation.

No SAM inference, fitting, atlas relocation, or modification of source assets.
"""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def array_sha(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def save_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def interpolate(vertices, faces, records):
    face_ids = np.array([r['face_index'] for r in records], dtype=int)
    bary = np.array([r['barycentric'] for r in records], dtype=float)
    tri = vertices[faces[face_ids]]
    xyz = (tri * bary[:, :, None]).sum(1)
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    length = np.linalg.norm(cross, axis=1)
    normals = cross / np.maximum(length[:, None], 1e-30)
    return xyz, normals, length / 2


def project(points, K):
    return np.column_stack((K[0, 0] * points[:, 0] / points[:, 2] + K[0, 2],
                            K[1, 1] * points[:, 1] / points[:, 2] + K[1, 2]))


def local_quality(reference, target, faces, patch_faces):
    tri0, tri1 = reference[faces[patch_faces]], target[faces[patch_faces]]
    e = np.unique(np.sort(np.vstack([faces[patch_faces][:, [0, 1]], faces[patch_faces][:, [1, 2]],
                                     faces[patch_faces][:, [2, 0]]]), axis=1), axis=0)
    lengths0 = np.linalg.norm(reference[e[:, 0]] - reference[e[:, 1]], axis=1)
    lengths1 = np.linalg.norm(target[e[:, 0]] - target[e[:, 1]], axis=1)
    n0 = np.cross(tri0[:, 1] - tri0[:, 0], tri0[:, 2] - tri0[:, 0])
    n1 = np.cross(tri1[:, 1] - tri1[:, 0], tri1[:, 2] - tri1[:, 0])
    a0, a1 = np.linalg.norm(n0, axis=1), np.linalg.norm(n1, axis=1)
    valid = (a0 > 1e-16) & (a1 > 1e-16)
    dot = np.clip(np.sum(n0[valid] * n1[valid], axis=1) / (a0[valid] * a1[valid]), -1, 1)
    relative = np.abs(lengths1 / lengths0 - 1)
    return dict(local_edge_change_p99=float(np.percentile(relative, 99)),
                local_area_ratio_median=float(np.median(a1 / a0)),
                local_normal_angle_p95_deg=float(np.percentile(np.degrees(np.arccos(dot)), 95)) if valid.any() else None,
                local_normal_reversal_fraction=float((dot < 0).mean()) if valid.any() else None,
                local_degenerate_faces=int((a1 <= 1e-16).sum()), local_face_count=int(len(patch_faces)))


def canonical_preview(vertices_cm, faces, mask_ids, records, destination):
    points, _, _ = interpolate(vertices_cm, faces, records)
    vertices = vertices_cm * 10
    points *= 10
    canvas = Image.new('RGB', (1150, 1000), 'white')
    draw = ImageDraw.Draw(canvas)
    tri = vertices[faces]
    colors = np.zeros(len(faces), bool)
    colors[mask_ids] = True
    for panel, (horizontal, view) in enumerate(((0, 'canonical X/Y'), (2, 'canonical Z/Y'))):
        x0 = panel * 570 + 20
        low, high = vertices.min(0), vertices.max(0)
        scale = min(500 / (high[horizontal] - low[horizontal]), 850 / (high[1] - low[1]))
        def xy(p):
            return (x0 + 20 + (p[horizontal] - low[horizontal]) * scale, 930 - (p[1] - low[1]) * scale)
        order = np.argsort(tri[:, :, 2 if horizontal == 0 else 0].mean(1))[::-1]
        for i in order:
            draw.polygon([xy(p) for p in tri[i]], fill=(234, 152, 152) if colors[i] else (205, 205, 205))
        draw.text((x0, 10), view + ' | native cm -> displayed mm | +Y upward', fill='black')
        draw.text((x0, 30), 'Red: historical region; blue: old seeds; orthographic audit only', fill='black')
        if horizontal == 0:
            draw.line([xy(np.array([0, low[1], 0])), xy(np.array([0, high[1], 0]))], fill=(30, 170, 50), width=2)
        for i, p in enumerate(points):
            x, y = xy(p)
            draw.ellipse((x-4, y-4, x+4, y+4), fill=(15, 50, 235))
            draw.text((x+5, y-5), records[i]['id'], fill='black')
    canvas.save(destination, quality=94)


def audit_assets(args):
    assets, cache, out = args.assets, args.cache, args.out / 'p0_assets'
    out.mkdir(parents=True, exist_ok=True)
    v = np.load(assets / 'mhr_rest_vertices.npy')
    zero = np.load(assets / 'mhr_zero_forward_vertices.npy')
    faces = np.load(assets / 'mhr_faces.npy')
    atlas = read(assets / 'VIRTUAL_ACUPOINTS_ENGINEERING_V1.json')
    contract = read(assets / 'EXPERIMENT_CONTRACT.json')
    mask = read(assets / 'candidate_posterior_mask.json')
    source_contract = read(assets / 'POSTERIOR_TORSO_V1_CONTRACT.json')
    assert v.shape == (18439, 3) and faces.shape == (36874, 3)
    assert zero.shape == v.shape
    zero_delta_mm = np.linalg.norm(zero.astype(float) - v.astype(float), axis=1) * 10
    assert array_sha(v) == atlas['mesh_hashes']['rest_vertices_sha256']
    assert array_sha(faces.astype('<i4')) == contract['historical_faces_sha256']
    unit_source = args.sam_repo / 'sam_3d_body/models/heads/mhr_head.py'
    lines = unit_source.read_text().splitlines()
    evidence = [{'line': i+1, 'text': line.strip()} for i, line in enumerate(lines)
                if 'curr_skinned_verts = curr_skinned_verts / 100' in line]
    assert evidence
    records = atlas['records']
    bary = np.array([r['barycentric'] for r in records])
    assert len(records) == 8 and np.all(bary >= 0) and np.allclose(bary.sum(1), 1, atol=1e-12)
    xyz, normals, areas = interpolate(v, faces, records)
    old_xyz = np.array([r['canonical_xyz_mm'] for r in records])
    assert np.allclose(xyz, old_xyz, atol=1e-6)  # Old numeric values were native cm.
    assert np.all(areas > 0)
    corrected = copy.deepcopy(atlas)
    corrected['schema'] = 'ENGINEERING_ATLAS_UNIT_CORRECTED_V1'
    corrected['native_unit'] = 'cm'
    corrected['native_to_mm'] = 10.0
    corrected['status'] = 'GEOMETRY_VALID_SEMANTIC_REVIEW_REQUIRED'
    corrected['correction'] = 'Unit labels/derived xyz only; face IDs, barycentrics and anatomical labels unchanged'
    point_audit = []
    for r, p, n in zip(corrected['records'], xyz, normals):
        r['canonical_xyz_native_cm'] = p.tolist()
        r['canonical_xyz_mm'] = (p * 10).tolist()
        flags = []
        if r['laterality'] == 'midline' and abs(p[0]) > 1e-8:
            flags.append('MIDLINE_LABEL_WITH_NONZERO_CANONICAL_X')
        if ((r['laterality'] == 'left' and p[0] < 0) or
                (r['laterality'] == 'right' and p[0] > 0)):
            flags.append('CONFLICT_WITH_HISTORICAL_PLUS_X_IS_SUBJECT_LEFT_DECLARATION')
        inside = r['face_index'] in mask['face_ids']
        r['semantic_flags'] = flags
        r['medical_truth'] = False
        point_audit.append(dict(id=r['id'], face_index=r['face_index'], inside_posterior=inside,
                                canonical_xyz_mm=r['canonical_xyz_mm'], normal=n.tolist(), flags=flags))
    saved = {r['id']: np.array(r['canonical_xyz_mm']) for r in corrected['records']}
    vertical = dict(GV14_y_mm=float(saved['GV14'][1]), GV4_y_mm=float(saved['GV4'][1]),
                    GV14_above_GV4_under_plus_Y_up=bool(saved['GV14'][1] > saved['GV4'][1]),
                    note='Engineering semantic ordering check, not observed vertebral locations')
    checks = []
    for subject in contract['subjects']:
        for seed in contract['seeds']:
            for method in contract['methods']:
                path = cache / 'meshes' / subject / f'seed_{seed}' / (method.replace('+', '_') + '.npz')
                meta = read(path.with_suffix('.json'))
                actual_sha = sha(path)
                assert actual_sha == meta['mesh_sha256']
                with np.load(path, allow_pickle=False) as z:
                    assert np.array_equal(z['faces'], faces)
                    assert z['vertices_m'].shape == v.shape
                    assert array_sha(z['faces'].astype('<i8')) == meta['faces_sha256']
                    split = np.load(cache / 'inputs' / subject / f'split_{seed}.npz')
                    assert not np.intersect1d(z['optimization_point_idx'], split['heldout_idx']).size
                checks.append(dict(subject=subject, seed=seed, method=method, source=str(path), sha256=actual_sha,
                                   faces_equal=True, optimization_heldout_intersection=0))
    assert len(checks) == 300
    # Correct report units without re-running any native-coordinate rule geometry.
    report = read(assets / 'rule_sanity_v1/RULE_ONLY_GEOMETRY_SANITY_V1.json')
    for row in report['samples']:
        if row['sample'] == 'canonical_mhr':
            row['native_unit'] = 'cm'
            row['native_to_mm'] = 10.0
            row['projection_distance_median_mm'] *= 10
            row['projection_distance_max_mm'] *= 10
    comparison = read(assets / 'rule_sanity_v1/RULE_ONLY_VS_TRANSFER_GEOMETRY_V1.json')
    for row in comparison['samples']:
        if row['sample'] == 'canonical_mhr':
            for key in ('median_mm', 'max_mm'):
                row[key] *= 10
            for r in row['per_point']:
                r['rule_vs_transfer_distance_mm'] *= 10
    write(out / 'RULE_ONLY_GEOMETRY_SANITY_UNIT_CORRECTED.json', report)
    write(out / 'RULE_VS_TRANSFER_UNIT_CORRECTED.json', comparison)
    write(out / 'ENGINEERING_ATLAS_UNIT_CORRECTED.json', corrected)
    audit = dict(status='PASS_UNITS_AND_TOPOLOGY_HOLD_ANATOMICAL_SEMANTICS', native_unit='cm', native_to_mm=10,
                 predicted_cache_unit='m', predicted_native_to_mm=1000,
                 raw_rest_equals_raw_zero_forward=bool(np.array_equal(v, zero)),
                 zero_forward_minus_rest_median_mm=float(np.median(zero_delta_mm)),
                 zero_forward_minus_rest_max_mm=float(zero_delta_mm.max()),
                 canonical_source='raw rest vertices; zero-forward comparison recorded separately',
                 unit_source=str(unit_source), unit_source_sha256=sha(unit_source),
                 unit_source_lines=evidence, canonical_bbox_mm=dict(min=(v.min(0)*10).tolist(), max=(v.max(0)*10).tolist()),
                 faces_sha256_int32=array_sha(faces.astype('<i4')), faces_sha256_int64=array_sha(faces.astype('<i8')),
                 actual_caches_verified=300, medical_truth=False, old_axis_declaration=source_contract['coordinate_convention'],
                 point_checks=point_audit, vertical_order=vertical,
                 limitations=['Old point labels/placements retained as engineering seeds; semantic flags prohibit accuracy claims',
                              'Orientation declaration conflicts are recorded, not silently relabeled'])
    write(out / 'POINT_ASSET_AUDIT.json', audit)
    write(out / 'CACHE_SOURCE_MANIFEST.json', checks)
    write(out / 'ASSET_SOURCE_MANIFEST.json', [{'path': str(p), 'sha256': sha(p)} for p in sorted(assets.rglob('*')) if p.is_file()])
    canonical_preview(v, faces, mask['face_ids'], records, out / 'canonical_seed_audit.jpg')
    print(json.dumps({k: audit[k] for k in ['status', 'actual_caches_verified', 'canonical_bbox_mm', 'vertical_order']}), flush=True)


def comparison_page(cache, subject, seed, names, matrices, normals, ids, deltas, destination):
    with np.load(cache / 'inputs' / subject / 'input.npz') as inp:
        rgb, K, points = inp['rgb'], inp['K'], inp['points_m']
        back = inp['posterior_point_mask']
    h, w = rgb.shape[:2]
    canvas = Image.new('RGB', ((len(names)+1)*w, h+610), 'white')
    draw = ImageDraw.Draw(canvas)
    canvas.paste(Image.fromarray(rgb), (0, 110))
    draw.text((8, 8), f'{subject} seed {seed}: cached engineering points', fill='black')
    draw.text((8, 26), 'Not independently labeled acupoints', fill='black')
    draw.text((8, 44), 'Purple/green: predicted surface/outline', fill='black')
    draw.text((8, 62), 'Yellow: numbered OLD engineering seed', fill='black')
    draw.text((8, 80), 'Point semantic problems retained', fill='black')
    for col, method in enumerate(names, 1):
        depfile = cache / 'visualizations' / subject / f'seed_{seed}' / (method.replace('+', '_')+'_render.npz')
        dep = np.load(depfile)['depth_m']
        image = rgb.copy()
        mask = dep > 0
        image[mask] = np.clip(.58*image[mask]+.42*np.array([255,70,160]), 0, 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(image, contours, -1, (30,255,80), 1)
        p, _, _ = matrices[method]
        for index, uv in enumerate(project(p, K)):
            x,y = np.rint(uv).astype(int)
            if p[index,2] > 0 and 0 <= x < w and 0 <= y < h:
                cv2.circle(image, (x,y), 5, (255,235,0), -1)
                cv2.putText(image, str(index+1), (x+6,y-4), cv2.FONT_HERSHEY_SIMPLEX, .38, (0,0,0), 2)
                cv2.putText(image, str(index+1), (x+6,y-4), cv2.FONT_HERSHEY_SIMPLEX, .38, (255,255,255), 1)
        canvas.paste(Image.fromarray(image), (col*w, 110))
        draw.text((col*w+8,8), method, fill='black')
        draw.text((col*w+8,29), 'Same K / frozen mesh and raster cache', fill='black')
    fig, axes = plt.subplots(1,2,figsize=(15,3.3))
    cp = points[back][::8]
    axes[0].scatter(cp[:,1],cp[:,2],s=1,c='gray',alpha=.15,label='observed back cloud projection')
    for method, (p, n, area) in matrices.items():
        axes[0].plot(p[:,1],p[:,2],'o',ms=4,label=method)
    axes[0].set_xlabel('camera Y (m)'); axes[0].set_ylabel('camera Z (m)')
    axes[0].set_title('Y/Z diagnostic projection; not sagittal slice or anatomy GT')
    axes[0].invert_yaxis(); axes[0].legend(fontsize=6)
    x=np.arange(len(ids))
    axes[1].bar(x-.18,deltas['normal'],width=.36,label='absolute normal component')
    axes[1].bar(x+.18,deltas['tangent'],width=.36,label='tangent magnitude')
    axes[1].set_xticks(x,[f'{i+1}:{name}' for i,name in enumerate(ids)],rotation=25,ha='right',fontsize=7)
    axes[1].set_ylabel('Rigid -> D point movement (mm)')
    axes[1].set_title('Deformation movement, not acupoint error'); axes[1].legend(fontsize=7)
    fig.tight_layout()
    temporary=destination.with_suffix('.plot.png')
    fig.savefig(temporary,dpi=140); plt.close(fig)
    plot=Image.open(temporary).convert('RGB')
    plot.thumbnail((canvas.width,450))
    canvas.paste(plot,((canvas.width-plot.width)//2,h+125))
    draw.text((10,h+570),'Point IDs: '+', '.join(f'{i+1}={v}' for i,v in enumerate(ids)),fill='black')
    draw.text((10,h+590),'Current atlas has known semantic conflicts. Approximate PressurePose camera, no medical ground truth.',fill='black')
    canvas.save(destination,quality=92)
    temporary.unlink()


def run_points(args, dev=False):
    cache=args.cache
    atlas=read(args.out/'p0_assets/ENGINEERING_ATLAS_UNIT_CORRECTED.json')
    contract=read(args.assets/'EXPERIMENT_CONTRACT.json')
    faces=np.load(args.assets/'mhr_faces.npy').astype(int)
    records=atlas['records'];ids=[r['id'] for r in records]
    mask_ids=set(read(args.assets/'candidate_posterior_mask.json')['face_ids'])
    patches=[np.flatnonzero(np.isin(faces,faces[r['face_index']]).any(1)) for r in records]
    out=args.out/('p1_dev' if dev else 'p1_cached_transfer')
    out.mkdir(parents=True,exist_ok=True)
    subjects=contract['dev'] if dev else contract['subjects']
    seeds=[0] if dev else contract['seeds']
    source_files={}
    rows=[];pair_rows=[];visuals=[]
    for subject in subjects:
        inp_path=cache/'inputs'/subject/'input.npz'
        source_files[str(inp_path)]=sha(inp_path)
        with np.load(inp_path) as inp:
            rgb,K,cloud,roi=inp['rgb'],inp['K'],inp['points_m'],inp['posterior_rgb_mask']
        h,w=rgb.shape[:2]
        for seed in seeds:
            splitpath=cache/'inputs'/subject/f'split_{seed}.npz'
            source_files[str(splitpath)]=sha(splitpath)
            with np.load(splitpath) as split:
                train_idx,heldout_idx=split['train_idx'],split['heldout_idx']
                assert not np.intersect1d(train_idx,heldout_idx).size
            train_tree,heldout_tree=cKDTree(cloud[train_idx]),cKDTree(cloud[heldout_idx])
            matrices={};vertices={};metas={}
            for method in contract['methods']:
                base=method.replace('+','_')
                path=cache/'meshes'/subject/f'seed_{seed}'/(base+'.npz')
                source_files[str(path)]=sha(path)
                meta=read(path.with_suffix('.json')); assert source_files[str(path)]==meta['mesh_sha256']
                assert source_files[str(inp_path)] == meta['input_sha256']
                assert source_files[str(splitpath)] == meta['split_sha256']
                source_files[str(path.with_suffix('.json'))]=sha(path.with_suffix('.json'))
                with np.load(path) as z:
                    assert np.array_equal(faces,z['faces'])
                    assert not np.intersect1d(z['optimization_point_idx'],heldout_idx).size
                    vertices[method]=z['vertices_m'].copy()
                    if method=='Official+Rigid+D':
                        cached_D=z['displacement_m'].copy()
                    if method=='Official+Rigid':
                        R,t=z['rigid_R'].copy(),z['rigid_t_m'].copy()
                matrices[method]=interpolate(vertices[method],faces,records)
                metas[method]=meta
            assert np.allclose(vertices['Official+Rigid']@np.eye(3),vertices['Official']@R.T+t,atol=1e-8)
            assert np.allclose(vertices['Official+Rigid+D'],vertices['Official+Rigid']+cached_D,atol=1e-8)
            direct=matrices['Official'][0]@R.T+t
            assert np.allclose(matrices['Official+Rigid'][0],direct,atol=1e-8)
            delta=matrices['Official+Rigid+D'][0]-matrices['Official+Rigid'][0]
            refn=matrices['Official+Rigid'][1]
            component=np.sum(delta*refn,axis=1)
            tangent=delta-component[:,None]*refn
            normal_mm=np.abs(component)*1000;tangent_mm=np.linalg.norm(tangent,axis=1)*1000
            assert np.allclose(delta,(component[:,None]*refn)+tangent,atol=1e-12)
            for method in contract['methods']:
                p,n,area=matrices[method];uv=project(p,K)
                near_train=train_tree.query(p)[0]*1000;near_heldout=heldout_tree.query(p)[0]*1000
                render_path=cache/'visualizations'/subject/f'seed_{seed}'/(method.replace('+','_')+'_render.npz')
                source_files[str(render_path)]=sha(render_path)
                dep=np.load(render_path)['depth_m']
                tc=[len(x) for x in train_tree.query_ball_point(p,.02)]
                hc=[len(x) for x in heldout_tree.query_ball_point(p,.02)]
                for i,r in enumerate(records):
                    x,y=np.rint(uv[i]).astype(int)
                    inside=bool(p[i,2]>0 and 0<=x<w and 0<=y<h)
                    inroi=bool(inside and roi[y,x])
                    raster_gap=float((p[i,2]-dep[y,x])*1000) if inside and dep[y,x]>0 else None
                    local=local_quality(vertices['Official'],vertices[method],faces,patches[i])
                    row=dict(subject=subject,role='dev' if subject in contract['dev'] else 'historically_consumed_test_role',
                             seed=seed,method=method,point_id=r['id'],face_id=r['face_index'],
                             barycentric=r['barycentric'],xyz_m=p[i].tolist(),xyz_mm=(p[i]*1000).tolist(),
                             surface_normal=n[i].tolist(),face_area_mm2=float(area[i]*1e6),uv_px=uv[i].tolist(),
                             inside_rgb=inside,inside_back_roi=inroi,inside_posterior=r['face_index'] in mask_ids,
                             closest_train_point_mm=float(near_train[i]),closest_heldout_point_mm=float(near_heldout[i]),
                             support_radius_mm=20,train_support_count=tc[i],heldout_support_count=hc[i],
                             raster_depth_gap_mm=raster_gap,source_mesh_sha256=metas[method]['mesh_sha256'],
                             medical_truth=False,semantic_flags=r['semantic_flags'],
                             local_quality_reference='Official same subject/seed',**local)
                    rows.append(row)
            for i,r in enumerate(records):
                qual=local_quality(vertices['Official+Rigid'],vertices['Official+Rigid+D'],faces,patches[i])
                angle=np.degrees(np.arccos(np.clip(np.dot(refn[i],matrices['Official+Rigid+D'][1][i]),-1,1)))
                pair_rows.append(dict(subject=subject,role='dev' if subject in contract['dev'] else 'historically_consumed_test_role',
                                      seed=seed,point_id=r['id'],movement_total_mm=float(np.linalg.norm(delta[i])*1000),
                                      movement_normal_signed_mm=float(component[i]*1000),movement_normal_abs_mm=float(normal_mm[i]),
                                      movement_tangent_mm=float(tangent_mm[i]),point_face_normal_angle_deg=float(angle),
                                      rgb_projection_movement_px=float(np.linalg.norm(project(matrices['Official+Rigid+D'][0][i:i+1],K)-project(matrices['Official+Rigid'][0][i:i+1],K))),
                                      reference='Rigid -> Rigid+D, same frozen point binding; not GT error',**qual))
            page=out/'visualizations'/subject/f'seed_{seed}_comparison.jpg'
            page.parent.mkdir(parents=True,exist_ok=True)
            comparison_page(cache,subject,seed,contract['methods'],matrices,refn,ids,
                            {'normal':normal_mm,'tangent':tangent_mm},page)
            visuals.append(dict(subject=subject,seed=seed,path=str(page.relative_to(out)),sha256=sha(page)))
            print(f'CACHE_POINT_DIAGNOSTIC {subject} seed={seed}: 40 points, no inference/fitting',flush=True)
    expected=len(subjects)*len(seeds)*5*8
    assert len(rows)==expected
    (out/'PROPAGATED_POINTS.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n' for row in rows),encoding='utf-8')
    save_csv(out/'PER_POINT_DIAGNOSTICS.csv',pair_rows)
    numeric=['movement_total_mm','movement_normal_abs_mm','movement_tangent_mm','point_face_normal_angle_deg',
             'rgb_projection_movement_px','local_edge_change_p99','local_area_ratio_median','local_normal_angle_p95_deg',
             'local_normal_reversal_fraction','local_degenerate_faces']
    means=[]
    for subject in subjects:
        for point in ids:
            selected=[r for r in pair_rows if r['subject']==subject and r['point_id']==point]
            means.append(dict(subject=subject,point_id=point,role=selected[0]['role'],
                              **{key:float(np.mean([r[key] for r in selected])) for key in numeric}))
    save_csv(out/'PER_SUBJECT_POINT_SEED_MEAN.csv',means)
    subject_summary=[]
    for subject in subjects:
        selected=[r for r in means if r['subject']==subject]
        subject_summary.append(dict(subject=subject,role=selected[0]['role'],
                                    **{key:float(np.median([r[key] for r in selected])) for key in numeric}))
    save_csv(out/'PER_SUBJECT_SUMMARY.csv',subject_summary)
    point_summary={p:{key:float(np.median([r[key] for r in means if r['point_id']==p])) for key in numeric} for p in ids}
    source_after={path:sha(path) for path in source_files}
    assert source_after==source_files
    write(out/'SOURCE_PRE_POST_IDENTITY.json',dict(status='PASS',verified_files=len(source_files),before=source_files,after=source_after))
    write(out/'VISUALIZATION_MANIFEST.json',visuals)
    limitations = []
    for row in rows:
        flags = list(row['semantic_flags'])
        if not row['inside_posterior']:
            flags.append('OUTSIDE_POSTERIOR_EVAL_REGION')
        if not row['inside_back_roi']:
            flags.append('OUTSIDE_FROZEN_RGB_BACK_ROI')
        if row['local_degenerate_faces']:
            flags.append('LOCAL_DEGENERATE_FACES')
        if row['heldout_support_count'] == 0:
            flags.append('NO_HELDOUT_SUPPORT_WITHIN_20MM')
        if flags:
            limitations.append(dict(subject=row['subject'],seed=row['seed'],method=row['method'],point_id=row['point_id'],flags=flags))
    write(out/'FAILURE_AND_LIMITATION_RECORDS.json',limitations)
    write(out/'SUMMARY.json',dict(status='CACHE_PROPAGATION_COMPLETED_SEMANTICS_HOLD',subjects=len(subjects),seeds=seeds,
                                  source_meshes=len(subjects)*len(seeds)*5,point_records=len(rows),comparison_pages=len(visuals),
                                  anatomy_verified=False,inference_runs=0,fit_runs=0,per_point=point_summary,
                                  overall_subject_medians={key:float(np.median([r[key] for r in subject_summary])) for key in numeric},
                                  aggregation='seed arithmetic mean -> per subject and point -> equal-subject median; optional within-subject point median',
                                  support_contract='20mm Euclidean radius; train/held-out support diagnostic only; never used to fit, filter or accept',
                                  camera_status='APPROXIMATE_PINHOLE_NOT_INDEPENDENTLY_VALIDATED'))
    print(json.dumps({'status':'CACHE_PROPAGATION_COMPLETED_SEMANTICS_HOLD','point_records':len(rows),'comparison_pages':len(visuals)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['assets','cache','out','sam-repo']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--phase',choices=['assets','dev','full'],required=True)
    args=parser.parse_args()
    if args.phase=='assets':audit_assets(args)
    else:run_points(args,dev=args.phase=='dev')
