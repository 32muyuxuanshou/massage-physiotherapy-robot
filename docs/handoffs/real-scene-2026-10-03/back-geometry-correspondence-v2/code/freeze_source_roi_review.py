"""Source ROI refinements from original RGB, before any new BEHAVE inference."""
from common import ROOT,write

OVERRIDES={24:[.78,.38],25:[.78,.47],26:[.72,.32],29:[.78,.23],39:[.45,.23],
    48:[.45,.23],49:[.62,.23],54:[.42,.23],57:[.4,.24],58:[.4,.20],59:[.4,.23],
    81:[.4,.30],83:[.35,.34],85:[.35,.30],86:[.36,.28],92:[.62,.35],108:[.60,.20],
    121:[.4,.22],133:[.60,.23],137:[.38,.18],140:[.35,.23],
    162:[.35,.20],163:[.40,.35],164:[.30,.22],166:[.35,.23],168:[.4,.20],177:[.38,.2],178:[.35,.23],
    186:[.55,.18],201:[.6,.27],208:[.62,.35],212:[.50,.20],214:[.38,.22],215:[.6,.32],
    228:[.50,.25],237:[.5,.23],239:[.5,.25],261:[.65,.30],276:[.65,.40],278:[.4,.35],279:[.40,.30],
    295:[.67,.23],298:[.38,.20]}

def main():
    out=ROOT/'b_qualification';write(out/'SOURCE_CENTER_OVERRIDES.json',{str(k):v for k,v in OVERRIDES.items()})
    write(out/'SOURCE_ROI_REVIEW_HISTORY.json',dict(status='ORIGINAL_RGB_REFINEMENT_PRE_MODEL',
        default_proposals_are_not_final_ROIs=True,
        corrected_source_boxes=list(OVERRIDES),excluded_candidate_153='Initial K0 contact classification corrected: anterior shirt, not posterior',
        all_changes_from_RGB_only=True,model_outputs_used=0,
        support_metrics_not_used_to_set_centers='centers moved only from background/arm/hip/ball to visible back',
        source_patch_same_surface_requires_heldout_RGB_confirmation=True))

if __name__=='__main__':main()
