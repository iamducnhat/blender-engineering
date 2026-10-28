import bpy
import math
import os
from mathutils import Vector


OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FINAL_BLEND = os.path.join(OUT_DIR, "forest_green_camping_lantern.blend")
PRIMARY_BLEND = os.path.join(OUT_DIR, "checkpoint_primary_shape.blend")
SECONDARY_BLEND = os.path.join(OUT_DIR, "checkpoint_secondary_structure.blend")
ACTIVE_COLLECTION = None


def set_input(node, name, value):
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def material(name, color, metallic=0.0, roughness=0.45, transmission=0.0,
             emission=None, emission_strength=0.0, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, alpha)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, "Base Color", (*color, 1.0))
        set_input(bsdf, "Metallic", metallic)
        set_input(bsdf, "Roughness", roughness)
        set_input(bsdf, "IOR", 1.45)
        set_input(bsdf, "Transmission Weight", transmission)
        if emission is not None:
            set_input(bsdf, "Emission Color", (*emission, 1.0))
            set_input(bsdf, "Emission Strength", emission_strength)
        set_input(bsdf, "Alpha", alpha)
    # Blender 4/5 uses surface_render_method; keep this guarded for portability.
    try:
        if alpha < 0.99:
            mat.surface_render_method = 'BLENDED'
            mat.use_transparency_overlap = False
            mat.show_transparent_back = False
            mat.use_transparent_shadow = False
            mat.use_backface_culling_shadow = True
    except Exception:
        pass
    return mat


def configure_diffuser_gradient(mat):
    """Give the emissive sleeve a restrained deterministic amber value gradient."""
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "Roughness", 0.24)
    set_input(bsdf, "Emission Color", (1.0, 0.035, 0.002, 1.0))
    set_input(bsdf, "Emission Strength", 0.9)
    set_input(bsdf, "Alpha", 1.0)
    tex = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.12
    ramp.color_ramp.elements[0].color = (0.20, 0.006, 0.001, 1.0)
    ramp.color_ramp.elements[1].position = 0.88
    ramp.color_ramp.elements[1].color = (0.72, 0.040, 0.004, 1.0)
    links.new(tex.outputs.get("Generated"), separate.inputs.get("Vector"))
    links.new(separate.outputs.get("Z"), ramp.inputs.get("Fac"))
    links.new(ramp.outputs.get("Color"), bsdf.inputs.get("Base Color"))
    links.new(bsdf.outputs.get("BSDF"), out.inputs.get("Surface"))


GREEN = material("Forest Green Powder Coat", (0.025, 0.16, 0.075), metallic=0.72, roughness=0.28)
GREEN_DARK = material("Forest Green Dark Recess", (0.008, 0.035, 0.016), metallic=0.45, roughness=0.34)
BRASS = material("Warm Brushed Brass", (0.44, 0.20, 0.055), metallic=0.86, roughness=0.24)
BRASS_LIGHT = material("Highlight Brass", (0.76, 0.42, 0.12), metallic=0.9, roughness=0.18)
GLASS = material("Clear Green Glass", (0.025, 0.13, 0.07), metallic=0.0, roughness=0.035,
                 transmission=0.46, alpha=0.46)
DIFFUSER = material("Warm Amber Diffuser", (0.55, 0.02, 0.002), metallic=0.0, roughness=0.24,
                    emission=(1.0, 0.035, 0.002), emission_strength=0.9)
BLACK = material("Vent Interior", (0.004, 0.006, 0.005), metallic=0.05, roughness=0.35)
RUBBER = material("Handle Grip", (0.012, 0.025, 0.017), metallic=0.18, roughness=0.48)


def link_obj(obj, collection=None, semantic=None):
    target = collection or ACTIVE_COLLECTION or bpy.context.scene.collection
    if obj.name not in target.objects:
        target.objects.link(obj)
    # Operators already link to the active collection; remove any duplicate links.
    for coll in list(obj.users_collection):
        if coll != target:
            coll.objects.unlink(obj)
    if semantic:
        obj["semantic_part"] = semantic
        obj["part_id"] = semantic
    return obj


