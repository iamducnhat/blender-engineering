import argparse
import math
import os
import sys
from mathutils import Vector

import bpy


def parse_args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Build an editable looping delivery-drone scene.")
    parser.add_argument("--out", required=True, help="Output .blend path")
    return parser.parse_args(raw)


def ensure_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if parent is None:
        if coll.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(coll)
    else:
        if coll.name not in parent.children:
            parent.children.link(coll)
    return coll


def move_to_collection(obj, coll):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    coll.objects.link(obj)


def mat_principled(name, color, roughness=0.42, metallic=0.0, emission=None, emission_strength=0.0, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, alpha)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if emission is not None:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
                bsdf.inputs["Emission Strength"].default_value = emission_strength
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (*emission, 1.0)
                if "Emission Strength" in bsdf.inputs:
                    bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        # Blender 4.2+ uses surface_render_method; older builds use blend_method.
        try:
            mat.surface_render_method = 'BLENDED'
        except Exception:
            try:
                mat.surface_render_method = 'BLENDED'
            except Exception:
                try:
                    mat.blend_method = 'BLEND'
                except Exception:
                    pass
        if hasattr(mat, "use_transparency_overlap"):
            mat.use_transparency_overlap = False
    return mat


def assign_mat(obj, mat):
    if obj.data and hasattr(obj.data, "materials"):
        obj.data.materials.append(mat)


def smooth(obj):
    if obj.type == 'MESH':
        for poly in obj.data.polygons:
            poly.use_smooth = True


