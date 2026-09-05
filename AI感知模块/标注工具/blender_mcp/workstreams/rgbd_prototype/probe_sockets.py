import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
view_layer = scene.view_layers[0]
view_layer.use_pass_z = True
view_layer.use_pass_position = True
view_layer.use_pass_object_index = True
scene.use_nodes = True
node = scene.node_tree.nodes.new("CompositorNodeRLayers")
for i, socket in enumerate(node.outputs):
    if socket.name in {"Depth", "Position", "IndexOB", "Image"}:
        print(i, socket.name, socket.identifier, "unavailable", socket.is_unavailable, "enabled", socket.enabled)
