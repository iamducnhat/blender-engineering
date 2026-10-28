# Organic and character recipe

Use this recipe for characters, creatures, faces, plants with irregular growth, soft props, and likeness-heavy or sculptural forms. The route is shape-first. Retopology, UVs, rigging, and material detail are conditional on the requested use.

## Build order

1. Establish references, style grammar, and shape hierarchy: primary mass, secondary anatomy/design landmarks, tertiary surface detail. Record what is observed versus inferred, especially for unseen sides.
2. Choose a base: sculpt/primitive blockout, authored/imported asset, generated mesh, or hybrid. Preserve the source before remesh, cleanup, retopo, or destructive modifiers.
3. Check silhouette, proportion, landmarks, negative space, and pose from front/side/back/three-quarter views. Run a turnaround or neutral clay pass before investing in skin pores, hair, clothing micro-detail, or texture.
4. Use remesh/voxel cleanup for sculpt preparation or a stable surface, not as proof of deformation-ready topology. If deformation/rigging, UVs, or SubD are required, retopologize deliberately around joints, face, hands, feet, and silhouette landmarks.
5. Test expression/pose/deformation before final topology when the target needs them. Repair the shape or edge flow that fails; do not hide joint collapse with a beauty camera.
6. Build UVs after major shape/topology changes settle. Allocate texel density to camera/use; preserve a high-detail source for baking/reprojection when appropriate.
7. Add materials, hair/fur, clothing, and tertiary detail according to the style and camera. Keep the face/gesture/primary contour readable at the intended distance.
8. If rigging or animation-ready geometry is required, establish a rest pose, bone naming/map, root/pivot policy, and target profile. Read `animation-contract.md` before exporting or retargeting.

## Retopology decisions

- Use clean edge flow where deformation, selection, facial expressions, or SubD needs it. A static sculpt or render-only asset may retain deliberate triangles/ngons or dense regions.
- Do not call an automatic quad remesh animation-ready. Inspect poles, stretch, joint loops, facial rings, volume preservation, and pose behavior.
- Preserve the sculpt/generated mesh and record the relationship between high-detail and retopologized versions. A lost source cannot be reprojection-fixed later.
- Model to the required silhouette and deformation; do not use anatomy rules as an excuse to erase a requested stylization.

## Defect table

| Observation | Likely cause | Repair scope |
|---|---|---|
| Character reads as generic or wrong identity | Primary silhouette/landmarks are wrong | Return to primary/secondary shape checkpoint; do not add pores |
| Face looks good from one angle only | Camera overfit or missing volume | Inspect side/back/three-quarter; repair planes and volumes |
| Joint collapses or twists | Edge flow/rest pose/weights do not support deformation | Repair local topology, rest pose, weights, or rig profile; rerun pose tests |
| Generated mesh has floating/merged parts | Backend representation or cleanup failure | Preserve source; separate/repair part locally or change route |
| Detail overwhelms gesture | Tertiary density exceeds shape hierarchy | Reduce/remove detail and restore readability at target camera |
| UV/texture looks stretched | Seams/unwrap done before shape settled or poor island layout | Re-unwrap affected regions, test-grid render, preserve material assignment |

## Acceptance

For a render-only organic asset, pass requires readable shape hierarchy, silhouette, proportions, style, materials, and requested views. For a deforming asset, add rest-pose, rig, weight, expression/pose, and target-runtime checks. For an imported/generated asset, add provenance and representation limits. Do not infer rig readiness, animation quality, or likeness fidelity from a beauty render.

Primary references: [Blender Studio modeling guide](https://studio.blender.org/tools/artist-guide/asset-creation/modeling), [Live Retopology at BCON22](https://studio.blender.org/blog/live-retopology-at-bcon22/), [Stylized Character Workflow](https://studio.blender.org/training/stylized-character-workflow/), and [Blender Manual retopology/remeshing](https://docs.blender.org/manual/en/latest/modeling/meshes/retopology.html).
