# Carrying over agent instructions and memories

Agents inside the container cannot see the Mac's `~/.claude` (by design). If the user has used
Claude Code on the Mac, two things are worth carrying over. Read these files only with the
user's permission, and never copy credentials (`.credentials.json`, `.claude.json`, history).

## 1. Global instructions → the policy's personal section

The Mac's `~/.claude/CLAUDE.md` holds the user's standing preferences. Inside the container the
managed policy (`setup/agent-policy.md`) is loaded instead, and much of a typical global file is
already covered by its generic sections (honesty, scientific safety, targeted edits).

1. Read `~/.claude/CLAUDE.md` with the user.
2. Put what the policy does **not** already say into `answers.json`: `user_blurb` (who they
   are), `author_email`, and `extra_preferences` (one string per rule).
3. Drop Mac-specific rules (local conda env names, shell aliases): they mislead in the container.
4. Re-render; the result appears as an "About the user" section at the end of the policy.

## 2. Project memories → `agent-notes/` in each project

Claude's auto-memory lives at `~/.claude/projects/<path-key>/memory/` on the Mac, keyed by the
folder the session ran in (e.g. `-Users-you-Desktop-software-myproject`). After a folder moves,
or inside the container, those memories no longer load. To keep them with the project:

1. Map each memory folder to the project's new location; ask when unsure.
2. Read every memory file first. Copy nothing containing secrets or personal data.
3. Copy the topic files **verbatim** into `<project>/agent-notes/`.
4. Write `<project>/agent-notes/INDEX.md`: a header saying where and when the notes came from, a
   table mapping old paths in the notes to their new locations, then the original `MEMORY.md`
   index lines (their relative links keep working).
5. Add an import to the project's `CLAUDE.md` (create a minimal one if needed):
   ```markdown
   ## Agent notes

   Notes carried over from earlier agent sessions (index below; topic files in `agent-notes/`).

   @agent-notes/INDEX.md
   ```
   Only the short index loads at startup; agents open topic files when relevant.
6. Check the `CLAUDE.md` for an **unclosed code fence** (an odd number of lines starting with
   three backticks). Claude ignores `@imports` inside code blocks, so an unclosed fence above the
   import silently disables it.
7. Leave the Mac originals in place.

Memories that only apply on the Mac (e.g. "use conda env X", shell alias quirks) are better
dropped than copied.
