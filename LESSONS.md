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
