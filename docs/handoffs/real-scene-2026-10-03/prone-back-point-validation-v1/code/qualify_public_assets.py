"""Read-only qualifications; no model inference and no ground-truth promotion."""
import argparse,base64,csv,hashlib,importlib.util,io,json
from collections import Counter
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageOps
from scipy.spatial import cKDTree
from run_cached_point_diagnostics import sha,read,write,save_csv


def qualify_dmd(root,out):
    source=root/'dmd_bak/historical_v1_quality_audit'
    manifest=read(source/'DOWNLOAD_AUDIT.json');rows=[]
    for i,record in enumerate(manifest['records']):
        image_file,annotation_file=record['files'];image_path=Path(image_file['path']);ann_path=Path(annotation_file['path'])
        assert sha(image_path)==image_file['sha256'] and sha(ann_path)==annotation_file['sha256']
        ann=read(ann_path);external=np.asarray(Image.open(image_path).convert('RGB'))
        embedded=ann.get('imageData');pixel_identity=None;embedded_size=None
        if embedded:
            embedded_arr=np.asarray(Image.open(io.BytesIO(base64.b64decode(embedded))).convert('RGB'))
            embedded_size=[int(embedded_arr.shape[1]),int(embedded_arr.shape[0])]
            pixel_identity=bool(np.array_equal(external,embedded_arr))
        h,w=external.shape[:2];points=[s for s in ann['shapes'] if s.get('shape_type')=='point']
        labels=Counter(s['label'] for s in points)
        outside=sum(not (0<=p[0]<w and 0<=p[1]<h) for s in points for p in s['points'])
        rows.append(dict(sample_id=f'dmd_audit_{i:03d}',image_sha256=image_file['sha256'],annotation_sha256=annotation_file['sha256'],
            image_size=[w,h],embedded_present=bool(embedded),embedded_size=embedded_size,embedded_external_pixels_equal=pixel_identity,
            annotation_size_matches=[w,h]==[ann.get('imageWidth'),ann.get('imageHeight')],outside_points=outside,
            imagePath_basename_matches=Path(ann.get('imagePath','')).name==image_path.name,
            point_count=len(points),point_label_counts=dict(labels),
            geometry_qualification='2D_DEVELOPMENT_ONLY' if outside==0 and [w,h]==[ann.get('imageWidth'),ann.get('imageHeight')] and pixel_identity is not False else 'QUARANTINED_IDENTITY_OR_COORDINATE_ISSUE',
            medical_label_qualification='UNVERIFIED_WITHDRAWN_SOURCE_VERSION',subject_identity='UNVERIFIED',
            visual_review_status='PENDING_PER_IMAGE_REVIEW'))
    write(out/'IMAGE_LABEL_IDENTITY_AUDIT.json',dict(status='205_PAIRS_ACTUAL_HASH_AND_PIXEL_AUDIT_COMPLETE',rows=rows,
        count=len(rows),embedded_images=sum(r['embedded_present'] for r in rows),
        embedded_pixel_matches=sum(r['embedded_external_pixels_equal'] is True for r in rows),
        embedded_pixel_mismatches=sum(r['embedded_external_pixels_equal'] is False for r in rows),
        structural_development_candidates=sum(r['geometry_qualification']=='2D_DEVELOPMENT_ONLY' for r in rows),
        exact_duplicate_images=len(rows)-len({r['image_sha256'] for r in rows}),
        clinical_training_approved=0,limits='Pixel identity does not validate anatomical labels or subject splits; no original files corrected'))
    print('DMD_IDENTITY',len(rows),Counter(r['geometry_qualification'] for r in rows),flush=True)


