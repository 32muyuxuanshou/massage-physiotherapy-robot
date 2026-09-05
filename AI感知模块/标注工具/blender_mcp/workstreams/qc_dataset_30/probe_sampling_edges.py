"""Independent dense silhouette-ray diagnostic, not a relaxed acceptance test."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Matrix, Vector

sample, output = map(Path, sys.argv[sys.argv.index("--")+1:])
depth = np.load(sample/"scene_depth_z.npy", allow_pickle=False)
inp = oiio.ImageInput.open(str(sample/"skin_mask.png"))
mask = np.asarray(inp.read_image(oiio.UINT8)).reshape(depth.shape) > 0
inp.close()
edge=np.zeros_like(mask)
edge[1:,:] |= mask[1:,:] != mask[:-1,:]
edge[:-1,:] |= mask[1:,:] != mask[:-1,:]
edge[:,1:] |= mask[:,1:] != mask[:,:-1]
edge[:,:-1] |= mask[:,1:] != mask[:,:-1]
scene=bpy.context.scene
camera=scene.camera
dg=bpy.context.evaluated_depsgraph_get()
world_to_cv=Matrix.Diagonal((1.,-1.,-1.,1.)) @ camera.matrix_world.inverted()
projection=camera.calc_matrix_camera(dg,x=depth.shape[1],y=depth.shape[0],scale_x=1.,scale_y=1.)
projection_k=[projection[0][0]*depth.shape[1]/2,
              projection[1][1]*depth.shape[0]/2,
              (1-projection[0][2])*depth.shape[1]/2,
              (1+projection[1][2])*depth.shape[0]/2]
labels=json.loads((sample/"labels.json").read_text(encoding="utf-8"))
declared=labels["camera"]["intrinsics"]
fx,fy,cx,cy=[float(declared[key]) for key in ("fx","fy","cx","cy")]
k_roundoff=max(abs(a-b) for a,b in zip(projection_k,(fx,fy,cx,cy)))
if k_roundoff>1e-3:
    raise ValueError("Declared K disagrees with independent Blender projection")
# Cast the dataset's declared camera, not a second camera formed by float32
# projection round-off. The general verifier separately checks K/projection.
inv=world_to_cv.inverted()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"independent_verifier"))
from blender_scene_probe import _first_rendered_hit
mismatches=[]
max_error=0.
for row,col in np.argwhere(edge):
    direction=inv.to_3x3() @ Vector(((float(col)+.5-cx)/fx,(float(row)+.5-cy)/fy,1.))
    hit,pos,normal,face,obj,_=_first_rendered_hit(scene,dg,inv.translation,direction.normalized(),100.)
    z=float((world_to_cv @ pos).z) if hit else 0.
    error=abs(z-float(depth[row,col]))
    max_error=max(max_error,error)
    if error > .003 or bool(mask[row,col]) != bool(hit and obj.name=="SKEL-skin-female"):
        mismatches.append({"row":int(row),"column":int(col),"raster_depth":float(depth[row,col]),"ray_z":z,"ray_object":obj.name if hit else None,"depth_error":error})
report={"pixel_count":int(edge.sum()),"mismatch_count":len(mismatches),"max_depth_error_m":max_error,"mismatches":mismatches,
        "ray_intrinsics":"declared sample K, independently checked against Blender projection",
        "float32_projection_K_roundoff_px":k_roundoff}
output.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!="mismatches"}))
