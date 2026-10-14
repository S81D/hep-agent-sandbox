# hep-agent-sandbox: instructions for agents

This repository is a public Claude Code plugin that builds a security sandbox. Before changing
anything, read the maintainer guide (imported below) and `docs/DESIGN.md`.

- Never weaken the security invariants listed in MAINTAINING.md without the owner's explicit
  agreement.
- Never commit personal data (emails, usernames, project or dataset names, job IDs, tokens).
- Ask before `git commit` and `git push`. CI must pass on both architectures.

@MAINTAINING.md
