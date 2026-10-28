# Frame-by-frame sprite route

This reference defines the portable raster route used by
[`scripts/sprite_pipeline.py`](../scripts/sprite_pipeline.py). It is designed
for a novice who supplies one request and judges the final appearance. The
pipeline owns timing, packing, source preservation, and validation; it should
not stop to ask the user to repair an atlas or identify a missing pivot.

## Source contract

The canonical source is an explicit timeline JSON plus its PNG frame files.
An optional `.aseprite` file remains a higher-fidelity editable source when it
exists. A packed PNG, GIF, or MP4 is a derived artifact and must never be
reported as the editable master.

Minimal timeline example:

```json
{
  "schema": "blender-engineering.sprite-timeline.v1",
  "canvas": {"width": 32, "height": 32},
  "default_pivot": {"x": 16, "y": 28},
  "frames": [
    {"id": "idle_s_000", "file": "frames/idle_s_000.png", "duration_ms": 120,
     "action": "idle", "direction": "south", "index": 0},
    {"id": "idle_s_001", "file": "frames/idle_s_001.png", "duration_ms": 180,
     "action": "idle", "direction": "south", "index": 1}
  ],
  "actions": {
    "idle_south": {
      "frames": ["idle_s_000", "idle_s_001"],
      "loop": "loop"
    }
  }
}
```

Coordinates use a top-left origin. `pivot` and `source_offset` are logical
canvas pixels, not atlas pixels. A frame PNG may be a full-canvas image or a
smaller image placed at `source_offset`; the latter must still fit within the
declared canvas. A normalized pivot can be written as
`{"x": 0.5, "y": 0.875, "normalized": true}`. When a pivot is omitted the
helper uses the canvas center and emits a warning; this is a reversible default,
not a claim that the center is artistically correct.

`duration_ms` is authoritative. An action is an ordered list of frame IDs and
has one of these modes:

- `loop`: repeat the listed sequence;
- `once`: play once;
- `pingpong`: play the list forward and then its interior in reverse;
- `reverse`: play the listed sequence in reverse order.

If a loop intentionally repeats identical pixels at its boundary, set
`allow_boundary_duplicate: true` on that action. Otherwise validation fails so
an accidental “include last frame” export cannot silently create a pause. A
hold should normally be represented by a longer `duration_ms`, not by copying a
frame ID and hoping the target importer infers the intent.

## Packing and metadata

Run the helper from its own directory or use its absolute path:

```sh
python3 scripts/sprite_pipeline.py pack timeline.json \
  --atlas build/hero_atlas.png \
  --metadata build/hero_atlas.json \
  --padding 2 --extrude 1 --trim \
  --preview build/hero_fullspeed.gif \
  --slow-preview build/hero_slow.gif --slow-factor 2
```

Pillow is optional for this programmatic PNG/atlas/GIF route. The skill has no
mandatory package or repository-root dependency. If the active interpreter
does not already have Pillow, install it in an isolated task environment and
run the helper with that interpreter:

```sh
SKILL_ROOT=/path/to/installed/blender-engineering-animation
python3 -m venv .venv
.venv/bin/python -m pip install Pillow
.venv/bin/python "$SKILL_ROOT/scripts/sprite_pipeline.py" pack timeline.json \
  --atlas build/hero_atlas.png --metadata build/hero_atlas.json
```

The same `.venv/bin/python` should run `validate` and `preview`. `--help` and
`probe` remain useful without Pillow, while `pack`, `validate`, and `preview`
report the missing optional dependency clearly.

The packer preserves the input order and uses a deterministic shelf layout.
`padding` separates packed rectangles. `extrude` duplicates edge pixels around
each content rectangle to reduce filtering bleed. The metadata stores both:

- `frame`: the content rectangle, excluding extrusion;
- `packed_frame`: the rectangle including extrusion;
- `source_size`: the original logical canvas;
- `sprite_source_size` and `offset`: the content rectangle’s position in the
  original canvas;
- `pivot`: the original logical-canvas pivot plus normalized values;
- action, direction, frame index, duration, and source hash.

`--trim` removes transparent borders only from the atlas content. It preserves
the original canvas offset in `sprite_source_size` and `offset`. A target that
ignores those offsets will visibly jitter, so target import must consume the
metadata or use full-canvas frames. A full-canvas atlas is the safer default
when a runtime’s offset support is unknown.

