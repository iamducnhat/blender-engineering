# Blender Engineering

Blender Engineering is a two-skill public package for turning a novice-language brief into a finished, inspectable 3D or motion result. The user supplies the intent and judges the final look. The agent chooses the representation, builds the asset, inspects it, repairs diagnosed defects, and reports what was actually checked.

The package is designed for a hybrid workflow. A deterministic Blender route is used when the form is controlled by profiles, dimensions, parts, constraints, or repeated structure. Retrieved or generated geometry may be used when it supplies shape information that procedural construction cannot express well. In that case the workflow keeps the source, records provenance, and treats cleanup, inspection, and delivery as part of the work. A provider prompt or a single attractive image is not a finished model.

This repository contains skill instructions and supporting references. It does not certify that every Blender version, connector, generator, export target, or animation runtime is available on every machine. A successful package install is not a claim of polished output, universal runtime support, or quality certification. When a required capability cannot be verified, the run must report `INCOMPLETE`, `BLOCKED`, or `NOT_TESTED` with the evidence.

## Skills

The public package contains exactly these two skills:

| Skill | Use it for |
| --- | --- |
| `blender-engineering-modeling` | Finished 3D assets, scenes, assemblies, materials, requested exports, and model QA from an ordinary-language brief. |
| `blender-engineering-animation` | Motion planning, animation authoring, timing, target-profile checks, and delivery of motion outputs. |

The modeling skill can route a request through revolve/profile modeling, hard-surface parts, organic or generated bases, scenes and assemblies, or a hybrid. It must not stop at a primitive or greybox when the user asks for a finished asset. Animation work keeps motion intent, timing, constraints, markers, loop policy, and target profile separate from the runtime-specific representation.

For motion, a retrieved clip or motion asset may be part of the route when its source, license, transformation, and limitations are recorded. Custom keyframes, procedural motion, cleanup, retiming, and target-specific adaptation remain part of the agent's responsibility; retrieving a clip alone is not a delivered animation.

## Install from GitHub

The supported public distribution is the GitHub repository through the open `skills` CLI. It does not require a custom npm package.

List the available skills without installing them:

```bash
npx skills add iamducnhat/blender-engineering --list
```

Install every public skill in the repository for the current project:

```bash
npx skills add iamducnhat/blender-engineering --skill '*' -y
```

Install both skills for Codex in the current project:

```bash
npx skills add iamducnhat/blender-engineering \
  --skill blender-engineering-modeling \
  --skill blender-engineering-animation \
  --agent codex \
  -y
```

Install one skill for one host:

```bash
npx skills add iamducnhat/blender-engineering \
  --skill blender-engineering-modeling \
  --agent codex \
  -y

npx skills add iamducnhat/blender-engineering \
  --skill blender-engineering-animation \
  --agent claude-code \
  -y
```

Install both skills globally for Codex:

```bash
npx skills add iamducnhat/blender-engineering \
  --skill blender-engineering-modeling \
  --skill blender-engineering-animation \
  --global \
  --agent codex \
  -y
```

Install both skills globally for Claude Code when that host is the target:

```bash
npx skills add iamducnhat/blender-engineering \
  --skill blender-engineering-modeling \
  --skill blender-engineering-animation \
  --global \
  --agent claude-code \
  -y
```

Use a single skill directly from its GitHub directory:

```bash
npx skills add \
  https://github.com/iamducnhat/blender-engineering/tree/main/skills/blender-engineering-modeling \
  --agent codex \
  -y
```

`npx skills` currently supports `codex` and `claude-code` as separate agent targets. Project installs use the CLI's canonical `.agents/skills` path and may create agent-specific links; `--copy` requests independent copies when links are unsuitable:

```bash
npx skills add iamducnhat/blender-engineering \
  --skill blender-engineering-modeling \
  --agent codex \
  --copy \
  -y
```

The CLI itself requires Node.js 22.20 or newer. The repository does not promise that the host agent has Blender, a bridge, a generator, a renderer, or a target runtime. Those capabilities are probed during a task.

## Read before using or changing a skill

At the beginning of every task and every resumed task, the agent must reread the applicable `SKILL.md`, its research playbook ([modeling](skills/blender-engineering-modeling/references/research-playbook.md) or [animation](skills/blender-engineering-animation/references/research-playbook.md)), the relevant recipe/platform profile, and the current run evidence. The agent must not continue from a remembered summary when a saved artifact, receipt, checkpoint, or failure is available.

The user should be able to give one ordinary-language request. The agent owns technical choices and internal stages; it should not ask the user to choose modifiers, topology, providers, polygon counts, cameras, repair commands, or blockout approvals. The user remains the final aesthetic judge. The agent must still make technical state and uncertainty visible.

