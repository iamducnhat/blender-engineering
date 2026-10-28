import bpy
import math
import os
from mathutils import Vector


BLEND = os.environ.get(
    "BLEND_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "forest_green_camping_lantern.blend"),
)
OUT_DIR = os.environ.get(
    "RENDER_OUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "presentation_renders"),
)


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def make_mat(name, color, roughness=0.45, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if bsdf.inputs.get("Base Color"):
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if bsdf.inputs.get("Roughness"):
            bsdf.inputs["Roughness"].default_value = roughness
        if bsdf.inputs.get("Metallic"):
            bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = (*color, 1.0)
    return mat


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    scene = bpy.context.scene
    os.makedirs(OUT_DIR, exist_ok=True)
    scene.render.engine = 'CYCLES' if os.environ.get('RENDER_ENGINE') == 'cycles' else 'BLENDER_EEVEE'
    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = int(os.environ.get('CYCLES_SAMPLES', '32'))
        scene.cycles.use_denoising = True
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = '8'
    # Optional diagnostic material variant; never enabled for the accepted run.
    if os.environ.get("GLASS_TEST") == "opaque":
        glass = bpy.data.materials.get("Clear Green Glass")
        if glass:
            bsdf = glass.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                if bsdf.inputs.get("Alpha"):
                    bsdf.inputs["Alpha"].default_value = 1.0
                if bsdf.inputs.get("Transmission Weight"):
                    bsdf.inputs["Transmission Weight"].default_value = 0.14
            try:
                glass.surface_render_method = 'DITHERED'
            except Exception:
                pass
    elif os.environ.get("GLASS_TEST") == "transparent":
        glass = bpy.data.materials.get("Clear Green Glass")
        if glass:
            glass.use_nodes = True
            nodes = glass.node_tree.nodes
            links = glass.node_tree.links
            nodes.clear()
            out = nodes.new("ShaderNodeOutputMaterial")
            mix = nodes.new("ShaderNodeMixShader")
            transparent = nodes.new("ShaderNodeBsdfTransparent")
            bsdf = nodes.new("ShaderNodeBsdfPrincipled")
            if bsdf.inputs.get("Base Color"):
                bsdf.inputs["Base Color"].default_value = (0.025, 0.13, 0.07, 1.0)
            if bsdf.inputs.get("Roughness"):
                bsdf.inputs["Roughness"].default_value = 0.05
            if bsdf.inputs.get("Metallic"):
                bsdf.inputs["Metallic"].default_value = 0.0
            if bsdf.inputs.get("Transmission Weight"):
                bsdf.inputs["Transmission Weight"].default_value = 0.15
            mix.inputs[0].default_value = 0.78
            links.new(transparent.outputs[0], mix.inputs[1])
            links.new(bsdf.outputs[0], mix.inputs[2])
            links.new(mix.outputs[0], out.inputs[0])
            try:
                glass.surface_render_method = 'BLENDED'
            except Exception:
                pass
            try:
                glass.use_transparency_overlap = False
                glass.show_transparent_back = False
                glass.use_transparent_shadow = False
            except Exception:
                pass
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass

    # The saved preview rig is left intact in the deliverable; render evidence
    # uses a temporary neutral studio rig that is never saved back to the blend.
    for obj in list(scene.objects):
        if obj.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(obj, do_unlink=True)

    world = scene.world or bpy.data.worlds.new("Presentation World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.006, 0.010, 0.018, 1.0)
        bg.inputs["Strength"].default_value = 0.24

    floor_mat = make_mat("Presentation Floor", (0.032, 0.045, 0.050), roughness=0.32, metallic=0.05)
    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, -0.004))
    floor = bpy.context.object
    floor.name = "Temporary_Presentation_Floor"
    floor.data.materials.append(floor_mat)

    def add_area(name, loc, energy, size, color, target=(0, 0, 2.0)):
        data = bpy.data.lights.new(name, type='AREA')
        data.energy = energy
        data.shape = 'DISK'
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = loc
        look_at(obj, target)
        return obj

    add_area("Hero_Key", (4.6, -5.0, 7.0), 950, 3.8, (1.0, 0.72, 0.48))
    add_area("Hero_Fill", (-4.0, -2.5, 4.0), 700, 4.0, (0.30, 0.52, 1.0))
    add_area("Hero_Rim", (3.2, 4.0, 6.2), 1100, 3.0, (0.38, 0.72, 1.0))
    data = bpy.data.lights.new("Hero_Warm_Point", type='POINT')
    data.energy = 95
    data.color = (1.0, 0.16, 0.02)
    data.shadow_soft_size = 0.5
    point = bpy.data.objects.new("Hero_Warm_Point", data)
    scene.collection.objects.link(point)
    point.location = (0.0, -0.2, 1.75)

    camera_data = bpy.data.cameras.new("Presentation_Camera")
    camera = bpy.data.objects.new("Presentation_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera_data.lens = 56
    camera_data.sensor_width = 36
    camera_data.clip_start = 0.05
    camera_data.clip_end = 100
    scene.camera = camera

    views = {
        "hero": ((6.1, -7.5, 4.9), (0.0, 0.0, 2.15)),
        "front": ((0.0, -8.4, 2.45), (0.0, 0.0, 2.10)),
        "side": ((8.4, 0.0, 2.45), (0.0, 0.0, 2.10)),
        "back": ((0.0, 8.4, 2.45), (0.0, 0.0, 2.10)),
        "top": ((0.0, -0.6, 9.0), (0.0, 0.0, 2.0)),
    }
    if os.environ.get("ONLY_VIEW"):
        views = {os.environ["ONLY_VIEW"]: views[os.environ["ONLY_VIEW"]]}
    for view, (location, target) in views.items():
        camera.location = location
        look_at(camera, target)
        scene.render.filepath = os.path.join(OUT_DIR, f"lantern_{view}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", scene.render.filepath)


if __name__ == "__main__":
    main()