def qualify_pcdare(root,out,reader_path):
    spec=importlib.util.spec_from_file_location('acquisition_reader',reader_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=root/'pcdare_35f7a1d9';inventory=read(root/'quality_audit/PCDARE_STRUCTURE_AUDIT.json')
    evidence=[]
    for rel in ['StartPCdareRegisterApp.m','Asymmetry/E2_StartPCDrawLineApp.m','Asymmetry/hNet/A_GenerateDepthAsymmMaps.m']:
        p=source/rel
        for i,line in enumerate(p.read_text(errors='replace').splitlines()):
            if 'pc.Location*1000' in line or 'point cloud is in m' in line or 'pcLinePts/1000' in line or 'pcLinePts = jsonObject.pcLinePts/1000' in line:
                evidence.append(dict(file=rel,sha256=sha(p),line=i+1,text=line.strip()))
    assert evidence
    rows=[];candidate_rows=[]
    for i,item in enumerate(x for x in inventory['files'] if not x['derived_output_path']):
        p=source/item['path'];points,_=module.read_ply(p)
        # Only filesystem-near candidates. Numeric agreement is recorded and does not establish identity on its own.
        jsons=sorted(set(p.parent.glob('*.json'))|set((p.parent/'Output').glob('*.json')))
        candidates=[]
        tree=None
        for j in jsons:
            ann=read(j)
            if not isinstance(ann,dict) or not ann.get('pcLinePts'):continue
            line=np.asarray(ann['pcLinePts'],float).reshape(-1,3);idx=np.asarray(ann.get('pcLinePtInds',[]),int)-1
            valid=bool(len(idx)==len(line) and len(idx)>0 and np.all((idx>=0)&(idx<len(points))))
            index_max=None;index_median=None
            if valid:
                dist=np.linalg.norm(points[idx]*1000-line,axis=1);index_max=float(dist.max());index_median=float(np.median(dist))
            if tree is None:tree=cKDTree(points*1000)
            near=tree.query(line)[0]
            exact=bool(valid and index_max<.01)
            cr=dict(scan_id=f'pcscan_{i:03d}',json_path=str(j.relative_to(source)),json_sha256=sha(j),
                    line_points=len(line),one_based_index_count=len(idx),indices_in_range_and_length_match=valid,
                    indexed_point_max_difference_mm=index_max,indexed_point_median_difference_mm=index_median,
                    nearest_scan_point_median_mm=float(np.median(near)),nearest_scan_point_p95_mm=float(np.percentile(near,95)),
                    direct_index_coordinate_match=exact,semantic_status='DRAWN_SURFACE_LINE_NOT_ACUPOINT_OR_VERTEBRAL_GT')
            candidates.append(cr);candidate_rows.append(cr)
        matches=[x for x in candidates if x['direct_index_coordinate_match']]
        rows.append(dict(scan_id=f'pcscan_{i:03d}',path=str(p.relative_to(source)),sha256=sha(p),vertices=len(points),
            source_route=str(p.relative_to(source)).split('/Data/')[0],
            native_unit='m_source_code_contract',native_to_mm=1000,source_unit_evidence='PCdare pcread -> pc.Location*1000; JSON pcLinePts stored mm',
            nearby_json_candidates=len(candidates),direct_index_matches=len(matches),
            binding_status='SCAN_LINE_INDEX_COMPATIBLE_NOT_UNIQUE_SESSION_IDENTITY' if matches else 'GEOMETRY_ONLY_REFERENCE_BINDING_NOT_ESTABLISHED',
            rgb_camera_qualification='NO_CALIBRATED_RGB_PAIR_ESTABLISHED',acupoint_qualification='NONE',
            subject_identity='NOT_PROMOTED_FROM_DIRECTORY',derived_name=any(k in p.stem.lower() for k in ['_cut','_ds']),
            matching_json_paths=';'.join(x['json_path'] for x in matches)))
        if (i+1)%50==0:print('PCDARE_SCAN',i+1,flush=True)
    save_csv(out/'SCAN_REFERENCE_BINDING.csv',rows)
    write(out/'SCAN_REFERENCE_CANDIDATES.json',candidate_rows)
    write(out/'PCDARE_UNIT_AND_PROVENANCE.json',dict(status='324_NON_OUTPUT_SCANS_ENUMERATED',scan_count=len(rows),
        independent_subjects_verified=None,derived_named_scans=sum(r['derived_name'] for r in rows),
        scans_with_index_compatible_lines=sum(r['direct_index_matches']>0 for r in rows),
        available_non_output_geometry=len(rows),calibrated_prone_rgbd_pairs_qualified=0,acupoint_ground_truth_qualified=0,
        unit_source_evidence=evidence,
        limits=['Index-coordinate agreement tests scan association, not anatomical truth or session identity',
                'Output directory and _ds/_cut names are processing hints; non-Output does not guarantee raw acquisition',
                'Directory counts are not independent subject counts; no data used for model training']))
    print('PCDARE_BINDINGS',len(rows),sum(r['direct_index_matches']>0 for r in rows),flush=True)


def behave_inventory(root,out):
    manifest=root/'v2_3/report/BEHAVE_V2_FROZEN_TEST_MANIFEST.json';man=read(manifest);rows=[];visuals=[]
    pages={}
    for spec in man['rows']:
        folder=root/'data/sequences'/spec['sequence']/spec['frame'];cam_images=[]
        for k in range(4):
            paths=[folder/f'k{k}.{ext}' for ext in ['color.jpg','depth.png','person_mask.jpg']]
            rgb=cv2.cvtColor(cv2.imread(str(paths[0])),cv2.COLOR_BGR2RGB);depth=cv2.imread(str(paths[1]),-1);mask=cv2.imread(str(paths[2]),0)
            good=(depth>0)&(mask>127);ys,xs=np.where(mask>127)
            x0,x1=max(0,int(xs.min())-30),min(rgb.shape[1],int(xs.max())+31);y0,y1=max(0,int(ys.min())-30),min(rgb.shape[0],int(ys.max())+31)
            tile=Image.new('RGB',(450,630),'white');crop=ImageOps.contain(Image.fromarray(rgb[y0:y1,x0:x1]),(440,580));tile.paste(crop,((450-crop.width)//2,30))
            ImageDraw.Draw(tile).text((5,5),f"{spec['frame']} K{k} | data only",fill='black')
            cam_images.append(tile)
            person_fit=folder/'person/person_fit.ply'
            rows.append(dict(subject=spec['subject'],sequence=spec['sequence'],frame=spec['frame'],camera=f'K{k}',
                role='K0_INPUT_ONLY' if k==0 else 'HELDOUT_EVALUATION_ONLY',previously_consumed=True,
                image_shape=list(rgb.shape),person_mask_pixels=int((mask>127).sum()),valid_person_depth_pixels=int(good.sum()),
                depth_median_m=float(np.median(depth[good])/1000),display_crop_xyxy=[x0,y0,x1,y1],
                sources=[dict(path=str(p),sha256=sha(p)) for p in paths],person_fit_present=person_fit.exists(),
                posterior_visibility='PENDING_RGB_REFERENCE_REVIEW',posterior_roi_status='NOT_FROZEN'))
        pages.setdefault(spec['sequence'],[]).append(cam_images)
    for sequence,frames in pages.items():
        canvas=Image.new('RGB',(1800,len(frames)*630+40),'white');ImageDraw.Draw(canvas).text((5,5),sequence+' | no model output; display crops only',fill='black')
        for row,tiles in enumerate(frames):
            for k,tile in enumerate(tiles):canvas.paste(tile,(450*k,row*630+40))
        path=out/'behave_reference_review'/(sequence+'.jpg');path.parent.mkdir(parents=True,exist_ok=True);canvas.save(path,quality=92)
        visuals.append(dict(sequence=sequence,path=str(path.relative_to(out)),sha256=sha(path)))
    write(out/'BEHAVE_DATA_COVERAGE_INVENTORY.json',dict(status='FILES_AND_DEPTH_QA_PASS_POSTERIOR_ROI_PENDING',source_manifest_sha256=sha(manifest),
        frozen_frame_count=len(man['rows']),camera_views=len(rows),subjects=sorted({r['subject'] for r in rows}),rows=rows,
        model_runs=0,limits='Dataset person mask includes clothes; valid depth does not prove visible posterior skin or an anatomical reference'))
    write(out/'BEHAVE_DATA_REVIEW_VISUAL_MANIFEST.json',visuals)
    print('BEHAVE_DATA_QA',len(man['rows']),len(rows),'posterior ROI not yet frozen',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--acquired-root',type=Path,required=True);p.add_argument('--behave-root',type=Path,required=True)
    p.add_argument('--reader-code',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['dmd','pcdare','behave'],required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.phase=='dmd':qualify_dmd(a.acquired_root,a.out)
    elif a.phase=='pcdare':qualify_pcdare(a.acquired_root,a.out,a.reader_code)
    else:behave_inventory(a.behave_root,a.out)
