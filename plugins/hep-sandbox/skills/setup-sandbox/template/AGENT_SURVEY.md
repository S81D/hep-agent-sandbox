# Agent survey: HEP dev container

Please answer this at the **end of a working session**, using only what you actually experienced
in this session. The goal is to make your working environment more efficient. Concrete evidence
(exact commands and error messages) is far more useful than general impressions.

## Rules

- Answer only from this session. If something did not come up, write **none**. Do not speculate.
- You may run quick read-only checks (e.g. `command -v <tool>`, `<tool> --version`, `python3 -c "import X"`).
  Do not install, delete, or modify anything to answer.
- Never include secrets, tokens, or file contents. Short paths and error messages are fine.
- Keep it under ~400 words.
- Save your answers to
  `/workspace/hep/scratch/agent-survey/<YYYY-MM-DD>-<agent>-<project>.md`
  (e.g. `2026-10-14-claude-my-analysis.md`), creating the folder if needed, then tell the user
  the file path.

## Questions

Use these headings exactly, so answers from many sessions can be compared.

### 1. Context
Agent and interface (Claude panel / `claude` CLI / Codex), model, the task(s) you worked on, and
your working directory.

### 2. Failures and workarounds
Commands or tools that failed or were unavailable: exact command, error message, and what you did
instead.

### 3. Missing tools or packages
Anything you needed that is not installed (system tool or Python package). How you know, e.g. a
`command not found` or `ImportError`. Note anything you installed temporarily with `pip install --user`.

### 4. Documents and data formats
Any trouble reading PDFs, notebooks, ROOT files, HepMC files, or images? Which file type, and what
went wrong?

### 5. Sandbox boundaries
Did a read-only folder, the missing Fermilab access, or another sandbox limit block legitimate
work? Give the path or operation. (Boundaries working as designed are fine; we want to know their cost.)

### 6. Permission prompts
Which confirmation prompts were genuinely useful, and which were noise? Give the command patterns.

### 7. Instructions and notes
Was anything in your instructions unclear, contradictory, outdated, or missing? This covers
`/etc/claude-code/CLAUDE.md`, project `CLAUDE.md` files, and `agent-notes/`. Include stale paths
you hit.

### 8. Network
External sites or services you needed (domains only), and anything that failed to connect. This
informs a future network allowlist.

### 9. Speed
Operations that were slow (builds, file searches, notebook or script runs), with rough durations.

### 10. Top recommendations
Up to three changes, ranked, each with the expected benefit and any cost or risk.
