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

## 3. UI — be picky, obsess over pixel perfection

When testing a product end-to-end, scrutinize every UI you see and be **obsessed with
pixel perfection**. If something clearly looks off — misalignment, spacing, color,
jitter, wrong state — get it fixed, **even if it is unrelated** to the task you came in
for. Leave every screen you touch better than you found it.

## 4. Engineering excellence — no broken windows

Hold the codebase to that same standard. If you see a **lint error, a failing test, or
a flaky test**, fix it — even when it predates your change and is unrelated to what
you're working on right now. Do not step around broken windows, and do not let them
accumulate.

## 5. Lessons learned — capture so we never trip twice

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
can be promoted to global later.

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
