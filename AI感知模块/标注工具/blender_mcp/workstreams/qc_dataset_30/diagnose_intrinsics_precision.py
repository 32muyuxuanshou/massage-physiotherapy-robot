import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

labels_path,output=map(Path,sys.argv[sys.argv.index("--")+1:])
labels=json.loads(labels_path.read_text(encoding="utf-8"))
scene=bpy.context.scene
camera=scene.camera
dg=bpy.context.evaluated_depsgraph_get()
mat=Matrix.Diagonal((1.,-1.,-1.,1.))@camera.matrix_world.inverted()
inv=mat.inverted()
projection=camera.calc_matrix_camera(dg,x=1280,y=1024,scale_x=1.,scale_y=1.)
declared=labels["camera"]["intrinsics"]
ks=[("declared_K",declared["fx"],declared["fy"]),
    ("float32_projection_K",projection[0][0]*640,projection[1][1]*512)]
rows=[]
for name,fx,fy in ks:
    direction=(inv.to_3x3()@Vector(((563.5-640)/fx,(938.5-512)/fy,1.))).normalized()
    hit,pos,normal,face,obj,_=scene.ray_cast(dg,inv.translation,direction,distance=100.)
    rows.append({"name":name,"fx":fx,"fy":fy,"hit_object":obj.name if hit else None,"face":face,"depth_z":float((mat@pos).z) if hit else None})
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(rows,indent=2),encoding="utf-8")
print(json.dumps(rows))