Every task should preserve the original request, explicit criteria, observed reference facts, use profile, assumptions, route, provenance, checks, and deliverables. Technical checks use `PASS`, `FAIL`, `UNCERTAIN`, `NOT_APPLICABLE`, or `NOT_TESTED`. A valid `.blend`, export, script exit code, or beauty render does not by itself prove correct geometry, hidden connections, rigging, runtime playback, print fit, or visual quality.

## Practical prerequisites

- Node.js 22.20 or newer for the `npx skills` installer.
- Python 3.10 or newer for repository validation and packaging tools outside Blender.
- A Blender application for actual 3D authoring, inspection, rendering, or `.blend` delivery. The supported version and executable are recorded by each run; this package does not claim every Blender release works.
- Pillow only when a workflow explicitly uses the sprite or image-processing pipeline.
- `ffmpeg` is optional for preview assembly or media inspection; it is not required for ordinary skill installation.

The Blender app, Python process, and target runtime are separate capabilities. A machine that can install the skill may still be unable to complete a particular modeling, animation, export, or playback request.

## Repository layout

Each skill is self-contained so it can be installed alone:

```text
skills/<skill-name>/
├── SKILL.md
├── agents/                 # host metadata when needed
├── references/             # recipes and operating guidance
├── scripts/                # narrow helpers when shipped and tested
└── assets/                 # public, licensed assets only
```

Do not make a skill depend on `../shared`, a repository-root directory, a home-directory cache, or a machine-specific path. The installer copies or links the selected skill directory; sibling files outside that directory are not a portable dependency. Keep required references, scripts, and public assets inside the skill that uses them. Host metadata must remain thin and must not duplicate the skill instructions.

The public release deliberately excludes Facebook captures, investigation corpora, raw browser snapshots, private assets, model weights, caches, secrets, and generated delivery archives. The normalized archive keeps the public `docs/`, `tests/`, `tools/`, `.github/workflows/validate.yml`, `.gitignore`, and `requirements-dev.txt` metadata alongside the two skill folders. The release helper writes an integrity receipt with archive and member hashes; that receipt records packaging coverage only and does not certify Blender output quality.

## Local validation and packaging

From the repository root, run the standard-library packaging check:

```bash
python3 tools/package_release.py --output dist/blender-engineering-v0.1.0.zip
```

The helper maps the package source to a clean archive root containing `skills/`, README and license files, contributor instructions, public validation/tests/tools, and allowed metadata. It reads the archive back, checks every member, and writes a sibling `.receipt.json` file.

Run the isolated installer test when Node.js and network access are available:

```bash
python3 tools/test_install.py
```

The installer test pins and verifies the `skills` CLI version, disables telemetry, uses a temporary HOME/npm cache/project, tests each skill separately for Codex and Claude Code, exercises copy and default link behavior, and compares installed reference/script hashes with the source package. It never installs into the user's normal skill directories.

The public GitHub checkout and release archive use `skills/`, `tests/` and
`tools/`. Validate them with:

```bash
for skill in skills/*; do
  python3 tools/validate_package.py "$skill"
done
python3 -m unittest discover -s tests -p 'test_*.py'
```

The optional sprite tests additionally need Pillow:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover \
  -s skills/blender-engineering-animation/tests \
  -p 'test_*.py'
```

An investigation/authoring workspace may keep the skill folders, tests and
validator under `plugin/`; prefix those paths with `plugin/` only in that layout.
The release helper handles both layouts without requiring the investigation.

The repository tests include real headless Blender integration fixtures when a Blender executable is available. They explicitly skip when it is absent. See [validation and coverage](docs/VALIDATION.md) for actual local runs, forward cases and limits. A packaging pass must not be reported as a modeling or animation quality test.

## Contributing

Before changing a skill, read [`AGENTS.md`](AGENTS.md), this README, the relevant `SKILL.md`, its [modeling](skills/blender-engineering-modeling/references/research-playbook.md) or [animation playbook](skills/blender-engineering-animation/references/research-playbook.md), the applicable recipe, and the current evidence. Keep observed facts, self-reported claims, inferences, proposed behavior, and tested outcomes separate.

Preserve user criteria and accepted checkpoints during repair. Add provenance for retrieved or generated geometry. Use the least destructive route that can meet the requested use, and keep a fallback when the primary route cannot. Do not add a greybox-only ceiling to a finished-asset request, and do not label an untested route as supported.

The project uses the MIT license. See [`LICENSE`](https://github.com/iamducnhat/blender-engineering/blob/main/LICENSE).
