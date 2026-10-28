#!/usr/bin/env python3
"""Create a small deterministic Blender scene for the integration tests.

This file is executed by Blender, not by the host Python interpreter.  It
intentionally contains both source/evaluated geometry evidence and contract
failure fixtures so the tests exercise the adapter's real background process.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--with-dependencies",
        action="store_true",
        help="Create an existing //textures image and //libraries linked blend.",
    )
    parser.add_argument(
        "--with-faraway-helpers",
        action="store_true",
        help="Add far-away camera, light, and empty presentation helpers.",
    )
    parser.add_argument(
        "--with-beveled-curve",
        action="store_true",
        help="Add a beveled poly curve whose evaluated mesh bounds are testable.",
    )
    return parser.parse_args(argv)


def _move_to_collection(obj, collection) -> None:
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def _set_part_id(obj, part_id: str) -> None:
    obj["part_id"] = part_id
    obj["asset_role"] = "semantic_test_part"


def main() -> int:
    args = _parse_args()

    import bpy

    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.frame_set(1)

    model_collection = bpy.data.collections.new("MODEL")
    scene.collection.children.link(model_collection)

    dependencies_root = out.parent
    textures_dir = dependencies_root / "textures"
    libraries_dir = dependencies_root / "libraries"
    relative_image_path = textures_dir / "relative.png"
    linked_library_path = libraries_dir / "linked_part.blend"
    image = None
    missing_image_path = None
    if args.with_dependencies:
        textures_dir.mkdir(parents=True, exist_ok=True)
        libraries_dir.mkdir(parents=True, exist_ok=True)
        # Save a real PNG beside the source blend, then store the Blender path
        # as //textures/relative.png.  Validation must resolve it against the
        # source blend directory rather than a temporary working directory.
        image = bpy.data.images.new("RelativeTexture", width=1, height=1)
        image.generated_color = (0.18, 0.55, 0.92, 1.0)
        image.filepath_raw = str(relative_image_path)
        image.file_format = "PNG"
        image.save()
        image.filepath = "//textures/relative.png"
    else:
        # A deliberately missing image makes external-path validation
        # observable in the baseline fixture.
        missing_image_path = out.parent / "missing-texture.png"
        image = bpy.data.images.new("MissingTexture", width=1, height=1)
        image.filepath = str(missing_image_path)

    body_material = bpy.data.materials.new("BodyMaterial")
    body_material.use_nodes = True
    nodes = body_material.node_tree.nodes
    links = body_material.node_tree.links
    texture_node = nodes.new("ShaderNodeTexImage")
    texture_node.name = "MissingTextureNode"
    texture_node.image = image
    principled = nodes.get("Principled BSDF")
    if principled is not None:
        links.new(texture_node.outputs["Color"], principled.inputs["Base Color"])
    body_material.diffuse_color = (0.16, 0.34, 0.62, 1.0)

    wheel_material = bpy.data.materials.new("WheelMaterial")
    wheel_material.diffuse_color = (0.025, 0.03, 0.04, 1.0)

    # The cube remains the native source mesh.  The unapplied bevel makes the
    # evaluated mesh statistics observably different from source statistics.
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.8), scale=(1.0, 0.6, 0.8))
    body = bpy.context.object
    body.name = "Body"
    body.data.name = "BodySourceMesh"
    _move_to_collection(body, model_collection)
    _set_part_id(body, "body")
    body.data.materials.append(body_material)
    bevel = body.modifiers.new("EvaluatedBevel", "BEVEL")
    bevel.width = 0.08
    bevel.segments = 3
    bevel.limit_method = "ANGLE"

    for name, x in (("WheelA", -0.72), ("WheelB", 0.72)):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=0.32,
            depth=0.18,
            location=(x, 0.0, 0.32),
            rotation=(math.pi / 2.0, 0.0, 0.0),
        )
        wheel = bpy.context.object
        wheel.name = name
        wheel.data.name = f"{name}SourceMesh"
        _move_to_collection(wheel, model_collection)
        _set_part_id(wheel, "wheel")
        wheel.data.materials.append(wheel_material)

    # This is intentionally an Empty: its semantic id is a spoof of a mesh
    # part, and its display size is zero so the extent proof must fail too.
    spoof = bpy.data.objects.new("SpoofEmpty", None)
    model_collection.objects.link(spoof)
    spoof.location = (0.0, 0.0, 0.8)
    spoof.empty_display_type = "CUBE"
    spoof.empty_display_size = 0.0
    _set_part_id(spoof, "spoofed_mesh")

    linked_objects = []
    if args.with_dependencies:
        # Write one object to an actual external .blend, remove its local
        # authoring copy, and link it back into the scene.  The final main
        # blend stores the library path as //libraries/linked_part.blend.
        bpy.ops.mesh.primitive_cube_add(location=(1.35, 0.0, 0.35), scale=(0.15, 0.15, 0.35))
        library_object = bpy.context.object
        library_object.name = "LinkedLibraryPart"
        library_object.data.name = "LinkedLibraryMesh"
        _set_part_id(library_object, "linked")
        library_mesh = library_object.data
        bpy.data.libraries.write(str(linked_library_path), {library_object})
        bpy.data.objects.remove(library_object, do_unlink=True)
        if library_mesh.users == 0:
            bpy.data.meshes.remove(library_mesh)

        with bpy.data.libraries.load(str(linked_library_path), link=True) as (data_from, data_to):
            data_to.objects = ["LinkedLibraryPart"]
        for linked_object in data_to.objects:
            if linked_object is not None:
                model_collection.objects.link(linked_object)
                linked_objects.append(linked_object)

    curve_object = None
    if args.with_beveled_curve:
        curve_data = bpy.data.curves.new("BeveledCurveData", type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.resolution_u = 1
        curve_data.bevel_depth = 0.085
        curve_data.bevel_resolution = 2
        curve_data.fill_mode = "FULL"
        spline = curve_data.splines.new("POLY")
        spline.points.add(2)
        for point, coordinate in zip(
            spline.points,
            ((-0.75, 0.0, 0.25, 1.0), (0.0, 0.0, 1.25, 1.0), (0.75, 0.0, 0.75, 1.0)),
        ):
            point.co = coordinate
        curve_object = bpy.data.objects.new("BeveledCurve", curve_data)
        model_collection.objects.link(curve_object)
        _set_part_id(curve_object, "curve")

    # Make the saved source itself free of selection/UI state that could leak
    # into a stable evidence fingerprint.
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    bpy.context.view_layer.objects.active = None
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    if args.with_dependencies:
        for library in bpy.data.libraries:
            if Path(bpy.path.abspath(library.filepath)).resolve() == linked_library_path.resolve():
                library.filepath = "//libraries/linked_part.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(out))

    if args.with_faraway_helpers:
        camera_data = bpy.data.cameras.new("FarAwayCameraData")
        far_camera = bpy.data.objects.new("FarAwayCamera", camera_data)
        scene.collection.objects.link(far_camera)
        far_camera.location = (100000.0, 100000.0, 100000.0)
        camera_data.lens = 50.0
        scene.camera = far_camera

        light_data = bpy.data.lights.new("FarAwayLightData", type="POINT")
        far_light = bpy.data.objects.new("FarAwayLight", light_data)
        scene.collection.objects.link(far_light)
        far_light.location = (-100000.0, -100000.0, 100000.0)
        light_data.energy = 100.0

        far_empty = bpy.data.objects.new("FarAwayEmpty", None)
        scene.collection.objects.link(far_empty)
        far_empty.location = (100000.0, -100000.0, -100000.0)
        far_empty.empty_display_type = "CUBE"
        far_empty.empty_display_size = 25.0
        bpy.ops.wm.save_as_mainfile(filepath=str(out))

    print(
        json.dumps(
            {
                "status": "PASS",
                "blend": str(out),
                "missing_external_file": str(missing_image_path) if missing_image_path else None,
                "relative_image": str(relative_image_path) if args.with_dependencies else None,
                "linked_library": str(linked_library_path) if args.with_dependencies else None,
                "source_objects": [
                    "Body",
                    "WheelA",
                    "WheelB",
                    "SpoofEmpty",
                    *[obj.name for obj in linked_objects],
                    *(["FarAwayCamera", "FarAwayLight", "FarAwayEmpty"] if args.with_faraway_helpers else []),
                    *([curve_object.name] if curve_object is not None else []),
                ],
                "evaluated_modifier": "Body.EvaluatedBevel",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