Positive padding and extrusion reduce atlas bleeding but do not prove the
chosen engine’s sampler settings are correct. Tight packing, rotation, alpha
dilation, premultiplied alpha, texture filtering, and mipmaps are target
concerns. For pixel art, record nearest filtering as a target requirement and
test the actual renderer.

## Validation gates

`validate timeline.json` checks that:

- the schema and canvas are valid;
- frame IDs are unique and every source file exists and decodes;
- image dimensions and offsets fit the logical canvas;
- alpha channels have dimensions matching their images;
- durations are positive finite integers;
- action references exist, action frame counts match requested expectations,
  and loop modes are known;
- transparent-only frames are rejected;
- unmarked identical loop-boundary frames fail.

`validate build/hero_atlas.json` additionally checks atlas dimensions, RGBA
decoding, frame and packed-frame bounds, source rectangles, expected padding /
extrusion geometry, non-overlap, action references, and expected counts. It
does not check native playback. Its report keeps `runtime_playback` as
`NOT_TESTED`.

Useful checks:

```sh
python3 scripts/sprite_pipeline.py validate build/hero_atlas.json \
  --expected-frames 2 --expected-action idle_south=2
python3 scripts/sprite_pipeline.py probe
```

The GIF preview preserves declared durations at full speed and multiplies them
for the optional slow preview. The sidecar says explicitly that GIF is a
palette-limited preview and that partial alpha may be lost. A preview is useful
for visual timing and silhouette review; it is not evidence that a Godot,
Unity, browser, Spine, or other runtime imports the atlas correctly.

## Native editor route and fallback honesty

[Aseprite’s official CLI documentation](https://www.aseprite.org/docs/cli/)
supports batch export, frame tags, split tags/layers/slices, JSON metadata,
trim, padding, extrusion, and Lua scripting. Its animation and tag
documentation covers frame durations and forward/reverse/ping-pong ranges;
[slices](https://aseprite.com/docs/slices/) can carry pivots. Keep the
`.aseprite` file and export JSON when Aseprite is available. The helper’s
`probe` command reports whether an Aseprite executable is discoverable, and
`--aseprite-source` records an explicitly supplied source without pretending
that the helper converted or validated it.

The programmatic PNG sequence is a transparent fallback. LibreSprite is a
useful open-source editor, but its [official README](https://github.com/LibreSprite/LibreSprite/blob/master/README.md)
does not establish Aseprite CLI or JSON feature parity; `probe` therefore
reports `NOT_ASSUMED` rather than treating a LibreSprite executable as an
Aseprite backend.

License constraints are part of the route receipt. Aseprite’s [EULA](https://github.com/aseprite/aseprite/blob/main/EULA.txt)
governs official compiled binaries, so the skill should detect an existing
installation rather than silently bundling one. LibreSprite’s repository is
GPLv2; [Krita documents GPLv3](https://krita.org/en/about/license/); and
[OpenToonz publishes a modified BSD-style license](https://github.com/opentoonz/opentoonz/blob/master/LICENSE.txt)
with separate third-party directories. These facts describe the tools and do
not grant permission to redistribute third-party binaries or sample art.

The official [Aseprite save documentation](https://www.aseprite.org/docs/save)
also makes the source/derivative boundary explicit: the native file retains
editing structure while PNG/GIF exports do not. The helper’s source manifest
should preserve that distinction in every delivery.

## Painterly and cel-animation fallbacks

For hand-drawn or painterly frame animation, [Krita’s render documentation](https://docs.krita.org/en/reference_manual/render_animation.html)
uses a PNG image sequence as the intermediate before a video encoder produces
GIF/MP4/MKV. Keep the `.kra` file and the image sequence; treat the encoded
movie as a preview or delivery artifact. Krita’s [native file-format notes](https://docs.krita.org/en/general_concepts/file_formats/file_kra.html)
explain that `.kra` retains Krita editing features that other applications do
not necessarily understand.

[OpenToonz’s animation-level documentation](https://github.com/opentoonz/opentoonz_docs/blob/master/source/editing_animation_levels.rst)
and [rendering documentation](https://opentoonz.readthedocs.io/en/latest/rendering_the_animation.html)
describe numbered image levels, vector levels, scene ranges, and image-sequence
outputs. MP4/WebM output depends on [FFmpeg integration](https://opentoonz.readthedocs.io/en/latest/using_ffmpeg_with_opentoonz.html);
other formats remain sequences. Preserve the `.tnz` scene and levels and do
not claim that exporting one vector level includes the full scene camera
animation. These routes are complementary editor backends, not proof that a
single generic sprite atlas is accepted by every target.

