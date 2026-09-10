"""Plan/materialize frozen SYSTEM_VAL or SYSTEM_SEALED multi-action RGB-D rows."""
from __future__ import annotations

import argparse, hashlib, json, os, shutil, subprocess, tempfile
from collections import defaultdict
from pathlib import Path

CAMERAS = ("kinect_008", "kinect_009")
SEVEN_ZIP = Path("/raid5/xuhd/MRC/dataset/tools/7zip/7zz")
SEED = "humman-system-multipose-20260910"

def read(p): return json.loads(Path(p).read_text(encoding="utf8"))
def write(p,v):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(8<<20),b""): h.update(b)
    return h.hexdigest()
def rank(text): return hashlib.sha256(text.encode()).hexdigest()

def require_winner(path):
    w=read(path)
    if w.get("status") != "FROZEN_BEFORE_FIRST_SELECTOR_SEALED_ACCESS": raise RuntimeError("winner is not frozen before SEALED access")
    if w.get("arm") not in ("S","M"): raise RuntimeError("winner arm must be S or M")
    if w.get("loser_arm_sealed_access_forbidden") is not True or w.get("final_reserve_access_forbidden") is not True: raise RuntimeError("sealed exclusions are not frozen")
    ckpt=Path(w["checkpoint"]["path"]); expected=w["checkpoint"]["sha256"]
    if not ckpt.is_file() or ckpt.stat().st_size != w["checkpoint"]["bytes"] or sha(ckpt) != expected: raise RuntimeError("winner checkpoint/hash mismatch")
    return {**w,"winner":f"MODEL_{w['arm']}","checkpoint_path":str(ckpt),"checkpoint_sha256":expected}

def plan(args):
    winner=require_winner(args.winner_freeze)
    split=read(args.subject_split); inv=read(args.inventory)
    chosen=split["groups"][args.split_name]; reserve=set(split["groups"]["FINAL_DEEP_RESERVE"])
    if set(chosen)&reserve: raise RuntimeError("identity split overlap")
    seqs=defaultdict(list)
    for r in inv["packed_coverage"]["sequence_records"]:
        if r["structurally_usable"] and r["subject"] in chosen: seqs[r["subject"]].append(r)
    observations=[]
    for subject in chosen:
        candidates=sorted(seqs[subject],key=lambda r:rank(f"{SEED}:sequence:{r['sequence']}"))
        if not candidates: raise RuntimeError(f"no structural sequence for {subject}")
        for row in candidates:
            cams={c["camera"]:c for c in row["cameras"]}; common=None
            for cam in CAMERAS:
                ids={i for lo,hi in cams[cam]["paired_frame_ranges"] for i in range(lo,hi+1)}
                common=ids if common is None else common&ids
            ids=sorted(common); frames=sorted({ids[round((len(ids)-1)*q)] for q in (.25,.5,.75)})
            observations.append({"subject":subject,"sequence":row["sequence"],"action":row["action"],"action_name":row.get("action_name"),"frame_ids":frames,"camera_candidates":list(CAMERAS),"split":args.split_name})
    depth_archive={}; archive_by_name={a["path"].replace("\\","/").rsplit("/",1)[-1]:a for a in inv["archives"]}
    for name,a in archive_by_name.items():
        if name.startswith("point_kinect_depth_part_"):
            for seq in a["sequences"]: depth_archive[seq]=name
    members=defaultdict(set)
    for r in observations:
        seq=r["sequence"]; members["point_cameras.7z"].add(f"{seq}/cameras.json")
        for cam in CAMERAS:
            members["point_kinect_color_part_02.7z"].add(f"{seq}/kinect_color/{cam}.mp4")
            for frame in r["frame_ids"]:
                members[depth_archive[seq]].add(f"{seq}/kinect_depth/{cam}/{frame:06d}.png");members["point_kinect_mask.7z"].add(f"{seq}/kinect_mask/{cam}/{frame:06d}.png")
    out={"status":f"{args.split_name}_EXTRACTION_PLAN_FROZEN","winner":winner["winner"],"winner_checkpoint_sha256":winner["checkpoint_sha256"],"subject_split_sha256":sha(args.subject_split),"inventory_sha256":sha(args.inventory),"server_archive_root":str(args.archive_root),"server_workset_root":str(args.workset_root),"observations":observations,"selected_subjects":chosen,"final_reserve_subjects_excluded":sorted(reserve),"selected_pixels":True,"final_reserve_pixels_selected":False,"archives":[{"file":n,"sha256":archive_by_name[n]["prior_report_sha256_not_rehashed_this_scan"],"members":sorted(m)} for n,m in sorted(members.items())]}
    write(args.output,out)

