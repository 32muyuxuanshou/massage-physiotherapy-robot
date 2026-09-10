"""100-step runtime gate for strict pose/camera-only SAM3D optimization."""
from __future__ import annotations

import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from pose_camera_output_freeze import PoseCameraOutputFreeze, find_final_linear


def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()


def snapshot(output, head):
    scale = output["scale"].detach().clone()
    return {
        "global_rotation": output["global_rot"].detach().clone(),
        "body_pose": output["body_pose"].detach().clone(),
        "camera_raw": output["pred_cam"].detach().clone(),
        "camera_translation": output["pred_cam_t"].detach().clone(),
        "shape": output["shape"].detach().clone(),
        "scale": scale,
        "derived_mhr_scales": (head.scale_mean[None,:] + scale @ head.scale_comps).detach().clone(),
        "hand": output["hand"].detach().clone(),
        "face": output["face"].detach().clone(),
    }


def comparison(reference, current):
    ans={}
    for name, base in reference.items():
        now=current[name]
        ans[name]={"tensor_exact_equal":bool(torch.equal(base,now)),
                   "max_abs_delta":float((base-now).abs().max().cpu())}
    return ans


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sam-repo",type=Path,required=True)
    ap.add_argument("--checkpoint",type=Path,required=True)
    ap.add_argument("--mhr",type=Path,required=True)
    ap.add_argument("--observation",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(args.sam_repo))
    from sam_3d_body import SAM3DBodyEstimator, load_sam_3d_body
    from sam_3d_body.data.utils.prepare_batch import prepare_batch
    from sam_3d_body.utils import recursive_to

    torch.manual_seed(20260910); np.random.seed(20260910)
    torch.use_deterministic_algorithms(True, warn_only=True)
    model,cfg=load_sam_3d_body(str(args.checkpoint),device="cuda",mhr_path=str(args.mhr))
    model.eval()
    controller=PoseCameraOutputFreeze(model)
    estimator=SAM3DBodyEstimator(model,cfg)
    with np.load(args.observation) as raw:
        rgb=raw["rgb_a"].copy(); bbox=raw["bbox_a"].copy(); K=raw["K_a"].copy()
    batch=prepare_batch(rgb,estimator.transform,bbox[None].astype(np.float32),None,None)
    batch=recursive_to(batch,"cuda")
    batch["cam_int"]=torch.as_tensor(K[None],device="cuda").to(batch["img"])
    model._initialize_batch(batch)

    pose_inputs=[]; camera_inputs=[]
    hp=model.head_pose.register_forward_pre_hook(lambda m,a: pose_inputs.append(a[0].detach().clone()))
    hc=model.head_camera.register_forward_pre_hook(lambda m,a: camera_inputs.append(a[0].detach().clone()))
    controller.begin_reference_capture()
    with torch.no_grad(): ref_out=model.forward_step(batch,decoder_type="body")["mhr"]
    frozen_output_reference=controller.end_reference_capture()
    hp.remove(); hc.remove()
    x_pose=pose_inputs[-1]; x_cam=camera_inputs[-1]
    reference=snapshot(ref_out,model.head_pose)

    params=list(controller.parameters())
    optimizer=torch.optim.AdamW(params,lr=2e-4,weight_decay=0.1,betas=(0.9,0.999))
    checkpoints={0:{"outputs":comparison(reference,reference),
                    "frozen_parameter_rows":controller.forbidden_parameter_rows_exact()}}
    for step in range(1,101):
        optimizer.zero_grad(set_to_none=True)
        pose_raw=model.head_pose.proj(x_pose)
        cam_raw=model.head_camera.proj(x_cam)
        # Nonzero deterministic targets exercise both allowed output rows and camera.
        loss=((pose_raw[:,:266]-0.125)**2).mean()+((cam_raw+0.075)**2).mean()
        loss.backward(); optimizer.step(); controller.restore_after_step(optimizer)
        if step in (1,10,100):
            controller.use_frozen_output_reference(frozen_output_reference)
            with torch.no_grad(): out=model.forward_step(batch,decoder_type="body")["mhr"]
            controller.clear_frozen_output_reference()
            checkpoints[step]={"loss":float(loss.detach().cpu()),
                               "outputs":comparison(reference,snapshot(out,model.head_pose)),
                               "frozen_parameter_rows":controller.forbidden_parameter_rows_exact()}

    forbidden=("shape","scale","derived_mhr_scales","hand","face")
    allowed=("global_rotation","body_pose","camera_raw","camera_translation")
    forbidden_pass=all(checkpoints[s]["outputs"][k]["tensor_exact_equal"]
                       for s in (1,10,100) for k in forbidden)
    rows_pass=all(all(checkpoints[s]["frozen_parameter_rows"].values()) for s in (0,1,10,100))
    allowed_changed={k:any(not checkpoints[s]["outputs"][k]["tensor_exact_equal"] for s in (1,10,100))
                     for k in allowed}
    status="PASS_EXACT_OUTPUT_FREEZE" if forbidden_pass and rows_pass and all(allowed_changed.values()) else "OUTPUT_FREEZE_FAILURE"
    test={"task":"POSE_CAMERA_OUTPUT_BLOCK_FREEZE_TEST_V1","status":status,
          "created_at":datetime.now(timezone.utc).isoformat(),"optimizer_steps":100,
          "fixed_input":{"kind":"real HuMMan RGB with dataset ROI and K","observation":str(args.observation),"sha256":sha256(args.observation)},
          "optimizer":{"type":"AdamW","lr":2e-4,"weight_decay":0.1,"betas":[0.9,0.999]},
          "runtime_output_contract":controller.output_contract_json(),
          "method":"freeze pose hidden layers; mask final pose Linear gradients; after every optimizer step exactly restore forbidden rows and zero same-shaped AdamW state rows; at every iterative decoder call clamp forbidden raw outputs to cached Official per-input/per-stage values; train full camera FFN",
          "official_reference_projection_calls":len(frozen_output_reference),
          "checkpoints":checkpoints,"forbidden_fields":list(forbidden),"allowed_fields":list(allowed),
          "forbidden_outputs_exact_all_checkpoints":forbidden_pass,
          "forbidden_parameter_rows_exact_all_checkpoints":rows_pass,
          "allowed_outputs_changed":allowed_changed,
          "determinism":{"torch_use_deterministic_algorithms_warn_only":True,"model_mode":"eval"}}
    (args.output_dir/"POSE_CAMERA_OUTPUT_BLOCK_FREEZE_TEST_V1.json").write_text(json.dumps(test,indent=2),encoding="utf-8")

    final=find_final_linear(model.head_pose.proj)
    entries=[]
    for name,p in model.named_parameters():
        role="frozen"
        output_rows=None
        if p is final.weight or p is final.bias:
            role="partially_trainable_output_rows"
            output_rows={"trainable":[[0,266]],"frozen":[[266,519]]}
        elif name.startswith("head_camera.proj"):
            role="trainable_camera_projection"
        entries.append({"name":name,"shape":list(p.shape),"numel":p.numel(),"requires_grad":p.requires_grad,
                        "role":role,"output_rows":output_rows,
                        "optimizer_group":0 if p.requires_grad else None,
                        "lr":2e-4 if p.requires_grad else None,"weight_decay":0.1 if p.requires_grad else None})
    effective=sum((266*final.in_features+266) if p is final.weight else 0 for p in [])
    manifest={"task":"V2_TRAINABLE_PARAMETER_MANIFEST","status":status,
              "output_contract":controller.output_contract_json(),"optimizer":"AdamW",
              "parameterization_note":"requires_grad applies to full final tensors, but effective trainable rows are 0:266; forbidden rows are exactly restored and optimizer state cleared after every step",
              "effective_trainable_numel":266*final.in_features+266+sum(p.numel() for n,p in model.named_parameters() if n.startswith("head_camera.proj")),
              "entries":entries}
    (args.output_dir/"V2_TRAINABLE_PARAMETER_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    provenance={"task":"RUNTIME_PROVENANCE_V2","status":"FROZEN_RUNTIME_PROVENANCE",
                "server":"172.18.18.151:436","python":sys.executable,"torch":torch.__version__,
                "cuda":torch.version.cuda,"gpu":torch.cuda.get_device_name(),
                "sam_repo":str(args.sam_repo),"checkpoint":{"path":str(args.checkpoint),"sha256":sha256(args.checkpoint)},
                "mhr":{"path":str(args.mhr),"sha256":sha256(args.mhr)},
                "runtime_sources":{str(p):sha256(p) for p in [args.sam_repo/"sam_3d_body/models/heads/mhr_head.py",args.sam_repo/"sam_3d_body/models/heads/camera_head.py"]},
                "test_code_sha256":sha256(Path(__file__)),"freeze_code_sha256":sha256(Path(__file__).with_name("pose_camera_output_freeze.py"))}
    (args.output_dir/"RUNTIME_PROVENANCE_V2.json").write_text(json.dumps(provenance,indent=2),encoding="utf-8")
    print(json.dumps({"status":status,"effective_trainable_numel":manifest["effective_trainable_numel"]},indent=2))

if __name__=="__main__": main()

