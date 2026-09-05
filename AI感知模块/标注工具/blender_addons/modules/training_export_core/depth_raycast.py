"""First opaque scene-surface depth at exact pinhole pixel centres.

The geometry buffers deliberately do not use Eevee's jittered Z pass or
silhouette raster coverage. RGB still comes from the same camera/frame.
"""
import bpy
import numpy as np
from mathutils import Vector

from .camera_geometry import world_to_opencv_camera
from .visibility import _hidden_for_render, _same_object


def pixel_center_buffers(scene, camera, skin, intrinsics):
    if camera.data.dof.use_dof or scene.render.use_motion_blur:
        raise ValueError("Pixel-centre geometry requires depth of field and motion blur disabled")
    with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        world_to_cv = world_to_opencv_camera(camera)
        cv_to_world = world_to_cv.inverted()
        rotation = cv_to_world.to_3x3()
        origin = cv_to_world.translation
        z = np.zeros((intrinsics.height, intrinsics.width), dtype=np.float32)
        skin_mask = np.zeros_like(z, dtype=bool)
        near, far = float(camera.data.clip_start), float(camera.data.clip_end)
        for row in range(intrinsics.height):
            y = (row + .5 - intrinsics.cy) / intrinsics.fy
            for col in range(intrinsics.width):
                cv_direction = Vector(((col + .5-intrinsics.cx)/intrinsics.fx, y, 1.))
                direction = (rotation @ cv_direction).normalized()
                ray_max = far * cv_direction.length
                cast_origin = origin
                travelled = 0.
                for attempt in range(64):
                    hit, location, normal, face, obj, matrix = scene.ray_cast(
                        depsgraph, cast_origin, direction, distance=max(0.,ray_max-travelled))
                    if not hit:
                        break
                    depth = float((world_to_cv @ location).z)
                    if not _hidden_for_render(obj) and near <= depth < far:
                        z[row,col] = depth
                        skin_mask[row,col] = _same_object(obj, skin)
                        break
                    travelled = float((location-origin).length)+1e-5
                    if travelled >= ray_max:
                        break
                    cast_origin = origin+direction*travelled
                else:
                    raise RuntimeError("Too many excluded/near-clipped intersections")
        return z, z > 0., skin_mask
