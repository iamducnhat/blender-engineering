# Revolve and profile recipe

Use this recipe for bottles, vases, jars, knobs, columns, wheels, lampshades, turned furniture, and any object whose primary silhouette is genuinely axis-symmetric. Read `routing.md` first: a radial base does not make an asymmetrical handle, panel break, hinge, or ornament rotational.

## Build order

1. Extract the visible profile, axis, center, top/bottom openings, wall thickness, and intended camera. If the reference has no scale, record a relative proportion assumption rather than inventing an absolute measurement.
2. Create a named editable profile curve or mesh. Include enough profile points for changes in silhouette and material/edge transitions; do not spend points on a straight segment that will not read.
3. Use Spin/revolve around a deliberate 3D-cursor center and axis. Choose radial sampling from curvature, target camera, and runtime budget. Use a full revolution only when the form closes; use a partial angle for open or intentionally incomplete forms.
4. Weld the full-revolution seam, recalculate normals, and inspect for doubled vertices, flipped faces, pinching, caps, and nonuniform scale. Preserve the profile source so a proportion repair does not require rebuilding the whole asset.
5. Add thickness, lip, neck, foot, cap, threads, seams, and openings as named secondary geometry. Use Solidify or a controlled inner profile when wall thickness is part of the visual or print requirement.
6. Build non-radial attachments as separate assemblies with explicit support/contact relationships. Use curves, bevels, booleans, or small procedural generators only after the main silhouette reads.
7. Apply deliberate bevel/normal/material treatment and inspect hero, front, side, back, top/opening, and a close-up of the critical transition.

## Decisions that matter

- Preserve silhouette before radial density. More segments cannot repair a wrong profile.
- Use a clean profile for the primary mass and separate profiles/parts for seams and ornamental rings. Do not make every detail part of the base revolution if that makes later edits fragile.
- Use enough radial segments to avoid visible faceting at the intended camera and lighting. For a stylized low-poly object, retain intentional planar rhythm and inspect the silhouette; do not smooth it away automatically.
- Check actual scale before bevel width or thickness. A numeric bevel has no meaning if the object scale is wrong.
- Place seams where they are hidden or intentional. A seam at a hero highlight can be a visual defect even if the mesh is technically welded.
- Preserve openings and cavities when the reference or camera can reveal them. A capped outer shell is not proof of a bottle interior.

## Common failure and repair

| Observation | Likely cause | Local repair |
|---|---|---|
| Form is too tall/wide or shoulder reads wrong | Profile points or axis placement are wrong | Restore profile checkpoint; adjust profile landmarks and rerun Spin |
| Visible vertical line or shading break | Unwelded seam, inconsistent normals, sharp/auto-smooth mismatch | Weld seam, recalculate normals, inspect weighted normals and material split |
| Rim/lip looks paper-thin or missing | No wall-thickness model or cap hidden in the wrong place | Add inner profile/Solidify and inspect opening close-up |
| Handle/hinge looks fused or floats | Non-radial part forced into the revolve | Separate assembly, add support/contact, check side/back views |
| Detail is dense but object still does not resemble reference | Primary profile or proportion error | Remove detail, restore accepted silhouette, repair the profile first |
| Hero render looks good but side/back fails | Camera-only optimization | Render complementary views and make hidden-side decisions explicit |

## Acceptance

The route passes only when the primary silhouette, axis/proportion, seam/normals, openings/thickness, and required attachments are supported by both evaluated scene checks and suitable views. A simple profile with correct hierarchy is better than a dense revolved mesh that hides the wrong shape. If the user asked for a finished asset, do not deliver the profile-only blockout.

Primary references: [Blender Manual — Spin](https://docs.blender.org/manual/en/latest/modeling/meshes/tools/spin.html), [Bevel Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html), [Subdivision Surface](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/subdivision_surface.html), and the [Blender Studio modeling guide](https://studio.blender.org/tools/artist-guide/asset-creation/modeling).
