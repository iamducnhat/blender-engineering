# Motion craft by intention and medium

Read the research playbook and the relevant platform profile before authoring.
The following are craft decisions to make, not mandatory ingredients in every shot.

## Plan a readable performance

Reduce the request to visible beats and their order: preparation, primary action,
contact/peak, reaction, recovery, and any meaningful hold. A small mechanical loop
may only need an actuator path and phase relation; an acting shot needs emotional
intent and a clear focal point. Infer a coherent interpretation without an intake
interview. Keep user requirements separate from the extra acting choices.

Block key poses and the camera together. Check silhouette, negative space,
eyelines, prop placement and where attention should go. Avoid tangencies that
hide hands, limbs or the action's destination. Test in the intended camera and a
diagnostic angle. A stable diagnostic camera makes sliding and weight transfer
easier to see; motivated handheld motion remains a valid final style.

Timing determines when beats happen; spacing determines how positions change
between them. Uniform interpolation rarely supplies intent by itself. Choose
accelerations, ease, moving holds, anticipation and recovery from weight, mood,
mechanism and responsiveness. An interactive action may need an immediate response
that a cinematic shot does not. Do not add long anticipation that defeats input.

## Contact and weight

Describe contacts as intervals: which foot supports, when the hand grips, when
the object is released, and whether the actor is airborne or sliding on purpose.
Use world-space evaluated positions to find unintended drift, sinking or popping
during an active contact. A swinging foot is expected to move. Source reference
occlusion means hidden-axis motion is inferred; inspect it from another view.

Follow the transfer of mass, support and reaction. A heavy lift changes posture,
timing, grip and recovery. A cartoon can exaggerate those cues; a weightless or
stylized brief can intentionally suspend them. A contact checker must not silently
rewrite the desired style into realistic locomotion.

Use IK/contact constraints when they help, while checking poles, limb stretch,
parent changes, target space and IK/FK continuity. Keep the editable rig and
constraints in source. Bake only the export copy when the target cannot evaluate
the same control graph. Revisit contacts after retargeting and compression.

## Arcs, overlap and secondary movement

Inspect the trajectories of focal hands, feet, head, props and camera. Use
breakdowns to control arcs and depth, rather than adding keys indiscriminately.
Remove reference-capture jitter when it obscures deliberate motion; preserve
small live details when the requested realism benefits from them.

Secondary parts follow their material and attachment. Tails, ears and straps
may lag; rigid gears, receivers and hinges follow mechanism constraints. Random
jiggle is not a substitute for inertia. Add overlap after the primary action
reads, and verify that it does not bury the contact or main silhouette.

## Medium-specific interpretation

- **3D skeletal:** preserve rest pose, bone mapping, deformation, prop attachments
  and root policy. Stress-test the shot's extreme poses before polishing.
- **Rigid/mechanical:** use correct pivots, axes, limits, gear ratios and phase
  relations; organic follow-through may be irrelevant.
- **Frame animation:** select drawings and exposures deliberately. Holds and
  stepped motion can be correct; increasing interpolation is not automatic polish.
- **Pixel art:** preserve silhouette, palette, pixel scale and stable anchors.
  Avoid unintended subpixel blur and frame-bound jitter.
- **Cutout/skeletal 2D:** check mesh deformation, attachment draw order, joints,
  constraints and the atlas in the actual renderer.
- **Vector/interactive:** preserve path correspondence, easing, state/input
  behavior and supported player features. A recorded movie cannot test interaction.
- **Camera/abstract/procedural:** verify visual rhythm and composition without
  imposing humanoid foot-contact or anatomy rules.

## Review in descending impact

First determine whether the action and emotion read at intended speed. Repair
wrong primary poses, missing beats and contact before adding secondary detail.
Then refine timing, spacing and transitions, and finally surface/camera polish.
When sound or effects are part of the request, sketch their timing early and
verify the synchronization after playback-speed or edit changes.

Reference principles, not an unexamined signature performance. Keep a small
reference board tied to actual design questions. Use footage/artist breakdowns
that were really viewed and cite observed intervals. Strong sources include
[Disney's animation process](https://www.disneyanimation.com/process/animation/),
[hand-drawn process](https://disneyanimation.com/process/hand-drawn-animation/),
[Blender Studio animation testing](https://studio.blender.org/tools/pipeline-overview/asset-creation/animation-testing)
and [shot production](https://studio.blender.org/tools/pipeline-overview/shot-production/animation).
