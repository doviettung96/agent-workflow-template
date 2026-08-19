# Global Lessons Learned

Cross-project gotchas worth never hitting twice. Project-specific lessons belong in that
repo's own `LESSONS.md`; promote a lesson here only once it generalizes.

Read before debugging (grep by error text or tag). Append after resolving any
non-obvious error. One atomic entry each, newest at the top.

Format:
```
### <one-line title>
- Date: YYYY-MM-DD
- Symptom: what was observed (paste the actual error text)
- Root cause: why it really happened
- Rule: what to do — and what never to do again
- Tags: #build #windows #flaky #async ...
```

---

<!-- Add lessons below this line -->

### Dim text in a Claude Code input box is a suggestion, not a draft
- Date: 2026-08-19
- Symptom: An agent read a peer's pane with `herdr pane read --format text`, saw
  `❯ go ahead with electronic_books` in the input box, concluded the owner had a message
  sitting unsubmitted, and refused to send its own — waiting indefinitely on a box that
  was never occupied.
- Root cause: Claude Code renders a *generated suggested-next-message* as dim (SGR 2)
  ghost text in the empty box. It is contextual prose that reads exactly like a human
  draft — it even echoed the recap line above it — and `--format text` discards the dim
  attribute that is the only thing distinguishing them. The older "the placeholder is
  dim" heuristic assumed the generic `Try "..."` placeholder and no longer covers this.
  `herdr agent explain --json`'s `prompt_box_body` region does *not* strip dim either, so
  it cannot make the call.
- Rule: Never judge a peer's input box from plain text, and don't look for a herdr
  command that does it — there isn't one. Read the styling:
  `herdr pane read <pane> --format ansi | grep -a '❯' | tail -1 | cat -v`. Leading
  `^[[2m` → suggestion, box is EMPTY, safe to send; no escape → real draft, wait. Only
  the `❯` between the last two full-width `───` rules is the live box — menu cursors,
  queued messages and transcript echoes all render `❯` too, and a modal removes the box
  and its rules entirely, so check `herdr agent get` before trusting the last `❯`.
- Tags: #herdr #agent-orchestration #ansi #sgr #claude-code #silent-failure

### Repo-root helpers must be copied, not symlinked
- Date: 2026-07-15
- Symptom: `py -3.12 scripts\shared\target_runtime.py status` run from
  `thienanh-novagate` reported
  `Repo root: C:\Users\Tung\Projects\agentic-workflow-template` instead of the target
  repo.
- Root cause: `target_runtime.py` derives `REPO_ROOT` from
  `Path(__file__).resolve().parents[2]`; resolving a symlink points back to the
  template checkout.
- Rule: For helper scripts that compute repo paths from `__file__`, copy the script
  into the downstream repo or change the helper to use a runtime cwd/config root. Never
  symlink those helpers unless symlink resolution has been tested.
- Tags: #bootstrap #windows #symlink #runtime-target #python

### Windows PowerShell 5.1 parses BOM-less UTF-8 .ps1 as Windows-1252
- Date: 2026-06-23
- Symptom: A .ps1 with em-dashes (—) in string literals fails with "Unexpected token",
  "The string is missing the terminator", and "Missing closing '}'" — even though the
  script is syntactically correct.
- Root cause: Windows PowerShell 5.1 reads a .ps1 with no BOM as Windows-1252, so
  multi-byte UTF-8 characters (—, curly quotes) corrupt string-literal parsing.
- Rule: Keep .ps1 scripts ASCII-only, or save them UTF-8 *with* BOM. Never put smart
  punctuation in PowerShell string literals. (.sh is fine — bash reads UTF-8.)
- Tags: #windows #powershell #encoding #scripting

### `herdr agent send` is keystroke injection, not a message
- Date: 2026-08-17
- Symptom: Messages sent between agents with `herdr agent send` sometimes fused with what
  the owner was half-typing in that pane and got submitted as one garbled turn; other
  times they sat in the target's input box unsent forever, with every later message
  piling onto the same stale draft. The receiving agent never saw any of it and the
  sender waited on a reply that could not come.
- Root cause: `agent send` (= `pane send-text`) writes raw bytes into the target's TTY at
  the cursor and does **not** submit — measured on the receiving side, `pane send-text
  "HELLO"` delivers exactly `HELLO` with no trailing byte, and the Enter is a *separate*
  `pane send-keys` write ~4 ms later. So it fuses with any existing draft, and whenever
  the second call is skipped, errors on a stale pane id (`pane send-keys` accepts only
  pane ids, which churn), or loses a race, nothing is submitted. Nothing clears the box,
  so the failure is sticky. `pane run` by contrast delivers
  `\x1b[200~HELLO\x1b[201~\r` — bracketed-paste text plus Enter — in one atomic write.
- Rule: Never `agent send` a chat agent (claude/codex). Deliver with `herdr pane run
  <pane_id> "<message>"`; re-resolve the pane id every send; `pane read` first and wait if
  the box already holds text (the empty-box placeholder is rendered dim, real drafts are
  not); check the exit code and confirm the target went `working` — a delivery you can't
  prove landed didn't land.
- Tags: #herdr #agent-orchestration #tty #bracketed-paste #silent-failure
