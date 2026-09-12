TYPES=("DEPTH_SUPPORT_LOW","DEPTH_CONTAMINATION","OBJECT_INTERACTION","CORRESPONDENCE_FAILURE","REGISTRATION_INSTABILITY","EXTREME_TRANSLATION","OFFICIAL_POSE_ERROR","OFFICIAL_SHAPE_ERROR","LOCAL_SURFACE_ERROR","MULTIPLE_FACTORS","UNKNOWN")

def empty_assessment(frame_id):
    return {"frame_id":frame_id,"candidate_root_causes":[],"requires_visual_review":True,"automatic_causal_conclusion":False}

def validate_assessment(value):
    for candidate in value["candidate_root_causes"]:
        if candidate["type"] not in TYPES or candidate["confidence"] not in {"LOW","MEDIUM","HIGH"} or not candidate.get("evidence"):raise ValueError("INVALID_ROOT_CAUSE_CANDIDATE")
    if value.get("automatic_causal_conclusion"):raise ValueError("AUTOMATIC_CAUSAL_CONCLUSION_FORBIDDEN")
    return value
