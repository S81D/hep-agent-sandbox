# HEP container: quick start

Day-to-day instructions for the HEP dev container. The design and security rationale are in
the `hep-agent-sandbox` repository (`docs/DESIGN.md`).

## First time only

Cmd+Shift+P → **Dev Containers: Open Folder in Container...** → pick
`{{hep_dir_display}}/infrastructure/hep-devcontainer` (the folder that contains `.devcontainer/`).

If VS Code offers to "Add Dev Container Configuration Files" or pick a template, press
**Escape**: the wrong folder was selected.

Then sign in to the Claude (and, if you use it, Codex) extension in that window, once.

## Every session

1. **Docker Desktop running?** Check for the whale in the menu bar.
   (To skip this step: Docker Desktop → Settings → General → *Start Docker Desktop when you sign in*.)
2. **GitHub key, only if you will push or pull over SSH.** In a **Mac** terminal:
   ```bash
   ssh-add -t 4h ~/.ssh/id_ed25519
   ```
   Use your key's filename if it differs. The key unloads after 4 hours; rerun when needed.
   Adding `--apple-use-keychain` saves retyping the passphrase.
3. **Open the container:** VS Code → File → **Open Recent** → the entry marked **[Dev Container]**.
4. **Check the bottom-left corner.** It must say **Dev Container: HEP Analysis Environment**.
   If it doesn't, you are on the Mac and agents are **not** sandboxed.
5. **Work.** Use the Claude panel in that window, or `claude` in its terminal. Files are at
   `/workspace/hep` (the same files as `{{hep_dir_display}}` on the Mac).

## Where things go

| Task | Where |
|---|---|
| Analysis, plots, LaTeX, git | Container window |
| Temporary files (disposable) | `/workspace/hep/scratch/` |
| Durable outputs (plots, tables, study results) | Inside the project, e.g. `<project>/results/` |
| Compiled builds (Geant4, MARLEY, ...) | `~/builds` (persistent volume, see below) |
{{remote_quickstart_row}}
| Running scripts an agent wrote | **Container**, never a Mac terminal |
| Pushing HTTPS remotes | Mac terminal, or switch the remote to SSH |

Read-only inside the container, by design: {{readonly_dirs_inline}}.

## Terminal-only use (optional)

Once the container exists (created by VS Code), you can enter it from any Mac terminal without
VS Code. Add to `~/.zshrc`, then `source ~/.zshrc`:

```zsh
# Start Docker Desktop if needed, start the container, and open a shell inside it.
hep() {
    if ! docker info >/dev/null 2>&1; then
        echo "Starting Docker Desktop..."
        open -a Docker
        local tries=0
        until docker info >/dev/null 2>&1; do
            (( ++tries > 60 )) && { echo "Docker Desktop did not start." >&2; return 1; }
            sleep 2
        done
    fi
    if ! docker start {{container_name}} >/dev/null 2>&1; then
        echo "No '{{container_name}}' container yet: open it once in VS Code (Dev Containers: Rebuild Container)." >&2
        return 1
    fi
    docker exec -it -u vscode -w /workspace/hep {{container_name}} bash
}
# Stop the container. Files, logins and ~/builds are untouched.
alias hep-stop='docker stop {{container_name}}'
```

Terminal shells have **no ssh-agent** (only VS Code forwards it), so push/pull over SSH from the
Mac or the VS Code container window.

## Persistent volumes (logins and builds)

Some container state lives in **named Docker volumes**. These are stored inside Docker Desktop,
not in `{{hep_dir_display}}`, so they are **not** in your Mac backup.

| Volume | Mounted at (container) | Holds |
|---|---|---|
| `hep-claude-config` | `/home/vscode/.claude` | Claude login, settings, session history, auto-memory |
| `hep-codex-home` | `/home/vscode/.codex` | Codex login and settings |
| `hep-builds` | `/home/vscode/builds` (`~/builds`) | Compiled software (Geant4, MARLEY, GENIE, ...) |
| `vscode` | `/vscode` | VS Code's own server and extension cache (managed by VS Code) |

