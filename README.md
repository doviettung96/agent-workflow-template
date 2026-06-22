# Agent Workflow Template

The canonical template for my projects: a self-contained, provider-neutral bundle of
agent skills (usable by both Codex and Claude) plus a runtime-routing helper. Downstream
projects adopt these skills so every repo shares the same engineering discipline —
brainstorm → plan → build → debug → verify.

## Skills (`skills/`)

Planning & engineering:

- `brainstorming` — turn an idea into a settled design through collaborative dialogue
- `writing-plans` — turn a settled spec into an executable implementation plan
- `systematic-debugging` — root-cause-first debugging discipline
- `verification-before-completion` — prove a change works before claiming done
- `build-and-test` — run a plan's `## Verification` commands without guessing the stack

Runtime (incl. game reverse-engineering):

- `target-runtime-exec` — route build/test/run/deploy commands through a selected local
  or SSH runtime target via `scripts/shared/target_runtime.py` (config at
  `.workflow/runtime-target.json`)

## Helper scripts (`scripts/shared/`)

- `target_runtime.py` — local/SSH runtime routing for project commands

## Using a skill

Each skill is a `SKILL.md` (plus supporting files). Point your agent harness at the
`skills/` directory, or copy individual skill folders into a downstream repo's
`.codex/skills/` or `.claude/skills/`.

## Attribution

The bundled engineering skills are curated copies derived from `obra/superpowers`, with
planner-flow ideas inspired by GSD. See [ATTRIBUTION.md](ATTRIBUTION.md).
