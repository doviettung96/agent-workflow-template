# Agent Instructions — Global

Single source of truth for the **general** guidelines that apply to *every* one of my
projects. This file lives in the `agent-workflow-template` repo. Edit it only here.

**Distribution** (run `scripts/bootstrap-agent-config.ps1 -Global`, elevated) — each
agent's global instruction file links straight to this one:
- `~/.claude/CLAUDE.md` → this file *(Claude Code)*
- `~/.codex/AGENTS.md` → this file *(Codex)*
- add more agents the same way, e.g. `~/.gemini/GEMINI.md` → this file

**Scope:** this file is GENERAL only. A project's own `AGENTS.md` holds project-specific
information and is owned by that project — the template never creates or edits it. Agents
read both: these general guidelines *and* the project's own `AGENTS.md`.

---

## 1. Engineering principles

When making technical decisions, give **little weight to development/implementation
cost**. Optimize instead for **quality, simplicity, robustness, scalability, and
long-term maintainability**.

A solution that is cheaper to build now but worse to live with is the wrong solution.
Prefer the design you would still be happy to own in two years.

## 2. Bug fixing — reproduce end-to-end first

Always start a bug fix by **reproducing the bug end-to-end**, as closely as possible to
how a real end user hits it: same entry point, same data flow, same environment.
Reproducing it for real is how you find the *actual* root cause, so that your fix
actually solves the problem.

- **Do not blindly trust unit tests.** A passing or failing unit test can hide or
  misrepresent the real problem.
- Only once you can reproduce it end-to-end, narrow down to the smallest failing layer.
- Confirm the fix by **re-running the same end-to-end reproduction**, not just a unit
  test.

## 3. Verification — prove behavior, not just syntax

Verification must exercise the behavior that changed. For any feature or fix, run at
least one meaningful test or live check that would fail if the implementation were
wrong. A syntax-only check such as `py_compile`, `compileall`, import smoke tests, or
typechecking is useful as a supporting guard, but it is **not sufficient verification**
for a behavior change.

For reverse-engineering and automation projects, prefer evidence from the real runtime:
build the latest code, run the current artifact, and validate the behavior through the
same UI, API, device, emulator, game client, logs, or protocol path that the user would
hit. If the changed function is too trivial or too tightly coupled to test in isolation,
move up a level: add or run an integration test, build the project, and perform a live
test against the latest build. When live verification is blocked, say exactly what was
blocked and what lower-confidence checks were run instead.

## 4. UI — be picky, obsess over pixel perfection

When testing a product end-to-end, scrutinize every UI you see and be **obsessed with
pixel perfection**. If something clearly looks off — misalignment, spacing, color,
jitter, wrong state — get it fixed, **even if it is unrelated** to the task you came in
for. Leave every screen you touch better than you found it.

## 5. Engineering excellence — no broken windows

Hold the codebase to that same standard. If you see a **lint error, a failing test, or
a flaky test**, fix it — even when it predates your change and is unrelated to what
you're working on right now. Do not step around broken windows, and do not let them
accumulate.

## 6. Lessons learned — capture so we never trip twice

When you hit a non-obvious error and resolve it, record the lesson so that no agent (or
human) trips on it again.

**Two scopes**
- **Global** → `~/.agents/LESSONS.md`. A fixed, known location for lessons that
  generalize across projects.
- **Project** → `LESSONS.md` at the current repo's root. No fixed path is given here on
  purpose — **find it yourself** in whatever repo you are working in, and create it if it
  does not exist yet. For lessons specific to that repo (committed to its git, so it is
  shared with the team and every agent that opens it).
- Keep *this* file for stable principles only. The growing log lives in the `LESSONS.md`
  files so the always-loaded instructions stay small and high-signal.

**Reading** — Before debugging, skim both scopes for prior gotchas: the project's own
`LESSONS.md` first, then the global one. Grep by error text or tag.

**Writing — ask before saving.** When you finish a task that surfaced a non-obvious bug
or insight worth remembering, **do not save it silently.** Present the proposed lesson to
me in the entry format below and ask whether to save it to **project scope, global scope,
both, or skip**. Write only where I approve. Suggest the scope by judgment: repo-specific
→ project; generalizes across projects → global; if unsure, suggest project and note it
can be promoted to global later. **In the same wrap-up, if the repo uses submodules, also
raise any warranted submodule sync or upstream update (§7) — ask, don't do it silently.**

**Entry format**
```
### <one-line title>
- Date: YYYY-MM-DD
- Symptom: what was observed (paste the actual error text)
- Root cause: why it really happened
- Rule: what to do — and what never to do again
- Tags: #build #windows #flaky #async ...
```

**Promotion & upkeep**
- If a project lesson turns out to be general, move it up to `~/.agents/LESSONS.md`.
- Periodically dedup, delete stale lessons, and fold any recurring rule into the
  relevant principle above.