def materialize(args):
    winner=require_winner(args.winner_freeze); p=read(args.plan)
    if not p["status"].endswith("_EXTRACTION_PLAN_FROZEN") or p["winner_checkpoint_sha256"]!=winner["checkpoint_sha256"]: raise RuntimeError("plan/winner mismatch")
    if p["final_reserve_pixels_selected"] is not False: raise RuntimeError("Final Reserve selection forbidden")
    if set(p["selected_subjects"])&set(p["final_reserve_subjects_excluded"]): raise RuntimeError("split overlap")
    root=Path(p["server_workset_root"]); root.mkdir(parents=True,exist_ok=True)
    report={"status":"RUNNING","winner_checkpoint_sha256":winner["checkpoint_sha256"],"archives":[],"views":[],"final_reserve_pixels_materialized":False}
    write(args.report,report); env=dict(os.environ); env["LD_LIBRARY_PATH"]="/raid5/xuhd/miniconda3/lib"
    for ar in p["archives"]:
        source=Path(p["server_archive_root"])/ar["file"]
        missing=[m for m in ar["members"] if not (root/m).is_file()]
        if missing:
            with tempfile.NamedTemporaryFile("w",encoding="utf8",delete=False,dir=Path(args.report).parent,suffix=".txt") as f:
                f.write("\n".join(missing)+"\n"); listfile=f.name
            try: subprocess.run([str(SEVEN_ZIP),"x",str(source),f"-o{root}","-y","-scsUTF-8",f"@{listfile}"],check=True,env=env)
            finally: Path(listfile).unlink(missing_ok=True)
        if any(not (root/m).is_file() for m in ar["members"]): raise RuntimeError(f"incomplete {ar['file']}")
        report["archives"].append({"file":ar["file"],"selected_files":len(ar["members"]),"newly_extracted":len(missing)})
        write(args.report,report)
    import cv2, numpy as np
    for r in p["observations"]:
        for cam in CAMERAS:
            cap=cv2.VideoCapture(str(root/r["sequence"]/"kinect_color"/f"{cam}.mp4")); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for frame in r["frame_ids"]:
                cap.set(cv2.CAP_PROP_POS_FRAMES,frame); ok,rgb=cap.read()
                depth=cv2.imread(str(root/r["sequence"]/"kinect_depth"/cam/f"{frame:06d}.png"),cv2.IMREAD_UNCHANGED)
                mask=cv2.imread(str(root/r["sequence"]/"kinect_mask"/cam/f"{frame:06d}.png"),cv2.IMREAD_UNCHANGED)
                if not ok or depth is None or mask is None or not np.any(depth) or not np.any(mask): raise RuntimeError((r["sequence"],cam,frame))
                target=root/r["sequence"]/"selected_rgb"/cam/f"{frame:06d}.png"; target.parent.mkdir(parents=True,exist_ok=True)
                if not cv2.imwrite(str(target),rgb): raise RuntimeError(target)
                report["views"].append({"subject":r["subject"],"sequence":r["sequence"],"camera":cam,"frame_id":frame,"video_frame_count":count})
            cap.release()
    report["status"]=p["status"].replace("EXTRACTION_PLAN_FROZEN","DECODE_PASS_GEOMETRY_QA_PENDING"); write(args.report,report)

if __name__=="__main__":
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="command",required=True)
    p=sub.add_parser("plan"); p.add_argument("--split-name",choices=("SYSTEM_VAL","SYSTEM_SEALED"),required=True); p.add_argument("--winner-freeze",type=Path,required=True); p.add_argument("--subject-split",type=Path,required=True); p.add_argument("--inventory",type=Path,required=True); p.add_argument("--archive-root",type=Path,required=True); p.add_argument("--workset-root",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    e=sub.add_parser("materialize"); e.add_argument("--winner-freeze",type=Path,required=True); e.add_argument("--plan",type=Path,required=True); e.add_argument("--report",type=Path,required=True)
    a=ap.parse_args(); plan(a) if a.command=="plan" else materialize(a)

