from .config import HELDOUT_CAMERAS

def classify_frame(row):
    labels=[]
    for camera in HELDOUT_CAMERAS:
        values=row["cameras"][camera];delta=float(values["txyz"]["median_mm"])-float(values["official"]["median_mm"])
        labels.append({"camera":camera,"delta_mm":delta,"improved":delta<0})
    n=sum(item["improved"] for item in labels)
    return {"n_improved":n,"frame_outcome_class":f"GROUP_{'DCBA'[n]}","heldout_camera_labels":labels,"role":"OFFLINE_AUDIT_LABEL"}