## 7. Submodules — keep shared dependencies in sync

Only relevant if the repo actually uses git submodules (many don't). When it does, treat
each as a first-class shared dependency, not a frozen blob.

- **Notice drift.** When your work touches or depends on a submodule — or before you wrap
  up — check its pin against upstream (`git submodule status`, then `git -C <sub> fetch`
  and compare `HEAD` to the upstream branch). A submodule pinned far behind upstream is a
  broken window (§5); flag it even if unrelated to your task.
- **Reflect general work upstream.** If you build something in the superproject that a
  shared submodule should own — so *every* consumer inherits it, not just this repo —
  author the change in the submodule/upstream, never a local fork or copy-paste. Keep the
  general design above the boundary; keep repo-specifics below it.
- **Ask before moving pins or pushing.** A submodule is shared across projects, so bumping
  its pin or pushing upstream affects all of them. Like lessons, never do it silently:
  present it and ask whether to **bump the pin here, push upstream, both, or skip** — then
  act only where approved.

## 8. Finishing a task — build the deliverable, commit, open a PR

At the end of a task that produced committable changes, don't leave the work loose.

- **Build the deliverable if your change alters it.** If the change affects a build artifact
  (binary, bundle, package, `.so`/`.exe`), build it and live-verify (§3) *before* declaring
  done — don't wait to be reminded. The concrete build command is project-specific and lives
  in the project's own `AGENTS.md`, not here.
- **Commit + open a PR.** Commit finished work on a branch (never straight to the default
  branch), push, and open a PR — that's the review point, especially for shared repos and
  submodules (§7). Scope each commit tightly: only the relevant files; keep unrelated WIP and
  generated/reference data (dumps, build outputs) out.
- One exception to "don't wait": a genuinely irreversible or broadly outward-facing push
  (force-push, production deploy, a shared default branch) still deserves a heads-up first.

## 9. Agent-to-agent communication — herdr

`herdr` is a CLI tool available on my machines that lets one agent talk to another —
ask a question, hand off a subtask, or get a second opinion. Just be aware it exists; I
decide when it's used and will invoke it when we need it. You don't need to reach for it
on your own.

- **When I do ask you to use it, discover first.** The exact commands and flags belong
  with the tool, not this file — run `herdr --help` (or the relevant subcommand's
  `--help`) for the current usage rather than assuming a syntax that may have drifted.
- **Never message a chat agent (claude/codex) with `herdr agent send`.** It is raw
  keystroke injection into that agent's terminal and it does **not** submit — the Enter is
  a separate command. So the text fuses with whatever I am half-typing in that pane, and
  any time the follow-up Enter is skipped, errors on a stale pane id, or loses a race, the
  message just sits in the input box. That box is never cleared, so every later message
  piles onto the same stale draft and **none of them are ever sent** — the other agent sees
  nothing and you wait forever on a reply that cannot come. Instead:
  - Deliver with **`herdr pane run <pane_id> "<message>"`** — one atomic write
    (bracketed-paste text *plus* the Enter), so nothing can land between them. Multi-line
    messages are fine; an embedded `\n` sent as keystrokes would only insert a newline,
    since both TUIs submit on `\r`.
  - **Re-resolve the pane id on every send** (`herdr agent list` / `agent get`). Ids churn
    as tabs and splits change, and a stale one either errors or presses Enter in whichever
    agent inherited it.
  - **Don't type over me.** `herdr pane read <pane_id>` first; if the input box already
    holds text, wait for it to clear instead of fusing your message onto mine. (Both TUIs
    render the empty-box placeholder dim, so dim text means the box is actually empty.)
  - **A delivery you can't prove landed didn't land.** Check the exit code, then confirm
    the target actually went `working`.
  - If a repo ships a helper that does all of this (chief-of-staffs has
    `scripts/herdr-send.py`), use it rather than re-deriving the sequence.

---

## Bootstrapping

This template owns one script: `scripts/bootstrap-agent-config.ps1` (Windows) /
`bootstrap-agent-config.sh` (macOS/Linux). It distributes these general guidelines and
wires up lessons — it **never** writes a project's own `AGENTS.md`.

- **Global, once per machine** — `bootstrap-agent-config.ps1 -Global`: creates the global
  symlinks above and inits `~/.agents/LESSONS.md` if missing.
- **Per project** — `bootstrap-agent-config.ps1 -ProjectPath <repo>`: inits
  `<repo>/LESSONS.md` if missing, and — only if the project already has its own
  `AGENTS.md` — symlinks `<repo>/CLAUDE.md` → `<repo>/AGENTS.md`. It does not touch the
  project's `AGENTS.md`.

Symlink creation needs an elevated shell on Windows unless Developer Mode is on.
