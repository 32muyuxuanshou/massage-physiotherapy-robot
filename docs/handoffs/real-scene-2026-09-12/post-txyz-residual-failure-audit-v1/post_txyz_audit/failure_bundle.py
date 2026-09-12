from .frame_outcomes import classify_frame
from .failure_taxonomy import empty_assessment
from .k0_feature_extractor import extract_existing

def build(row, schema, k0_sources=None, feature_values=None):
    spec=row["spec"];frame_id="/".join((spec["subject"],spec["sequence"],spec["frame"]))
    sources=k0_sources or {"status":"REQUIRES_SEQUENCE_ROOT_RESOLUTION","rgb":None,"depth":None,"mask":None}
    features=extract_existing(row,schema)
    for name,value in (feature_values or {}).items():features[name]={"status":"ACQUIRED_FOR_FORMAL_AUDIT","value":value}
    return {"frame_id":frame_id,"k0_source_references":sources,"k0_features":features,"heldout_outcome":classify_frame(row),"root_cause":empty_assessment(frame_id),"provenance":{"k0_features":"K0-only deployment candidates","heldout_outcome":"K1/K2/K3 offline audit label only"}}
