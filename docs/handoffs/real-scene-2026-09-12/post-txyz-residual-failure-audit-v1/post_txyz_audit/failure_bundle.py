from .frame_outcomes import classify_frame
from .failure_taxonomy import empty_assessment
from .k0_feature_extractor import extract_existing

def build(row, schema):
    spec=row["spec"];frame_id="/".join((spec["subject"],spec["sequence"],spec["frame"]))
    base=f"data/sequences/{spec['sequence']}/{spec['frame']}"
    return {"frame_id":frame_id,"k0_source_references":{"rgb":base+'/k0.color.jpg',"depth":base+'/k0.depth.png',"mask":base+'/k0.person_mask.jpg'},"k0_features":extract_existing(row,schema),"replay_only_fields":{"iteration_history":"REQUIRES_REPLAY","correspondence_statistics":"REQUIRES_REPLAY","k0_residual_histogram":"REQUIRES_REPLAY"},"heldout_outcome":classify_frame(row),"root_cause":empty_assessment(frame_id),"provenance":{"k0_features":"deployment candidates","heldout_outcome":"offline audit label only"}}
