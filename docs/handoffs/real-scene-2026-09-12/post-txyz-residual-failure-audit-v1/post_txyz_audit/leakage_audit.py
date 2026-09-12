def audit(features):
    violations=[]
    for feature in features:
        if feature.get("deployment_available") and (feature.get("uses_heldout_information") or feature.get("source_camera") in {"K1","K2","K3","K1_K2_K3"}):violations.append(feature["name"])
    return {"status":"PASS" if not violations else "FAIL_HELDOUT_LEAKAGE","violations":violations}

def assert_no_leakage(features):
    result=audit(features)
    if result["status"]!="PASS":raise RuntimeError(result["status"]+":"+",".join(result["violations"]))
    return result
