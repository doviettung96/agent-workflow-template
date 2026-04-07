---
name: writing-plans
description: "Use when you have a spec or requirements for a multi-step task, before touching code. This is an executor skill - use only when a bead has been claimed and you are in an executor session, NOT in a planner session."
---

# Writing Plans

**Workflow position:** Executor session, step 2 of 7 (after claiming bead). Next: implement -> `build-and-test` -> `verification-before-completion` or `requesting-code-review` -> `beads-close`. See BEADS_WORKFLOW.md.

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they do not know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

<HARD-GATE>
This is an **executor skill**. It should only be invoked in a session where a bead has been claimed via `bd update <id> --status in_progress`. Do NOT invoke this in a planner session that just ran `brainstorming`, `planner-research`, or `beads-planner`.
</HARD-GATE>

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it was not, suggest breaking this into separate plans - one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** Use Codex subagents when appropriate to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Verification Section (REQUIRED)

Every plan MUST end with a `## Verification` section that defines how to test the changes against the live system. This section is what `build-and-test` will execute after implementation.

Include:
- **What to build** - which components need rebuilding
- **How to deploy** - exact deploy commands
- **What to test** - specific API calls, expected responses, or observable behaviors
- **Success criteria** - what output or behavior means "it works"
- **Working directory and prerequisites** - when commands must run from a specific directory, need env vars, require a device, container, browser, fixture data, or seeded state

The verification section must be executable without guesswork. Assume the repo is still using the generic stage-1 `build-and-test` skill unless a repo-specific specialization already exists.

That means:
- write exact shell commands, not summaries
- include URLs, ports, endpoints, paths, and process names when relevant
- name the expected output, status code, DOM text, screenshot cue, or log line
- say when manual browser inspection is required and what to look for
- state whether a missing optional dependency such as a live device should fail the bead or downgrade the check to a skipped optional smoke test

Example:
````markdown
## Verification

**Build:** `cd native-lib && bash build.sh x64`
**Deploy:** `python inject.py --device emulator-5564 --launch`
**Smoke test:** `curl http://localhost:32164/ping` -> `{"status": "ok"}`

**Functional tests:**
1. Start campaign: `curl -X POST http://localhost:8787/campaign/start -d 'stage=1'` -> 200
2. Check state: `curl http://localhost:8787/status` -> expected state payload
3. Observe: bot performs the expected in-game behavior

**Success criteria:** All functional tests pass, no crashes in `adb logcat -s tgunmod:V`
````

Without this section, `build-and-test` will not know what to verify. Make it specific to the bead.

If you notice the same verification sequence repeating across multiple beads, that is a signal to specialize the repo-local `build-and-test` skill as stage 2 work.

## Remember

- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Plan Review Loop

After completing each chunk of the plan:

1. Dispatch a plan-document-reviewer subagent (see `plan-document-reviewer-prompt.md`) with precisely crafted review context - never your session history.
   - Provide: chunk content, path to spec document
2. If issues are found:
   - Fix the issues in the chunk
   - Re-dispatch reviewer for that chunk
   - Repeat until approved
3. If approved: proceed to next chunk (or execution handoff if last chunk)

**Chunk boundaries:** Use `## Chunk N: <name>` headings to delimit chunks. Each chunk should be <=1000 lines and logically self-contained.

## Execution Handoff

After saving the plan:

**"Plan complete and saved to `docs/plans/<filename>.md`. Ready to execute?"**

- If this skill was invoked by `/executor-loop`, `/executor-loop-epic`, or `/executor-once`, proceed to implementation automatically â€” do not wait for confirmation.
- Otherwise, wait for user confirmation before proceeding.

**When proceeding:** Use Codex subagents when they help, with code review (`requesting-code-review`) after each major task.

**After implementation is complete:** Invoke `build-and-test` (read `.codex/skills/build-and-test/SKILL.md` and follow it). The skill executes the verification contract from the plan and may be generic or repo-specific depending on the repo's maturity. If `build-and-test` fails, fix the implementation or tighten the plan and re-run it before moving to verification. Do NOT skip this step.
