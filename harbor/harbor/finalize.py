"""Epic finalize step — Phase 2.5 of harbor.

After `run_epic`'s main loop drains, harbor runs two synthetic beads through
the same tmux-pane infrastructure as a normal bead so the operator gets the
same observability:

  1. `finalize-build-and-test` — runs the project's build + test commands.
     Loads its prompt from `skills/build-and-test/SKILL.md` if present, else
     uses a generic stub instructing the agent to discover and run the
     project's build/test commands.
  2. `finalize-review-epic` — runs the review-epic skill against the closed
     beads. Loads from `skills/review-epic/SKILL.md` (canonical location).

Build-and-test runs first; review-epic only runs if it passes — a broken build
shouldn't get a sign-off review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .orchestrator import RunBeadOptions, RunBeadResult, run_bead
from .state import StateStore

# Generic fallback prompt for build-and-test when the per-repo skill hasn't
# been scaffolded yet. Real downstream repos will override this via
# `skills/build-and-test/SKILL.md` (created by the per-repo specialization
# bead — see `vvn-xy5: Specialize build-and-test for this repo`).
_BUILD_AND_TEST_FALLBACK = """\
Read:
- README.md (build/test command discovery)
- pyproject.toml or package.json or Makefile (build configuration)

Files:
- (no files modified — verification only)

Verify:
- echo build-and-test fallback — agent discovers per-project commands

Body:
Discover this project's build and test commands by reading the configuration
files listed above. Run them in this repository's root directory and report:

  HARBOR-DONE: finalize-build-and-test status=ok classification=none

if all build + test steps pass, or:

  HARBOR-DONE: finalize-build-and-test status=blocked classification=env

with a short paragraph describing what failed and how the operator can
reproduce it locally.
"""

_REVIEW_EPIC_FALLBACK = """\
Read:
- skills/review-epic/SKILL.md (the canonical review-epic prompt)

Files:
- (no files modified — review only)

Verify:
- echo review-epic fallback — skill should be present

Body:
The review-epic skill is missing from this repository. Skip the review and
emit:

  HARBOR-DONE: finalize-review-epic status=blocked classification=contract

so the operator knows to scaffold the skill before re-running.
"""


@dataclass
class FinalizeStep:
    """One step in the finalize pipeline. `bead_id` becomes the synthetic
    bead's identifier (visible in tmux session names + state.json), and the
    description is what `run_bead` would have read from `br show`."""
    bead_id: str
    description: str


@dataclass
class FinalizeResult:
    epic_id: str
    steps_run: list[str] = field(default_factory=list)
    steps_passed: list[str] = field(default_factory=list)
    steps_failed: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return not self.steps_failed and not self.skipped

    def render_summary(self) -> str:
        lines = [
            f"Finalize for epic {self.epic_id}",
            f"  steps_run    : {self.steps_run}",
            f"  steps_passed : {self.steps_passed}",
            f"  steps_failed : {self.steps_failed}",
            f"  skipped      : {self.skipped}",
        ]
        return "\n".join(lines)


def _load_skill_prompt(repo_root: Path, skill_name: str, fallback: str) -> str:
    """Read the prompt body from `skills/<name>/SKILL.md` if present, else
    return the fallback. The Read/Files/Verify sections in the SKILL.md
    determine reservation behavior (none for finalize) and verify gates."""
    candidate = repo_root / "skills" / skill_name / "SKILL.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return fallback


def _build_steps(repo_root: Path, epic_id: str) -> list[FinalizeStep]:
    bat_body = _load_skill_prompt(
        repo_root, "build-and-test", _BUILD_AND_TEST_FALLBACK,
    )
    review_body = _load_skill_prompt(
        repo_root, "review-epic", _REVIEW_EPIC_FALLBACK,
    )
    epic_note = f"\n\n# Context\nThis is the finalize step for epic `{epic_id}`.\n"
    return [
        FinalizeStep(
            bead_id="finalize-build-and-test",
            description=bat_body + epic_note,
        ),
        FinalizeStep(
            bead_id="finalize-review-epic",
            description=review_body + epic_note,
        ),
    ]


def run_finalize(
    *,
    epic_id: str,
    store: StateStore,
    run_id: str,
    repo_root: Path,
    profile: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    bead_timeout_s: float = 60 * 60 * 2,
    keep_pane_after_finish: bool = True,
    log: Callable[..., None] = print,
) -> FinalizeResult:
    """Run the finalize pipeline. Returns a FinalizeResult describing what
    happened. The caller (`epic.run_epic`) decides what to surface to the
    operator and what return code to map."""
    repo_root = Path(repo_root).resolve()
    steps = _build_steps(repo_root, epic_id)
    result = FinalizeResult(epic_id=epic_id)

    for step in steps:
        log(f"[harbor.finalize] running {step.bead_id}")
        result.steps_run.append(step.bead_id)
        bead_opts = RunBeadOptions(
            bead_id=step.bead_id,
            profile=profile,
            model=model,
            effort=effort,
            repo_root=repo_root,
            timeout_s=bead_timeout_s,
            keep_pane_after_finish=keep_pane_after_finish,
        )
        synthetic = {
            "id": step.bead_id,
            "status": "open",
            "title": step.bead_id,
            "description": step.description,
        }
        try:
            run_result: RunBeadResult = run_bead(
                bead_opts, log=log,
                parent_run=(store, run_id),
                synthetic_bead=synthetic,
            )
        except Exception as e:  # noqa: BLE001
            log(f"[harbor.finalize] {step.bead_id} crashed: {e!r}")
            result.steps_failed.append((step.bead_id, "crash"))
            # Skip remaining steps once we've hit a hard failure.
            for later in steps[steps.index(step) + 1:]:
                result.skipped.append(later.bead_id)
            return result

        if run_result.closed:
            result.steps_passed.append(step.bead_id)
            log(f"[harbor.finalize] {step.bead_id} ok")
        else:
            reason = run_result.sentinel_status or "timeout"
            result.steps_failed.append((step.bead_id, reason))
            log(f"[harbor.finalize] {step.bead_id} failed (reason={reason}); "
                f"skipping later steps")
            for later in steps[steps.index(step) + 1:]:
                result.skipped.append(later.bead_id)
            return result

    return result
