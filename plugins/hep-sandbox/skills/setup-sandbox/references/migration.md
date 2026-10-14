# Migrating project folders into the research folder

Moving projects (often from `~/Desktop`) into `~/hep` is optional and fully under the user's
control. Never move anything without (1) a confirmed backup and (2) the user's approval of the
exact move list.

## 1. Backup gate

Confirm a backup covers the research folder (Time Machine or equivalent). Check iCloud:

- If `~/Library/Mobile Documents/com~apple~CloudDocs/Desktop` is a symlink, Desktop & Documents
  sync is on. **Moving a folder out of `~/Desktop` removes it from iCloud** (and from the user's
  other devices). Without another backup, the moved files then have none.
- Check for cloud-only ("dataless") files before moving; moving them forces a download:
  `ls -lOR <folder> | grep -c dataless`.

If there is no backup, stop here: build the container with an empty or partial research folder,
and come back to migration later.

## 2. Inventory (read-only)

For each candidate folder: size (`du -sh`), whether it is a git repo (and its remote), when it
was last modified, and whether it is research or personal. Flag duplicates (two clones of the
same remote) and things that do **not** belong in an agent-visible folder:

- personal documents, email archives, interview or HR material
- anything holding credentials (bots, deploy scripts with tokens, shell histories, `.env` files)

## 3. Secret scan (read-only)

Before a folder moves into the workspace:

```bash
"${CLAUDE_SKILL_DIR}/scripts/secret_scan.sh" <folder> [<folder> ...]
```

It prints filenames only. Review every hit with the user. Real secrets stay out (or the secret is
removed first); false positives such as a Keynote file named `*.key` are fine.

## 4. Propose a move table

Show `source → destination` for every item, with size and notes, and a "leave in place" list with
reasons. Keep original folder names unless a name is ambiguous in its new parent, and mark every
rename. Let the user edit the table.

## 5. Move

- Same disk (normal case): each move is an instant rename. Nothing is copied or deleted.
- One item at a time: `/bin/mv -n "<source>" "<destination>"`. Use `/bin/mv` because many shells
  alias `mv` to `mv -i`, which prompts and silently defaults to "no". `-n` refuses to overwrite.
- Check that each destination exists afterwards, and log what moved.

## 6. Fix stale paths (shown as diffs)

Code often hard-codes absolute paths such as `/Users/<you>/Desktop/...`.

```bash
grep -rIlE '/Users/<you>/Desktop' <hep_dir> --include='*.py' --include='*.ipynb' --include='*.C' \
  --include='*.sh' --include='*.json' --include='*.tex' --include='*.md'
```

Rewrite them to `/Users/<you>/hep/...`. That path works on the Mac and, through the container's
path-parity symlink, inside the container too. Change only path strings, never logic, binning or
cuts. Show a per-file diff and apply only what the user approves.

## 7. After the move

- **Claude auto-memory is keyed by folder path.** Memories from sessions in the old location no
  longer load, on the Mac or in the container. Carry them over with
  [agent-memory.md](agent-memory.md).
- Shell aliases (`cd ~/Desktop/...`) and other tools' trusted-project lists may point to old paths.
  These are optional host edits, done only with the user's approval.
