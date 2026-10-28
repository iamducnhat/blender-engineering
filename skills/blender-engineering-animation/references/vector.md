# Vector and runtime animation route

Vector interchange and runtime animation are different deliverables. Preserve
the editor/source project, declare the feature subset, and test the actual
player. A JSON, SVG, or `.riv` file that parses is not proof that a target
renders the same animation.

## Lottie

[The Lottie specification](https://lottie.github.io/lottie-spec/latest/) is a
JSON-based vector animation format whose specification remains a work in
progress and defines an approved subset. [lottie-web’s support notes](https://github.com/airbnb/lottie-web/blob/master/README.md)
and [After Effects guidance](https://github.com/airbnb/lottie/blob/master/after-effects.md)
document practical limits: image sequences, video, and audio are not supported
by lottie-web; common expressions/effects, blending/luma mattes, and layer
styles are not a safe portable subset. External raster assets need their
associated asset files. Frame-rate mismatches can change interpolation; use
holds or match the target frame rate when timing must remain exact.

The source should remain the originating After Effects/vector project. The
Lottie JSON is a runtime artifact. `check-lottie` validates only the basic JSON
envelope (`v`, `fr`, `ip`, `op`, `layers`) and leaves `feature_subset` and
`target_playback` as `NOT_TESTED`. A skill should either select a known subset
or route to a different representation instead of silently dropping an
unsupported effect.

## SVG and Blender Grease Pencil

Blender 5.2 LTS documents Grease Pencil SVG export of the active keyframe,
selected keyframes as SVG animation, or all scene frames as SVG animation in
the official [5.2 LTS manual](https://docs.blender.org/manual/en/5.2/files/import_export/grease_pencil_svg.html).
The [4.5 release notes](https://developer.blender.org/docs/release_notes/4.5/grease_pencil/)
identify multi-frame SVG animation as an earlier feature introduction. This is
evidence for the Blender 5.2 exporter, not universal viewer support.

For the plugin’s local target, record:

```text
Blender 5.2 exporter: documented capability
Actual exporter invocation in this helper: NOT_TESTED
Native SVG viewer/engine playback: NOT_TESTED
```

Grease Pencil is a Blender-native editable route with frame-by-frame strokes,
layers/timelines, deformation, armatures, inherited animation, and onion
skinning. It is not ranked above Aseprite, Spine, Rive, Lottie, or OpenToonz;
choose based on the prompt and target. The exporter works from the largest 3D
Viewport and has object-mode limitations, so a controlled camera and an
explicit scene range belong in the receipt.

SVG’s `<animate>` support varies between viewers. If target playback is
important, deliver the editable `.blend`/Grease Pencil source and a tested
target-specific artifact. Do not substitute a browser preview for engine
validation.

## Runtime and license notes

Rive’s current [product page](https://rive.app/editor) distinguishes interactive
`.riv` runtime export from Cloud Renderer GIF/MP4/PNG/WebM output. The current
[pricing page](https://rive.app/pricing) states that free exports include a
Rive splash screen and paid plans remove it; plan policy can change and is not
a reason to build an unconditional dependency into this skill. Rive runtimes
are documented as MIT open source, while runtime feature support varies.

For every vector output, keep a target card with:

```text
target_name
target_version
source_project
runtime_artifact
feature_subset
asset_paths
font_policy
alpha_policy
frame_rate
playback_test: PASS | FAIL | NOT_TESTED
```

This prevents generic file export from being reported as universal platform
support.

