import hashlib, json
from pathlib import Path

def load_frozen(path):
    if not path:return {"status":"BLOCKED_PENDING_BACK_REGION_DEFINITION"}
    path=Path(path)
    if not path.is_file():raise RuntimeError("BLOCKED_PENDING_BACK_REGION_DEFINITION")
    value=json.loads(path.read_text());required={"definition_source","version","topology","vertex_indices","face_indices"}
    if not required.issubset(value) or not value["vertex_indices"] or not value["face_indices"]:raise RuntimeError("INVALID_FROZEN_BACK_REGION")
    value["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest();return value

def require_ready(value):
    if value.get("status")!="READY_FROZEN_BACK_REGION":raise RuntimeError("BLOCKED_PENDING_BACK_REGION_DEFINITION")
