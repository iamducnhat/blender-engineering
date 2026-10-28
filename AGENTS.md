# Blender Engineering contributor instructions

Before implementation, read the project README, the relevant skill entrypoint,
and its `references/research-playbook.md`. Read the relevant modeling recipe,
animation craft guide, platform profile, and source notes before choosing tools.
When resuming, reread the applicable references and the current run evidence;
do not implement from a remembered summary alone.

Apply research as operational decisions: choose representations deliberately,
inspect actual evaluated artifacts, use visual and temporal feedback, preserve
accepted checkpoints, and verify saved outputs. A citation list is not a
substitute for these behaviors. Keep observed facts, self-reports, design
inferences, and tested outcomes separate.

The target user supplies intent and judges aesthetics. The agent owns technical
decisions, authoring, inspection, repair, optimization, and delivery. Do not add
mandatory blockout approvals or ask the user to debug tools. A blockout is an
internal stage when the request is for a finished asset.

All shipped prose, CLI messages, examples, and metadata are English. Each skill
must work when installed alone: no sibling-skill, repository-root, home-directory,
or machine-specific runtime dependencies. Preserve other contributors' edits;
ownership is coordinated by the implementing agent.

Only publish original code/prose and explicitly permitted examples. Research
captures, account/session data, private assets, caches, and model weights are
not release content. Record real validation coverage; do not label an untested
platform as working or equate a valid export with native playback.
