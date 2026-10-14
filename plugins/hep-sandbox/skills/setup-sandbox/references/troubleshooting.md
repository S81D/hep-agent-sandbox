# Troubleshooting

Problems met while building and using this setup, with their causes and fixes.

## Building the image

| Symptom | Cause | Fix |
|---|---|---|
| `groupadd: GID '1000' already exists` | `ubuntu:24.04` ships a user `ubuntu` with UID/GID 1000 | The Dockerfile runs `userdel --remove ubuntu` first (already in the template) |
| conda solve on the Mac fails with `nothing provides __glibc` | macOS has no Linux glibc | Add `CONDA_OVERRIDE_GLIBC=2.39` to dry-run solves |
| A package "is not available" for `linux-aarch64` | Not every conda-forge package exists for every platform (e.g. `pymupdf`) | Pick an alternative (system tool via apt, or another package) |

## Opening the container in VS Code

| Symptom | Cause | Fix |
|---|---|---|
| "Dev Containers: Reopen in Container" missing from the palette | The window has no folder open (it only appears for local folders) | Use **Dev Containers: Open Folder in Container...** and pick `<hep>/infrastructure/hep-devcontainer` |
| VS Code asks "Add Dev Container Configuration Files" | The window isn't linked to the config: either a plain Mac window on another folder, or one *attached* to the running container | Press **Escape**. Reopen via *Open Folder in Container* on the config folder; the bottom-left must read "Dev Container: HEP Analysis Environment" |
| Rebuild from a Docker Desktop / "Attach to Running Container" window fails the same way | Attached windows don't know the config | Rebuild only from the Dev Container window |

## SSH and credentials

| Symptom | Cause | Fix |
|---|---|---|
| `Error connecting to agent: Permission denied` with `SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock` | Docker Desktop's forwarded socket is `root:root 0660`; the `vscode` user can't use it | Don't mount it. VS Code forwards the agent itself (the template does this) |
| `ssh-add -l`: "agent has no identities" | No key loaded on the Mac | `ssh-add -t 4h ~/.ssh/<key>` in a Mac terminal |
| No ssh-agent in a `docker exec` shell | Only VS Code forwards the agent | Do git push/pull from the Mac or the VS Code container window |
| `git credential fill` in the container returns a token | VS Code forwards the Mac's credential helper by default | Set `dev.containers.gitCredentialHelperConfigLocation: "none"` (user settings) and `git.terminalAuthentication: false` (in the template) |
| Fermilab SSH fails from the container | FNAL uses Kerberos, which is host-only in this design | Run Fermilab commands from a Mac terminal |

## Agents inside the container

| Symptom | Cause | Fix |
|---|---|---|
| Read tool: `pdftoppm is not installed` | Page-range reads of PDFs over 10 pages need poppler | `poppler-utils` is in the template's Dockerfile |
| Scanned PDF text is garbled | The text layer is bad OCR | Render the pages: `pdftoppm -png -r 100 -f N -l N file.pdf out` |
| `python3 -I -c "import X"` fails although `pip install --user X` worked | `-I` ignores user site-packages | Put the package in `setup/environment.yml` and rebuild |
| `grep` finds nothing in extracted text | Control characters make the text look binary | `grep -a` |
| A compiled build (e.g. Geant4) vanished after a rebuild | It lived in the container's own filesystem | Build in `~/builds` (the `hep-builds` volume) |
| Policy edits don't take effect | Policy is read at session start | Start a new Claude session. `managed-settings.json` changes need a rebuild |
| A project's `@agent-notes/INDEX.md` import doesn't load | An unclosed code fence earlier in `CLAUDE.md` (imports in code blocks are ignored) | Close the fence |

## Docker volumes

- `docker volume prune` and `docker system prune --volumes` remove only *anonymous* volumes.
  The named volumes here (`hep-claude-config`, `hep-codex-home`, `hep-builds`) survive them.
- `docker volume rm <name>`, `docker volume prune --all` (for volumes no container uses), Docker
  Desktop's *Clean / Purge data* or *Reset to factory defaults*, and uninstalling Docker Desktop
  all delete them. A deleted volume is recreated empty at the next container start.

## Verification script (`setup/verify.sh`)

- `root -e '...'` exits with the value of the last expression (a `printf` returning 13 gives exit
  code 13). Plain `root -l -b -q` exits 0.
- Never redirect LaTeX console output to `<jobname>.out`: hyperref uses that file for PDF
  bookmarks and the next pass breaks with `Missing { inserted`.

## The Mac shell

- `mv`/`cp` aliased to `-i` prompt and silently default to "no" in scripts. Use `/bin/mv`, `/bin/cp`.
- zsh does not word-split unquoted variables; loops like `for p in $list` behave differently from bash.