**They survive:** closing the window, restarting Docker Desktop or the Mac, and
**Dev Containers: Rebuild Container**. Nothing in this setup deletes them: no script, alias, or
config here runs a prune or `docker volume rm`, and Docker's automatic garbage collection only
touches the *build cache*.

**What does delete them** (avoid unless you mean it):

- `docker volume rm hep-builds` (or any volume name)
- `docker volume prune --all` / `-a`, but only for volumes not attached to any container
- Docker Desktop → Troubleshoot → **Clean / Purge data**, or **Reset to factory defaults**
- uninstalling Docker Desktop

Plain `docker volume prune` and `docker system prune --volumes` are **safe** for these:
in current Docker they remove only *anonymous* volumes, and all of these are named.

**Inspect them** (Mac terminal):

```bash
docker volume ls --filter name=hep-        # list
docker system df -v | grep -E 'hep-|VOLUME' # sizes
```

**If one is deleted, recreate it** by simply reopening or rebuilding the container: Docker
creates an empty volume with the same name automatically, owned by `vscode` because the image
pre-creates each mount point. Then:

- `hep-claude-config` / `hep-codex-home`: sign in again.
- `hep-builds`: rebuild the software from its project recipe. Keep a build recipe in the
  project for anything you put in `~/builds`.

**Optional backup of the builds** before risky Docker maintenance (Mac terminal; writes a tarball
to your home folder):

```bash
docker run --rm -v hep-builds:/builds:ro -v "$HOME":/backup ubuntu:24.04 \
  tar czf /backup/hep-builds-backup.tgz -C /builds .
```

## Changing the environment

- **Temporary Python package:** `pip install --user <pkg>`. It disappears at the next rebuild.
- **Permanent package:**
  1. On the Mac, edit `{{hep_dir_display}}/infrastructure/hep-devcontainer/setup/environment.yml`.
     The file is read-only from inside the container.
  2. Cmd+Shift+P → **Dev Containers: Rebuild Container**.

  Your files, logins and `~/builds` survive the rebuild.
- **JavaScript:** `node` and `npm` (Node 24 LTS) are in the conda env.
- **Do not bump pinned versions** just because newer ones exist. Exact builds are recorded in
  `setup/conda-<platform>.lock` after the first build.
- **Agent instructions** (rules every Claude session follows): edit `setup/agent-policy.md` on
  the Mac. Applies from the next Claude session, no rebuild. The permission prompts in
  `setup/managed-settings.json` do need a rebuild.
- **Project notes for agents** can live in each project's `agent-notes/` folder, loaded via
  that project's `CLAUDE.md` (`@agent-notes/INDEX.md`).

## Improving the setup: the agent survey

At the end of a working session, ask the agent:

> Please complete the survey in /workspace/hep/infrastructure/hep-devcontainer/AGENT_SURVEY.md

Answers collect in `/workspace/hep/scratch/agent-survey/`. Read a few, then decide which
suggestions are worth changing in the container (and which are one-offs).

## Quick checks (container terminal)

| Question | Command |
|---|---|
| Still sandboxed? | `bash /workspace/hep/infrastructure/hep-devcontainer/setup/verify.sh --agent-probe` |
| GitHub key available? | `ssh-add -l` |
| Full health check (about 2 min, mostly LaTeX tests) | `bash /workspace/hep/infrastructure/hep-devcontainer/setup/verify.sh` |

## If something's wrong

- **"Cannot connect to Docker":** start Docker Desktop.
- **Container seems broken:** Cmd+Shift+P → **Dev Containers: Rebuild Container**. The
  container is disposable; the Mac copy of `{{hep_dir_display}}` is the real one.
- **Signed out unexpectedly:** the volume was probably deleted. Sign in again.
- **`verify.sh` reports a FAIL:** read the line. It names what failed and why.

## Rules of thumb

- Only `{{hep_dir_display}}` is visible to agents. Keep passwords, keys and personal files out of it.
- Anything else on the Mac is **unsandboxed**: the Claude desktop app, other AI apps, and
  VS Code windows not marked [Dev Container].
- Closing the window stops the container. Nothing is lost.
