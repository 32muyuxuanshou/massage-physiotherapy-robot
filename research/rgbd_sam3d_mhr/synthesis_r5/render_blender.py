"""Render photographed HuMMan textures on their original scans, with exact cameras.

Run with Blender --background --python this_file -- --plan ... --source ... --out ...
No scan deformation or SMPL/MHR topology conversion is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import bpy
import numpy as np
from mathutils import Matrix, Vector


def look_at(position, target):
    q = (Vector(target)-Vector(position)).to_track_quat('-Z', 'Y')
    m = q.to_matrix().to_4x4()
    m.translation = Vector(position)
    return m


def setup_scene(config, hdri):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = config['engine']
    scene.render.resolution_x, scene.render.resolution_y = config['width'], config['height']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = config['cpu_threads']
    if config['engine'] == 'CYCLES':
        scene.cycles.device = 'CPU'
        scene.cycles.samples = config['samples']
        scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('CC0_studio_environment')
    world.use_nodes = True
    nodes = world.node_tree.nodes
    tex = nodes.new('ShaderNodeTexEnvironment')
    tex.image = bpy.data.images.load(str(hdri))
    world.node_tree.links.new(tex.outputs['Color'], nodes['Background'].inputs['Color'])
    nodes['Background'].inputs['Strength'].default_value = .4
    scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.015))
    floor = bpy.context.object
    floor.name, floor.pass_index = 'virtual_studio_floor', 2
    material = bpy.data.materials.new('matte_checker_floor')
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    checker = material.node_tree.nodes.new('ShaderNodeTexChecker')
    checker.inputs['Color1'].default_value = (.17, .19, .21, 1)
    checker.inputs['Color2'].default_value = (.23, .25, .27, 1)
    checker.inputs['Scale'].default_value = 200
    material.node_tree.links.new(checker.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = .9
    floor.data.materials.append(material)
    # Object-index is a separate, un-antialiased visibility pass.
    scene.view_layers[0].use_pass_object_index = True
    scene.view_layers[0].use_pass_z = True
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    layers = tree.nodes.new('CompositorNodeRLayers')
    composite = tree.nodes.new('CompositorNodeComposite')
    tree.links.new(layers.outputs['Image'], composite.inputs['Image'])
    compare = tree.nodes.new('CompositorNodeMath')
    compare.operation = 'COMPARE'
    compare.inputs[1].default_value, compare.inputs[2].default_value = 1, .1
    tree.links.new(layers.outputs['IndexOB'], compare.inputs[0])
    for label, socket in [('mask', compare.outputs[0]), ('zpass', layers.outputs['Depth'])]:
        node = tree.nodes.new('CompositorNodeOutputFile')
        node.name = label
        node.format.file_format = 'OPEN_EXR'
        node.format.color_mode = 'BW'
        node.format.color_depth = '32'
        tree.links.new(socket, node.inputs[0])
    camera_data = bpy.data.cameras.new('calibrated_camera')
    camera = bpy.data.objects.new('calibrated_camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.sensor_fit = 'HORIZONTAL'
    camera_data.sensor_width = 36
    camera_data.clip_start, camera_data.clip_end = .02, 100
    lights = []
    for name, size in [('key', 3), ('fill', 4), ('rim', 2)]:
        data = bpy.data.lights.new(name, 'AREA')
        data.shape, data.size = 'DISK', size
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        lights.append(obj)
    return scene, camera, lights


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--hdri', type=Path, required=True)
    p.add_argument('--limit-assets', type=int)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--threads', type=int, help='CPU threads per renderer; changes scheduling only')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    a.plan, a.source, a.out, a.hdri = [x.resolve() for x in (a.plan, a.source, a.out, a.hdri)]
    plan = json.loads(a.plan.read_text(encoding='utf8'))
    config = plan['render_config']
    if a.threads:
        config = dict(config, cpu_threads=a.threads)
    a.out.mkdir(parents=True, exist_ok=True)
    scene, camera, lights = setup_scene(config, a.hdri)
    # HuMMan world is Kinect color_000 (OpenCV): +Y down, +Z forward, metres.
    # Convert to a Blender scene with +Z up by rotating -90 degrees about X.
    source_rotation = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float)
    chosen = plan['assets'][a.offset:a.offset+a.limit_assets] if a.limit_assets else plan['assets'][a.offset:]
    start = time.monotonic()
    for asset in chosen:
        asset_id = asset['asset_id']
        source = a.source / asset['obj']
        bpy.ops.wm.obj_import(filepath=str(source), forward_axis='NEGATIVE_Z', up_axis='Y')
        objects = list(bpy.context.selected_objects)
        assert len(objects) == 1, 'Expected one textured scan'
        obj = objects[0]
        # OBJ import above assumes +Y up. Correct that convention before floor placement.
        obj.matrix_world = Matrix.Diagonal((1., -1., -1., 1.)) @ obj.matrix_world
        bpy.context.view_layer.update()
        obj.pass_index = 1
        # Read import-transformed coordinates, then normalize only floor and centring.
        v = np.array([obj.matrix_world @ x.co for x in obj.data.vertices], dtype=np.float64)
        span = np.ptp(v, axis=0)
        assert .8 < span[2] < 2.6, f'Source metre/up-axis audit failed: {span}'
        offset = np.array([(v[:, 0].min()+v[:, 0].max())/2,
                           (v[:, 1].min()+v[:, 1].max())/2, v[:, 2].min()])
        obj.location -= Vector(offset)
        bpy.context.view_layer.update()
        v -= offset
        obj.data.calc_loop_triangles()
        faces = np.array([t.vertices[:] for t in obj.data.loop_triangles], dtype=np.int32)
        obj.data.polygons.foreach_set('use_smooth', np.ones(len(obj.data.polygons), dtype=bool))
        for mat in obj.data.materials:
            if mat and mat.use_nodes:
                bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                bsdf.inputs['Roughness'].default_value = .72
                bsdf.inputs['Specular IOR Level'].default_value = .2
        (a.out / 'geometry').mkdir(exist_ok=True)
        # Transform is documented; original scan is never rescaled to fit a body model.
        np.savez_compressed(a.out / 'geometry' / (asset_id+'.npz'),
                            vertices_scene_m=v, faces=faces,
                            source_to_scene_R=source_rotation, source_to_scene_t_m=-offset)
        target = np.array([0, 0, (v[:, 2].min()+v[:, 2].max())/2])
        radius = np.linalg.norm(v-target, axis=1).max()
        for view in plan['cameras']:
            yaw, elevation = np.deg2rad(view['yaw_deg']), np.deg2rad(view['elevation_deg'])
            focal = view['focal_px']
            # Fit a conservative bounding sphere with margin. Distance remains physical metres.
            distance = radius * np.sqrt(1+(focal/(config['height']*.39))**2) + .1
            position = target + distance*np.array([np.sin(yaw)*np.cos(elevation),
                                                   -np.cos(yaw)*np.cos(elevation), np.sin(elevation)])
            camera.matrix_world = look_at(position, target)
            camera.data.lens = focal * camera.data.sensor_width / config['width']
            bpy.context.view_layer.update()
            world_to_blender_camera = np.array(camera.matrix_world.inverted())
            cv_flip = np.diag([1, -1, -1])
            R = cv_flip @ world_to_blender_camera[:3, :3]
            t = cv_flip @ world_to_blender_camera[:3, 3]
            K = np.array([[focal, 0, (config['width']-1)/2],
                          [0, focal, (config['height']-1)/2], [0, 0, 1]], dtype=np.float64)
            right = np.array(camera.matrix_world)[:3, 0]
            for light in plan['lighting']:
                sid = f"{asset_id}_c{view['camera_id']:02d}_l{light['lighting_id']}"
                output = a.out / 'renders' / (sid+'.png')
                output.parent.mkdir(exist_ok=True)
                if output.exists() and (a.out/'renders'/(sid+'.json')).exists():
                    continue
                positions = [position+right*2+np.array([0, 0, 1.6]),
                             position-right*2+np.array([0, 0, .3]),
                             target+(target-position)*.45+np.array([0, 0, 1.5])]
                for i, lamp in enumerate(lights):
                    lamp.matrix_world = look_at(positions[i], target)
                    lamp.data.energy = light['energy_watts'][i]
                    lamp.data.color = light['colors'][i]
                scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = light['hdri_strength']
                scene.render.filepath = str(output)
                for label in ['mask', 'zpass']:
                    scene.node_tree.nodes[label].base_path = str(a.out/'temporary_passes')
                    scene.node_tree.nodes[label].file_slots[0].path = sid+'_'+label+'_'
                bpy.ops.render.render(write_still=True)
                # EXR -> NPY inside Blender avoids third-party EXR interpretation.
                for label in ['mask', 'zpass']:
                    path = a.out/'temporary_passes'/(sid+'_'+label+'_0001.exr')
                    im = bpy.data.images.load(str(path), check_existing=False)
                    values = np.array(im.pixels[:], dtype=np.float32).reshape(config['height'], config['width'], 4)
                    np.save(a.out/'renders'/(sid+'_'+label+'.npy'), np.flipud(values[:, :, 0]))
                    bpy.data.images.remove(im)
                    path.unlink()
                meta = dict(sample_id=sid, asset_id=asset_id, identity=asset['identity'],
                            role=asset['role'], sequence=asset['sequence'], frame=asset['frame'],
                            K=K.tolist(), R_world_to_camera=R.tolist(), T_world_to_camera=t.tolist(),
                            view=view, lighting=light, surface_gt='HuMMan reconstructed clothed scan; no native MHR parameter GT',
                            geometry_file='geometry/'+asset_id+'.npz', render_engine=config['engine'],
                            samples=config['samples'], cpu_threads=config['cpu_threads'])
                (a.out/'renders'/(sid+'.json')).write_text(json.dumps(meta, indent=2))
                print('R5_RENDERED', sid, 'elapsed_s', round(time.monotonic()-start, 1), flush=True)
        bpy.data.objects.remove(obj, do_unlink=True)


if __name__ == '__main__':
    main()
