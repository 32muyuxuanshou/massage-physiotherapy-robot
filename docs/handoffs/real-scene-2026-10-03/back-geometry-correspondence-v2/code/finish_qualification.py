"""Close bounded data qualification, including its failure to supply the cohort."""
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageOps
from common import ROOT,BEHAVE,read,write,sha

Q=ROOT/'b_qualification'
SOURCE_INVALID={48:'source patch still includes arm',108:'ball occludes target patch',
    162:'source patch intersects background/shoulder edge',208:'source patch partly hair/neck',
    215:'source patch includes background'}

def nonadjacent(rows):
    chosen=[]
    for r in sorted(rows,key=lambda r:float(r['frame'][1:])):
        if not chosen or float(r['frame'][1:])-float(chosen[-1]['frame'][1:])>=3:chosen.append(r)
    return chosen

def main():
    inv=read(Q/'CANDIDATE_INVENTORY.json');proposal=read(Q/'PROPOSED_PATCH_SUPPORT.json')['rows']
    per=[];limits=[];source=[];all_exclusions=[]
    for r in proposal:
        ok=r['candidate_index'] not in SOURCE_INVALID
        source.append(dict(candidate_index=r['candidate_index'],source_rgb_review='PASS_GEOMETRIC_BACK_PATCH' if ok else 'FAIL',
            reason=SOURCE_INVALID.get(r['candidate_index'],'clothed posterior patch; no vertebral localization'),
            source_roi_center_fraction=r['source_roi_center_fraction'],medical_truth=False))
    allowed={r['candidate_index'] for r in source if r['source_rgb_review'].startswith('PASS')}
    eligible=[r for r in proposal if r['candidate_index'] in allowed and r['numerically_common_back_possible']]
    for s in ['Sub03','Sub04','Sub05','Sub06','Sub07']:
        seqs=sorted({r['sequence'] for r in eligible if r['subject']==s});available=[];counts=[]
        for seq in seqs:
            rs=[r for r in eligible if r['sequence']==seq];selected=nonadjacent(rs);available.extend(selected)
            counts.append(dict(sequence=seq,numeric_support_frames=len(rs),max_3s_spaced_count=len(selected),candidate_ids=[r['candidate_index'] for r in selected]))
        count=len(available);per.append(dict(subject=s,numeric_candidate_frames=sum(c['numeric_support_frames'] for c in counts),
            nonadjacent_upper_bound=count,sequences=len(seqs),planned_6_frames_2_sequences_possible=count>=6 and len(seqs)>=2,
            note='upper bound; heldout RGB projected-patch confirmation not complete for other subjects',by_sequence=counts))
    assert next(r for r in per if r['subject']=='Sub07')['nonadjacent_upper_bound']==3
    for f in inv['frames']:
        i=f['candidate_index'];r=next((r for r in proposal if r['candidate_index']==i),None)
        reason=('INITIAL_RGB_NOT_CLEAR_BACK' if r is None else 'SOURCE_ROI_REVIEW_FAILED' if i not in allowed else
                'NO_BIDIRECTIONAL_COMMON_DEPTH_SUPPORT' if not r['numerically_common_back_possible'] else 'NUMERIC_CANDIDATE_NOT_FORMAL_SELECTED')
        all_exclusions.append(dict(**f,status=reason,model_runs=0))
    write(Q/'SOURCE_PATCH_RGB_QA.json',dict(status='COMPLETE',rows=source,
        excluded_initial_candidate_153='anterior shirt; removed before projected-patch qualification'))
    write(Q/'COMMON_SUPPORT_COHORT_LIMITS.json',dict(status='INSUFFICIENT_FOR_PLANNED_5_BY_6',per_subject=per,
        total_numeric_candidates=len(eligible),planned_frames=30,maximum_under_6_per_person_cap=sum(min(6,r['nonadjacent_upper_bound']) for r in per),
        main_limitation='Sub07: one sequence, at most 3 nonadjacent timestamps under frozen RGB/50mm depth support definition',
        numeric_support_is_not_medical_or_calibration_accuracy=True,
        other_subject_heldout_patch_visual_confirmation='NOT_COMPLETED_AFTER_COHORT_NO_GO',
        no_new_BEHAVE_inference=True,no_new_BEHAVE_fit=True))
    write(Q/'FROZEN_MANIFEST.json',dict(status='NOT_ISSUED_COHORT_QUALIFICATION_FAILED',rows=[],
        required_target=30,reason='insufficient source/heldout same-patch support in planned validation subject Sub07',
        model_runs=0,contract_sha256=sha(Q/'QUALIFICATION_CONTRACT.json'),
        qualification_sha256=sha(Q/'COMMON_SUPPORT_COHORT_LIMITS.json')))
    write(Q/'EXCLUSION_REASONS.json',all_exclusions)
    # Audit the limiting subject's actual source/target projections, including failures.
    views={(v['candidate_index'],v['camera']):v for v in inv['views']};visuals=[]
    for r in [r for r in proposal if r['subject']=='Sub07']:
        i=r['candidate_index'];page=Image.new('RGB',(1600,650),'white')
        for k in range(4):
            rec=views[i,k];rgb=Image.open(rec['source_files'][0]['path']).convert('RGB')
            polygon=r['source_polygon_px'] if k==0 else r['target_polygons_px'][k-1]
            ImageDraw.Draw(rgb).polygon([tuple(p) for p in polygon],outline=(0,180,255),width=5)
            thumb=ImageOps.contain(rgb.crop(rec['display_crop_xyxy']),(390,550));page.paste(thumb,(k*400+(400-thumb.width)//2,70))
            d=ImageDraw.Draw(page);d.text((k*400+5,5),f'#{i} {r["frame"]} K{k}: source/projected patch',fill='black')
            if k:
                sup=r['supports'][k-1];d.text((k*400+5,25),f"support {sup['input_to_target_support']:.1%}/{sup['target_to_input_support']:.1%}",fill='black')
                med=sup['source_to_target_median_mm'];d.text((k*400+5,45),f'NN med {med} mm / pass {sup["numeric_pass"]}',fill='black')
        file=Q/'private_images'/f'Sub07_projected_patch_{i}.jpg';page.save(file,quality=95)
        visuals.append(dict(candidate_index=i,path=str(file),sha256=sha(file)))
    write(Q/'LIMITING_SUBJECT_PATCH_VISUALS.json',visuals)
    print('COHORT_NO_GO',len(eligible),per,flush=True)

if __name__=='__main__':main()
