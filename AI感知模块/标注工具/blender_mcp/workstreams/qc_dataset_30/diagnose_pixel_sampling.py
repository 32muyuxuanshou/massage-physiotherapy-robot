"""Isolated Eevee sampling diagnostic; never saves or edits input Blend."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
import training_export_core.render_buffers as rb
from training_export_core.camera_geometry import world_to_opencv_camera, camera_intrinsics

root = Path(sys.argv[sys.argv.index("--")+1])
root.mkdir(parents=True, exist_ok=False)
scene = bpy.context.scene
camera = scene.camera
skin = scene.objects["SKEL-skin-female"]
original = rb._copy_render_settings
reports = []
for trial in ("default", "center_sample"):
    def settings(source, target, **kwargs):
        original(source, target, **kwargs)
        if trial == "center_sample":
            target.eevee.taa_render_samples = 1
            target.render.filter_size = 0.01
    rb._copy_render_settings = settings
    result = rb.render_scene_buffers(source_scene=scene, camera=camera, skin_object=skin,
        output_dir=root/trial, width=1280, height=1024, debug_keep_intermediates=True)
    raw = root/trial/"debug_intermediates"/"full_scene"
    position = rb._read_float_image(next(raw.glob("position_*.exr")))
    matrix = world_to_opencv_camera(camera)
    k = camera_intrinsics(scene, camera, width=1280, height=1024)
    row, col = 982, 696
    p = matrix @ Vector(position[row,col,:3])
    projected = [k.fx*p.x/p.z+k.cx, k.fy*p.y/p.z+k.cy]
    hits=[]
    dg = bpy.context.evaluated_depsgraph_get()
    for dy in (-.25, 0., .25):
        for dx in (-.25, 0., .25):
            d = camera.matrix_world.to_3x3() @ Vector(((col+.5+dx-k.cx)/k.fx, -(row+.5+dy-k.cy)/k.fy, -1.))
            hit, pos, normal, face, obj, _ = scene.ray_cast(dg, camera.matrix_world.translation, d.normalized())
            hits.append({"dx":dx, "dy":dy,"object":obj.name if hit else None,"zc":float((matrix @ pos).z) if hit else None})
    reports.append({"trial":trial,"depth":float(result.scene_depth_z[row,col]),
        "mask":bool(result.skin_mask[row,col]), "position_projection":projected,
        "projected_minus_center":[projected[0]-col-.5, projected[1]-row-.5], "rays":hits})
(root/"diagnostic.json").write_text(json.dumps(reports,indent=2),encoding="utf-8")
print(json.dumps(reports))
