"""All-pixel analytic plane/foreground/hidden-object test in a fresh scene."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from training_export_core.camera_geometry import camera_intrinsics
from training_export_core.depth_raycast import pixel_center_buffers

output=Path(sys.argv[sys.argv.index("--")+1])
scene=bpy.data.scenes.new("ANALYTIC_DEPTH_ONLY")
scene.unit_settings.system="METRIC"
scene.unit_settings.scale_length=1.
scene.render.resolution_x=128
scene.render.resolution_y=128
scene.render.resolution_percentage=100
cam_data=bpy.data.cameras.new("TEST_PINHOLE")
cam_data.lens=36.
cam_data.sensor_width=36.
cam_data.sensor_fit="HORIZONTAL"
cam=bpy.data.objects.new("TEST_PINHOLE",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam

def plane(name,z,extent):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(-extent,-extent,z),(extent,-extent,z),(extent,extent,z),(-extent,extent,z)],[],[(0,1,2),(0,2,3)])
    obj=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    return obj

skin=plane("SKIN_PLANE",-2.,3.)
front=plane("FRONT_OCCLUDER",-1.,.25)
hidden=plane("HIDDEN_RENDER_PLANE",-.5,3.)
hidden.hide_render=True
bpy.context.window.scene=scene
bpy.context.view_layer.update()
k=camera_intrinsics(scene,cam)
z,valid,mask=pixel_center_buffers(scene,cam,skin,k)
rows,cols=np.indices((128,128))
inside=(np.abs((cols+.5-64)/128)<.25)&(np.abs((rows+.5-64)/128)<.25)
expected=np.where(inside,1.,2.)
error=np.abs(z-expected)
checks={"all_16384_depths_analytic":bool(error.max()<1e-6),
        "all_valid":bool(valid.all()),"skin_ownership_analytic":bool(np.array_equal(mask,~inside)),
        "hidden_plane_still_hidden":bool(hidden.hide_render),
        "skin_not_hidden":not skin.hide_render,
        "camera_unchanged":list(cam.location)==[0.,0.,0.]}
report={"passed":all(checks.values()),"checks":checks,"pixel_count":16384,
        "max_depth_error_m":float(error.max()),"foreground_pixel_count":int(inside.sum()),
        "notice":"Expected 1 m/2 m depth and occluder rectangle computed analytically; not selected from renderer/raycast outputs."}
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report))
if not report["passed"]:
    raise RuntimeError("Analytic depth test failed")