def bevel(obj, width=0.04, segments=3):
    mod = obj.modifiers.new(name="Soft_Edge", type='BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    try:
        mod.angle_limit = math.radians(25)
    except Exception:
        pass
    return mod


def add_cube(name, loc, dims, mat, coll, bevel_width=0.04, parent=None):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel_width:
        bevel(obj, bevel_width, 4)
    assign_mat(obj, mat)
    move_to_collection(obj, coll)
    if parent:
        obj.parent = parent
    return obj


def add_uv(name, loc, scale, mat, coll, parent=None, segments=48, rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth(obj)
    assign_mat(obj, mat)
    move_to_collection(obj, coll)
    if parent:
        obj.parent = parent
    return obj


def add_cylinder(name, p1, p2, radius, mat, coll, parent=None, vertices=32, bevel_width=0.0):
    p1 = Vector(p1)
    p2 = Vector(p2)
    vec = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=vec.length, location=(p1 + p2) * 0.5)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = vec.to_track_quat('Z', 'Y')
    smooth(obj)
    if bevel_width:
        bevel(obj, bevel_width, 3)
    assign_mat(obj, mat)
    move_to_collection(obj, coll)
    if parent:
        obj.parent = parent
    return obj


def add_empty(name, loc, coll, parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = 0.2
    obj.location = loc
    coll.objects.link(obj)
    if parent:
        obj.parent = parent
    return obj


def add_ellipse(name, loc, scale, mat, coll, parent=None, segments=96):
    verts = [(loc[0], loc[1], loc[2])]
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        verts.append((loc[0] + math.cos(a) * scale[0], loc[1] + math.sin(a) * scale[1], loc[2]))
    faces = []
    for i in range(segments):
        faces.append((0, i + 1, ((i + 1) % segments) + 1))
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    assign_mat(obj, mat)
    if parent:
        obj.parent = parent
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def set_linear_action(obj, data_path, index=None):
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    for fc in action_fcurves(action):
        if fc.data_path == data_path and (index is None or fc.array_index == index):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def set_smooth_action(obj, data_path):
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    for fc in action_fcurves(action):
        if fc.data_path == data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'


def action_fcurves(action):
    """Yield legacy or Blender 5.2 layered Action curves."""
    if hasattr(action, "fcurves"):
        yield from action.fcurves
        return
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def key_root_motion(root):
    frames = [1, 37, 73, 109, 145]
    xs = [0.00, 0.055, 0.00, -0.055, 0.00]
    ys = [0.00, 0.020, 0.00, -0.020, 0.00]
    zs = [0.00, 0.075, 0.00, -0.075, 0.00]
    rolls = [0.0, math.radians(6.5), 0.0, math.radians(-6.5), 0.0]
    yaws = [math.radians(-1.2), math.radians(1.5), math.radians(-1.2), math.radians(1.5), math.radians(-1.2)]
    for f, x, y, z, roll, yaw in zip(frames, xs, ys, zs, rolls, yaws):
        root.location = (x, y, z)
        root.rotation_euler = (0.0, roll, yaw)
        root.keyframe_insert(data_path='location', frame=f)
        root.keyframe_insert(data_path='rotation_euler', frame=f)
    set_smooth_action(root, 'location')
    set_smooth_action(root, 'rotation_euler')


def key_shadow_motion(shadow, inner_shadow):
    frames = [1, 37, 73, 109, 145]
    locs = [(0.00, 0.00, 0.026), (0.050, 0.035, 0.026), (0.00, 0.00, 0.026), (-0.050, -0.035, 0.026), (0.00, 0.00, 0.026)]
    scales = [(1.0, 1.0, 1.0), (0.92, 0.94, 1.0), (1.0, 1.0, 1.0), (1.10, 1.06, 1.0), (1.0, 1.0, 1.0)]
    inner_scales = [(0.66, 0.60, 1.0), (0.60, 0.56, 1.0), (0.66, 0.60, 1.0), (0.74, 0.66, 1.0), (0.66, 0.60, 1.0)]
    for f, loc, scl, inner_scl in zip(frames, locs, scales, inner_scales):
        shadow.location = loc
        shadow.scale = scl
        inner_shadow.location = loc
        inner_shadow.scale = inner_scl
        shadow.keyframe_insert(data_path='location', frame=f)
        shadow.keyframe_insert(data_path='scale', frame=f)
        inner_shadow.keyframe_insert(data_path='location', frame=f)
        inner_shadow.keyframe_insert(data_path='scale', frame=f)
    set_smooth_action(shadow, 'location')
    set_smooth_action(shadow, 'scale')
    set_smooth_action(inner_shadow, 'location')
    set_smooth_action(inner_shadow, 'scale')


def key_rotor(rotor, phase=0.0):
    rotor.rotation_euler = (0.0, 0.0, phase)
    rotor.keyframe_insert(data_path='rotation_euler', index=2, frame=1)
    # Ten rotations per second avoids a two-blade rotor landing on the same
    # silhouette at every 24fps sample (12 rps would advance exactly 180 deg).
    rotor.rotation_euler = (0.0, 0.0, phase + math.tau * 60.0)
    rotor.keyframe_insert(data_path='rotation_euler', index=2, frame=145)
    set_linear_action(rotor, 'rotation_euler', 2)


def add_rotor(name, hub_loc, root, drone_coll, dark_mat, blade_mat, index):
    hub = add_cylinder(name + "_Motor", (hub_loc[0], hub_loc[1], hub_loc[2] - 0.11), (hub_loc[0], hub_loc[1], hub_loc[2] + 0.13), 0.17, dark_mat, drone_coll, root, vertices=32, bevel_width=0.025)
    rotor = add_empty(name + "_Spin", hub_loc, drone_coll, root)
    rotor["semantic_role"] = "propeller_spin"
    rotor["rotations_per_second"] = 10.0
    rotor["phase_radians"] = float(index) * (math.pi / 2.0)
    # Two opposed rounded blades with a cyan tip inset for a readable silhouette.
    for side in (-1, 1):
        blade = add_cube(name + ("_Blade_L" if side < 0 else "_Blade_R"), (side * 0.275, 0.0, 0.0), (0.48, 0.085, 0.025), blade_mat, drone_coll, 0.035, rotor)
        blade["semantic_role"] = "propeller_blade"
        blade.rotation_euler[2] = 0.0 if side > 0 else math.pi
        accent = add_cube(name + ("_Tip_L" if side < 0 else "_Tip_R"), (side * 0.49, 0.0, 0.005), (0.08, 0.095, 0.032), blade_mat, drone_coll, 0.025, rotor)
        accent["semantic_role"] = "propeller_tip"
    cap = add_uv(name + "_Cap", hub_loc, (0.09, 0.09, 0.055), blade_mat, drone_coll, rotor, 32, 16)
    cap.location = (0.0, 0.0, 0.12)
    key_rotor(rotor, index * math.pi / 2.0)
    return rotor


def setup_world(scene):
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.032, 0.052, 0.085, 1.0)
        bg.inputs["Strength"].default_value = 0.32
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = 0.15
    scene.view_settings.gamma = 1.0


def add_light(name, light_type, loc, energy, color, size, target, coll):
    data = bpy.data.lights.new(name, type=light_type)
    data.energy = energy
    data.color = color
    if light_type == 'AREA':
        data.shape = 'DISK'
        data.size = size
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = loc
    look_at(obj, target)
    return obj


def main():
    args = parse_args()
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Clean generated data only in this new background process.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)

    scene = bpy.context.scene
    # Unit normalization: geometry remains in its authored Blender-unit layout,
    # while the scene declares a compact physical drone scale. At METRIC
    # scale_length 0.1, one authored unit represents 0.1 m; the measured
    # 3.596 BU rotor-span is therefore approximately 0.360 m.
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.1
    scene.unit_settings.length_unit = 'METERS'
    scene.frame_start = 1
    scene.frame_end = 145
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    # Blender 5.2 exposes the Eevee engine as BLENDER_EEVEE in this build.
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 512
    scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    try:
        scene.render.image_settings.color_depth = '8'
    except Exception:
        pass
    setup_world(scene)

    drone_coll = ensure_collection("Drone_Editable")
    presentation_coll = ensure_collection("Presentation")
    lighting_coll = ensure_collection("Lighting")

    orange = mat_principled("Drone_Orange", (0.95, 0.19, 0.035), roughness=0.30)
    orange_dark = mat_principled("Drone_Orange_Shadow", (0.60, 0.075, 0.018), roughness=0.36)
    cream = mat_principled("Delivery_Cream", (0.96, 0.76, 0.46), roughness=0.34)
    dark = mat_principled("Rotor_Charcoal", (0.015, 0.025, 0.045), roughness=0.24, metallic=0.28)
    blue = mat_principled("Signal_Blue", (0.035, 0.44, 0.85), roughness=0.24, metallic=0.15, emission=(0.02, 0.22, 0.8), emission_strength=2.2)
    pale_blue = mat_principled("Prop_Tip_Blue", (0.20, 0.75, 0.98), roughness=0.20, metallic=0.1, emission=(0.08, 0.35, 0.8), emission_strength=0.8)
    ground_mat = mat_principled("Ground_Matte", (0.14, 0.19, 0.25), roughness=0.82)
    backdrop_mat = mat_principled("Backdrop_Matte", (0.028, 0.052, 0.095), roughness=0.88)
    shadow_mat = mat_principled("Shadow_Soft", (0.008, 0.012, 0.022), roughness=1.0, alpha=0.22)
    inner_shadow_mat = mat_principled("Shadow_Core", (0.003, 0.006, 0.012), roughness=1.0, alpha=0.30)

    root = add_empty("Drone_Root", (0.0, 0.0, 0.0), drone_coll)
    root["asset_id"] = "forward_orange_delivery_drone"
    root["semantic_role"] = "authored_root_hover_loop"
    root["root_motion_policy"] = "in_place"
    root["duration_seconds"] = 6.0
    root["source_route"] = "Original procedural hard-surface construction; no external assets"
    root["unit_assumption"] = "METRIC scale_length=0.1; 1 Blender unit = 0.1 m"

    # Main shell and delivery package.
    upper = add_uv("Body_UpperShell", (0.0, 0.0, 3.37), (1.17, 0.76, 0.29), orange, drone_coll, root)
    upper["semantic_role"] = "primary_body_shell"
    lower = add_cube("Body_LowerShell", (0.0, 0.0, 3.14), (1.18, 0.78, 0.34), orange_dark, drone_coll, 0.16, root)
    lower["semantic_role"] = "lower_body_shell"
    cargo = add_cube("Delivery_Pod", (0.0, -0.03, 2.85), (0.86, 0.62, 0.50), cream, drone_coll, 0.14, root)
    cargo["semantic_role"] = "delivery_payload"
    front_panel = add_cube("Delivery_Pod_FrontPanel", (0.0, -0.355, 2.86), (0.54, 0.028, 0.28), orange, drone_coll, 0.045, root)
    add_cube("Delivery_Pod_Latch", (0.0, -0.378, 2.85), (0.14, 0.022, 0.045), blue, drone_coll, 0.02, root)
    add_uv("Delivery_Status_Lamp", (0.0, -0.405, 3.02), (0.048, 0.018, 0.048), pale_blue, drone_coll, root, 24, 12)

    # A clean cyan signal strip and a small roof dome make the front read at a glance.
    add_cube("Front_SignalStrip", (0.0, -0.765, 3.37), (0.48, 0.025, 0.07), blue, drone_coll, 0.02, root)
    add_uv("Roof_SensorDome", (0.0, 0.02, 3.67), (0.23, 0.23, 0.115), blue, drone_coll, root, 32, 16)
    add_cylinder("Roof_SensorStem", (0.0, 0.02, 3.65), (0.0, 0.02, 3.83), 0.045, dark, drone_coll, root, vertices=20, bevel_width=0.01)

    # Four rigid arms and raised motors.
    hub_xy = [(-1.43, -0.78), (1.43, -0.78), (-1.43, 0.78), (1.43, 0.78)]
    for i, (hx, hy) in enumerate(hub_xy):
        sx = -0.52 if hx < 0 else 0.52
        sy = -0.34 if hy < 0 else 0.34
        add_cylinder("Arm_%02d" % (i + 1), (sx, sy, 3.36), (hx, hy, 3.57), 0.09, dark, drone_coll, root, vertices=24, bevel_width=0.025)
        add_cylinder("ArmAccent_%02d" % (i + 1), (sx * 0.82, sy * 0.82, 3.42), (hx * 0.82, hy * 0.82, 3.58), 0.045, orange, drone_coll, root, vertices=24, bevel_width=0.015)
        add_rotor("Rotor_%02d" % (i + 1), (hx, hy, 3.66), root, drone_coll, dark, pale_blue, i)

    # Camera-facing framing and quiet studio environment.
    ground = add_cube("Ground_Plane", (0.0, 0.0, -0.075), (24.0, 24.0, 0.15), ground_mat, presentation_coll, 0.02)
    ground["semantic_role"] = "shadow_receiver"
    # Extend beyond the camera frustum so the background reads as a quiet studio
    # sweep instead of exposing a finite wall edge at frame left.
    wall = add_cube("Backdrop_Wall", (0.0, 6.6, 5.2), (40.0, 0.18, 10.4), backdrop_mat, presentation_coll, 0.02)
    wall["semantic_role"] = "studio_backdrop"

    shadow = add_ellipse("Shadow_Soft", (0.0, 0.0, 0.026), (1.15, 0.62, 1.0), shadow_mat, presentation_coll)
    shadow["semantic_role"] = "moving_soft_shadow"
    inner_shadow = add_ellipse("Shadow_Core", (0.0, 0.0, 0.029), (0.74, 0.41, 1.0), inner_shadow_mat, presentation_coll)
    inner_shadow["semantic_role"] = "moving_shadow_core"
    key_shadow_motion(shadow, inner_shadow)

    target = (0.0, 0.0, 2.55)
    cam_data = bpy.data.cameras.new("Hero_Camera")
    cam = bpy.data.objects.new("Hero_Camera", cam_data)
    presentation_coll.objects.link(cam)
    cam.location = (7.65, -11.3, 6.35)
    cam_data.lens = 54
    cam_data.sensor_width = 36
    look_at(cam, target)
    scene.camera = cam
    cam["semantic_role"] = "stable_hero_camera"

    add_light("Key_Area", 'AREA', (4.5, -4.8, 8.4), 980, (1.0, 0.73, 0.52), 4.6, (0.0, 0.0, 2.9), lighting_coll)
    add_light("Fill_Area", 'AREA', (-4.2, -2.0, 5.6), 650, (0.42, 0.63, 1.0), 4.0, (0.0, 0.0, 3.2), lighting_coll)
    add_light("Rim_Area", 'AREA', (0.8, 4.2, 7.2), 1120, (0.22, 0.46, 1.0), 3.0, (0.0, 0.0, 3.2), lighting_coll)
    add_light("Soft_Front", 'AREA', (0.0, -2.5, 3.8), 180, (1.0, 0.38, 0.20), 2.8, (0.0, 0.0, 3.1), lighting_coll)

    key_root_motion(root)
    for marker, frame in (("LOOP_START", 1), ("BANK_LEFT_PEAK", 37), ("CENTER_HOVER", 73), ("BANK_RIGHT_PEAK", 109), ("LOOP_END", 145)):
        scene.timeline_markers.new(marker, frame=frame)

    # Record the authored envelope and its physical interpretation in the
    # source file so later inspections can distinguish scene units from meters.
    scene.frame_set(1)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bounds = []
    for obj in drone_coll.all_objects:
        evaluated = obj.evaluated_get(depsgraph)
        if evaluated.type != 'MESH':
            continue
        bounds.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    bound_min = [min(point[i] for point in bounds) for i in range(3)]
    bound_max = [max(point[i] for point in bounds) for i in range(3)]
    dimensions_bu = [bound_max[i] - bound_min[i] for i in range(3)]
    dimensions_m = [value * scene.unit_settings.scale_length for value in dimensions_bu]
    root["authored_dimensions_blender_units"] = [round(value, 6) for value in dimensions_bu]
    root["approx_dimensions_meters"] = [round(value, 6) for value in dimensions_m]
    root["approx_rotor_span_meters"] = round(dimensions_m[0], 6)
    scene["unit_assumption"] = "METRIC scale_length=0.1; authored dimensions are Blender units and display as meters at 0.1 m per unit"
    scene["authored_dimensions_blender_units"] = [round(value, 6) for value in dimensions_bu]
    scene["approx_dimensions_meters"] = [round(value, 6) for value in dimensions_m]
    scene["contract_summary"] = "6-second 24fps in-place hover loop; root banks +/-6.5 degrees, bobs +/-0.075 BU (7.5 mm at scene scale), four rotors spin 10 rps, shadow pad follows sway/bob."
    scene["style_grammar"] = "orange delivery body, cream payload, cyan signal accents, charcoal hardware, midnight studio ground, warm key/cool rim. Compact physical scale: approximately 0.36 m rotor span."
    scene["research_decisions"] = "Stable hero camera; readable primary banking before propeller detail; linear rotor phase; smooth eased hover and shadow movement; complementary geometry kept named/editable; METRIC scale_length 0.1 maps the authored compact drone to approximately 0.36 m span."
    scene["provenance"] = "Original procedural Blender Python construction. No downloaded or external assets used."

    # Keep frame 1 active for a friendly file-open state.
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print("FORWARD_ANIMATION_BUILD_OK", out_path)


if __name__ == "__main__":
    main()
