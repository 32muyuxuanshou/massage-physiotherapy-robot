VALID_AVAILABILITY={"AVAILABLE_NOW","DERIVABLE_FROM_EXISTING_FILES","REQUIRES_K0_DATA_READ","REQUIRES_TXYZ_REPLAY","NOT_AVAILABLE"}

def validate_feature(feature):
    required={"name","description","unit","source_camera","source_file","deployment_available","uses_heldout_information","requires_replay","availability_status"}
    missing=required-set(feature)
    if missing:raise ValueError(f"FEATURE_SCHEMA_MISSING {sorted(missing)}")
    if feature["availability_status"] not in VALID_AVAILABILITY:raise ValueError("FEATURE_AVAILABILITY_INVALID")
    if feature["deployment_available"] and feature["uses_heldout_information"]:raise ValueError("HELDOUT_FEATURE_MARKED_DEPLOYMENT_AVAILABLE")
    return feature