def bevel(obj, width=0.04, segments=3):
    mod = obj.modifiers.new("Controlled edge bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    return obj


def finish_mesh(obj, mat, smooth=True, width=0.04, segments=3, semantic=None):
    if mat:
        obj.data.materials.append(mat)
    if smooth and hasattr(obj.data, "polygons"):
        for poly in obj.data.polygons:
            poly.use_smooth = True
    if width:
        bevel(obj, width, segments)
    return link_obj(obj, semantic=semantic)


def cylinder(name, radius, depth, z, mat, semantic=None, vertices=96, bevel_width=0.035):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.object
    obj.name = name
    return finish_mesh(obj, mat, smooth=True, width=bevel_width, semantic=semantic or name)


def cube(name, dims, loc, mat, semantic=None, bevel_width=0.035, rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rotation or (0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)
    return finish_mesh(obj, mat, smooth=True, width=bevel_width, semantic=semantic or name)


def torus(name, major, minor, z, mat, semantic=None, rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=96, minor_segments=18,
                                     location=(0, 0, z), rotation=rotation or (0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    return finish_mesh(obj, mat, smooth=True, width=0.0, semantic=semantic or name)


def sphere(name, radius, loc, scale, mat, semantic=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)
    return finish_mesh(obj, mat, smooth=True, width=0.0, semantic=semantic or name)


def curve_tube(name, points, mat, semantic=None, radius=0.075):
    curve = bpy.data.curves.new(name, type='CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 24
    curve.bevel_depth = radius
    curve.bevel_resolution = 6
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = co
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve)
    (ACTIVE_COLLECTION or bpy.context.scene.collection).objects.link(obj)
    curve.materials.append(mat)
    if semantic:
        obj["semantic_part"] = semantic
        obj["part_id"] = semantic
    return obj


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def create_collections():
    global ACTIVE_COLLECTION
    root = bpy.context.scene.collection
    lantern = bpy.data.collections.new("Lantern Assembly")
    root.children.link(lantern)
    for obj in list(root.objects):
        root.objects.unlink(obj)
        lantern.objects.link(obj)
    ACTIVE_COLLECTION = lantern
    return lantern


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Factory startup clears data-blocks, so instantiate the material palette
    # after the reset rather than retaining removed RNA references.
    global GREEN, GREEN_DARK, BRASS, BRASS_LIGHT, GLASS, DIFFUSER, BLACK, RUBBER
    GREEN = material("Forest Green Powder Coat", (0.025, 0.16, 0.075), metallic=0.72, roughness=0.28)
    GREEN_DARK = material("Forest Green Dark Recess", (0.008, 0.035, 0.016), metallic=0.45, roughness=0.34)
    BRASS = material("Warm Brushed Brass", (0.44, 0.20, 0.055), metallic=0.86, roughness=0.24)
    BRASS_LIGHT = material("Highlight Brass", (0.76, 0.42, 0.12), metallic=0.9, roughness=0.18)
    GLASS = material("Clear Green Glass", (0.025, 0.13, 0.07), metallic=0.0, roughness=0.035,
                     transmission=0.46, alpha=0.46)
    DIFFUSER = material("Warm Amber Diffuser", (0.55, 0.02, 0.002), metallic=0.0, roughness=0.24,
                        emission=(1.0, 0.035, 0.002), emission_strength=0.9)
    BLACK = material("Vent Interior", (0.004, 0.006, 0.005), metallic=0.05, roughness=0.35)
    RUBBER = material("Handle Grip", (0.012, 0.025, 0.017), metallic=0.18, roughness=0.48)
    configure_diffuser_gradient(DIFFUSER)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.1
    scene.unit_settings.length_unit = 'METERS'
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = 'RGBA'
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Lantern Studio World")
    scene.world.color = (0.008, 0.012, 0.01)
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass

    lantern = create_collections()
    scene["asset_name"] = "Stylized Forest Green Camping Lantern"
    scene["route_id"] = "hard_surface_rotational_hybrid_v1"
    scene["design_intent"] = "forest-green metal cage, clear chamber, warm light, carry handle, brass accents"
    scene["units_note"] = "1 Blender unit = 1 meter"
    scene["provenance"] = "Procedural local Blender Python; no external assets or images"
    scene["accepted_repair"] = "material_glass_and_diffuser_v1"

    # Primary silhouette: wide foot, glass chamber, shoulder and dome.
    base = cylinder("Lantern_Base", 1.02, 0.34, 0.17, GREEN, "base", bevel_width=0.055)
    lower = cylinder("Lower_Body_Collar", 0.95, 0.46, 0.55, GREEN, "body_lower", bevel_width=0.045)
    torus("Base_Brass_Ring", 0.88, 0.045, 0.36, BRASS, "brass_base_ring")
    torus("Lower_Brass_Ring", 0.87, 0.035, 0.82, BRASS, "brass_lower_ring")
    cube("Base_Front_Badge", (0.34, 0.045, 0.20), (0.0, -1.015, 0.54), BRASS, "brass_badge", bevel_width=0.025)

    # Glass and the glowing diffuser remain separate, editable parts.
    glass = cylinder("Glass_Chamber", 0.78, 1.90, 1.78, GLASS, "glass_chamber", bevel_width=0.012)
    diffuser = cylinder("Light_Diffuser", 0.48, 1.52, 1.78, DIFFUSER, "light_diffuser", bevel_width=0.02)
    # A dark inner wick cap makes the light source read as a lantern rather than a plain tube.
    cylinder("Diffuser_Top_Cap", 0.50, 0.08, 2.56, BRASS_LIGHT, "diffuser_top_cap", bevel_width=0.018)
    cylinder("Diffuser_Bottom_Cap", 0.50, 0.08, 1.00, BRASS_LIGHT, "diffuser_bottom_cap", bevel_width=0.018)
    torus("Chamber_Rim_Bottom", 0.76, 0.052, 0.84, BRASS, "brass_chamber_bottom")
    torus("Chamber_Rim_Top", 0.76, 0.052, 2.72, BRASS, "brass_chamber_top")
    # Stage checkpoint: primary lantern silhouette and chamber relationship.
    bpy.ops.wm.save_as_mainfile(filepath=PRIMARY_BLEND)

    # Four diagonal cage ribs leave the chamber visible from the hero/front view.
    rib_radius = 0.865
    for idx, angle in enumerate((45, 135, 225, 315), start=1):
        a = math.radians(angle)
        rib = cube(f"Cage_Rib_{idx:02d}", (0.15, 0.15, 1.90),
                   (rib_radius * math.cos(a), rib_radius * math.sin(a), 1.78),
                   GREEN, f"cage_rib_{idx:02d}", bevel_width=0.035)
        rib.rotation_euler[2] = a

    # Shoulder and cap frame the glass and provide a strong top silhouette.
    cylinder("Upper_Collar", 0.96, 0.26, 2.92, GREEN, "body_upper", bevel_width=0.045)
    cylinder("Hood_Cap", 1.00, 0.25, 3.16, GREEN, "hood_cap", bevel_width=0.05)
    torus("Hood_Brass_Edge", 0.89, 0.045, 3.30, BRASS, "brass_hood_edge")
    sphere("Dome", 1.0, (0, 0, 3.40), (0.98, 0.98, 0.48), GREEN, "dome")
    cylinder("Vent_Neck", 0.30, 0.25, 3.78, GREEN_DARK, "vent_neck", bevel_width=0.035)
    torus("Vent_Brass_Ring", 0.26, 0.038, 3.90, BRASS_LIGHT, "brass_vent_ring")
    cylinder("Vent_Top", 0.28, 0.18, 3.98, GREEN, "vent_top", bevel_width=0.03)
    # Vent slots are explicit dark recess parts for graphic readability.
    for idx in range(8):
        a = math.radians(idx * 45)
        cube(f"Vent_Slot_{idx:02d}", (0.07, 0.15, 0.07),
             (0.235 * math.cos(a), 0.235 * math.sin(a), 3.99),
             BLACK, f"vent_slot_{idx:02d}", bevel_width=0.01)

    # Functional carry handle with brass pivot hardware.
    handle_points = [(-1.00, 0.0, 3.08), (-1.18, 0.0, 3.72), (-0.78, 0.0, 4.35),
                     (0.0, 0.0, 4.57), (0.78, 0.0, 4.35), (1.18, 0.0, 3.72), (1.00, 0.0, 3.08)]
    handle = curve_tube("Carry_Handle", handle_points, GREEN, "carry_handle", radius=0.085)
    handle["role"] = "carry handle"
    for side, x in (("L", -1.00), ("R", 1.00)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.15, depth=0.22,
                                            location=(x, 0, 3.08), rotation=(math.radians(90), 0, 0))
        pivot = bpy.context.object
        pivot.name = f"Handle_Pivot_{side}"
        finish_mesh(pivot, BRASS_LIGHT, smooth=True, width=0.022, semantic=f"handle_pivot_{side.lower()}")
        torus(f"Handle_Pivot_Ring_{side}", 0.15, 0.025, 3.08, BRASS, f"handle_pivot_ring_{side.lower()}", rotation=(math.radians(90), 0, 0))

    # Front control: brass plate, dark switch and a tiny indicator.
    cube("Front_Switch_Plate", (0.40, 0.055, 0.18), (0.0, -0.95, 2.70), BRASS, "front_switch_plate", bevel_width=0.025)
    cube("Front_Switch", (0.13, 0.085, 0.10), (0.0, -1.005, 2.70), BLACK, "front_switch", bevel_width=0.020)
    sphere("Status_Indicator", 0.035, (0.22, -1.005, 2.70), (1.0, 0.55, 1.0), DIFFUSER, "status_indicator")

    # Small brass fasteners at the lower shoulder reinforce the assembly logic.
    for idx, (x, y) in enumerate(((-0.60, -0.68), (0.60, -0.68), (-0.60, 0.68), (0.60, 0.68)), start=1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.045, location=(x, y, 0.84))
        fast = bpy.context.object
        fast.name = f"Brass_Fastener_{idx:02d}"
        finish_mesh(fast, BRASS_LIGHT, smooth=True, width=0.0, semantic=f"brass_fastener_{idx:02d}")

    # Stage checkpoint: secondary cage, cap, handle, controls, and fasteners.
    bpy.ops.wm.save_as_mainfile(filepath=SECONDARY_BLEND)

    # Studio camera and lights are part of the editable file's preview setup.
    bpy.ops.object.camera_add(location=(6.2, -7.0, 5.0))
    camera = bpy.context.object
    camera.name = "Preview_Camera"
    camera.data.lens = 58
    camera.data.sensor_width = 36
    look_at(camera, (0, 0, 2.1))
    scene.camera = camera
    camera["role"] = "presentation camera"

    def area(name, loc, energy, size, color):
        bpy.ops.object.light_add(type='AREA', location=loc)
        lamp = bpy.context.object
        lamp.name = name
        lamp.data.energy = energy
        lamp.data.shape = 'DISK'
        lamp.data.size = size
        lamp.data.color = color
        look_at(lamp, (0, 0, 1.9))
        return lamp

    area("Key_Softbox", (4.8, -4.8, 7.0), 900, 4.0, (1.0, 0.84, 0.68))
    area("Fill_Softbox", (-4.0, -1.5, 4.0), 600, 3.0, (0.38, 0.62, 1.0))
    area("Rim_Strip", (2.5, 3.8, 5.2), 850, 2.5, (0.52, 0.8, 1.0))
    bpy.ops.object.light_add(type='POINT', location=(0.0, -0.1, 1.75))
    glow = bpy.context.object
    glow.name = "Warm_Chamber_Light"
    glow.data.energy = 125
    glow.data.color = (1.0, 0.13, 0.015)
    glow.data.shadow_soft_size = 0.45

    # Save the accepted final delivery after preview camera and lights are present.
    bpy.ops.wm.save_as_mainfile(filepath=FINAL_BLEND)
    print("SAVED", FINAL_BLEND)


if __name__ == "__main__":
    main()
