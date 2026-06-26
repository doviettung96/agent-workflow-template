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
