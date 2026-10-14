---
name: setup-sandbox
description: Set up (or re-create on a new Mac) a sandboxed HEP development container for AI coding agents - VS Code Dev Container with Python/ROOT/C++/LaTeX, only ~/hep shared with the container, no Docker socket, no sudo, SSH via the forwarded agent. Guides preflight checks, decisions, config generation, build, verification, and optional folder migration. Use when the user asks to set up, rebuild, or reproduce the HEP agent sandbox / hep-devcontainer, or to onboard a colleague's Mac.
license: MIT
compatibility: macOS (Apple Silicon or Intel) with Docker Desktop (or OrbStack) and VS Code + Dev Containers. Uses bash, python3 (3.9+) and docker on the Mac. Does not install software itself.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/preflight.sh *) Bash(${CLAUDE_SKILL_DIR}/scripts/secret_scan.sh *)
metadata:
  version: "0.1.1"
  source: "https://github.com/S81D/hep-agent-sandbox"
---

# Set up the HEP agent sandbox

You are helping the user build a Linux dev container in which AI coding agents (Claude Code,
optionally Codex) do their work, so that agents see only the user's research folder (default
`~/hep`), not the rest of the Mac. The finished setup is what `template/` describes:

- one bind mount: `~/hep` → `/workspace/hep` (plus read-only overlays for
  `infrastructure/` and any dataset folders the user chooses)
- non-root user `vscode`, no sudo, `--cap-drop=ALL`, `no-new-privileges`, no Docker socket
- conda-forge env with ROOT and the HEP Python stack (pinned), C/C++ toolchain, TeX Live
  subset, poppler, Node.js, Claude Code and Codex CLIs
- the Mac's ssh-agent forwarded by VS Code (keys never enter the container); agent logins
  and compiled builds in named Docker volumes
- an agent policy (`setup/agent-policy.md`) loaded as managed Claude Code instructions

**You run on the Mac, outside the sandbox.** That is unavoidable for setup, so be careful:
every host change is the user's decision.

## Guardrails (always apply)

- Never mount `~`, `~/Desktop`, `~/Documents`, `~/Downloads`, `~/Library` or `~/.ssh` into the
  container. Never mount `/var/run/docker.sock`. Never use `--privileged`. Never add sudo.
- Never read, copy or print private keys. `ssh-add -l` (public fingerprints) is fine.
- Never install software on the Mac yourself. When something is missing, point to
  [prerequisites.md](references/prerequisites.md) and let the user install it.
- Ask before every host change: VS Code settings, `~/.zshrc`, Docker Desktop settings, files
  outside the user's hep folder.
- Never move, rename or delete user files without first showing the exact list of moves,
  **and** confirming a backup exists. See [migration.md](references/migration.md).
- No Fermilab/HPC logins, grid jobs or remote writes on the user's behalf.
- Before claiming something works, run the check. Report failures with their output.

## Phase 1: Preflight (read-only)

Run:

```bash
"${CLAUDE_SKILL_DIR}/scripts/preflight.sh" ~/hep
```

(use the user's folder if it is not `~/hep`). Summarize the result in a short table. For each
MISSING item, point to the matching section of
[prerequisites.md](references/prerequisites.md) and stop until the user has fixed it. WARN items
can continue but must be mentioned (especially: no backup, iCloud Desktop sync, credential
helper settings not set).

## Phase 2: Decisions

Ask the user, one question per decision, with a recommended default. The options and their
trade-offs are in [decisions.md](references/decisions.md):

1. Research folder (`hep_dir`, default `~/hep`). If it does not exist yet, or projects still
   live elsewhere (often `~/Desktop`), plan the migration first (Phase 7) or start with an
   empty folder.
2. Read-only folders (datasets the agent must never modify).
3. Remote access preset: `none`, `fermilab-kerberos-host-only`, or `ssh-key-hpc`.
4. Python pins: the tested defaults, or matched to their existing host conda env.
5. Optional personal section for the agent policy (who they are, author email, preferences).
   Offer to draft it from their `~/.claude/CLAUDE.md` if they have one (read it only with
   permission). See [agent-memory.md](references/agent-memory.md).

Write the answers to `<hep_dir>/infrastructure/answers.json` (format:
[answers.example.json](scripts/answers.example.json)). Keeping it inside the hep folder means a
new Mac restored from backup can re-render the same setup.

## Phase 3: Generate the configuration

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render.py" --answers <hep_dir>/infrastructure/answers.json --dry-run
```

Show the user what will be added (and any diffs against an existing configuration). After they
approve, run it again without `--dry-run`. `render.py` never overwrites a differing file unless
given `--force`; use `--force` only after the user has seen the diff and agreed.

If the user chose "match my host env" for Python, edit the pins in the rendered
`setup/environment.yml` together with them, then check that it solves for Linux before
building (see decisions.md, "Python pins").

## Phase 4: Host settings (ask for each)

1. **VS Code user settings** (`~/Library/Application Support/Code/User/settings.json`), required:
   ```json
   "dev.containers.gitCredentialHelperConfigLocation": "none",
   "dev.containers.dockerCredentialHelper": false
   ```
   Without them, VS Code forwards the Mac's git and Docker credential helpers into the
   container, and an agent could read a GitHub token with `git credential fill`.
   Show the merged file before writing; keep every existing setting.
2. **Docker Desktop memory**: 8 GB or more (Settings → Resources). The user changes this.
3. **SSH key for GitHub** (only if they use SSH remotes): they run
   `ssh-add -t 4h ~/.ssh/<key>` in a Mac terminal when needed.
4. **Optional terminal aliases** (`hep` / `hep-stop`): the snippet is in the rendered
   `QUICKSTART.md`. Add to `~/.zshrc` only if they ask.

## Phase 5: Build and verify

1. Test build, from the rendered folder (no VS Code needed):
   ```bash
   cd <hep_dir>/infrastructure/hep-devcontainer
   docker build --build-arg HOST_HEP="$HOME/<hep folder name>" -t hep-dev:candidate .
   ```
   The first build downloads several GB and takes roughly 5-15 minutes; tell the user before
   starting. If it fails, read the error; common causes are in
   [troubleshooting.md](references/troubleshooting.md).
2. The user opens the container: Cmd+Shift+P → **Dev Containers: Open Folder in Container...**
   → `<hep_dir>/infrastructure/hep-devcontainer`. `verify.sh` runs automatically
   (`postCreateCommand`); ask them for its summary line.
3. Host-side ground truth (read-only):
   ```bash
   docker inspect <container_name> --format '{{.HostConfig.Privileged}} {{.HostConfig.CapDrop}} {{.HostConfig.SecurityOpt}}'
   docker inspect <container_name> --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} rw={{.RW}}{{"\n"}}{{end}}'
   ```
   Expect: `false [ALL] [no-new-privileges:true]`; mounts = the hep folder, the read-only
   overlays, and the named volumes only.
4. Ask the user to have the in-container Claude run
   `bash /workspace/hep/infrastructure/hep-devcontainer/setup/verify.sh --agent-probe` and paste
   the result. The process ancestry must show Linux paths, never `darwin`.
5. Export the lock file for the record:
   ```bash
   docker exec -u vscode <container_name> micromamba env export -p /opt/conda/envs/hep --explicit --md5 \
     > <hep_dir>/infrastructure/hep-devcontainer/setup/conda-linux-$(docker exec <container_name> uname -m | sed 's/x86_64/64/').lock
   ```

## Phase 6 (optional): carry over agent instructions and memories

If the user has used Claude Code on the Mac, follow [agent-memory.md](references/agent-memory.md)
to bring their global instructions into the policy's personal section and project memories into
per-project `agent-notes/` folders.

## Phase 7 (optional): migrate project folders

Only with a confirmed backup. Follow [migration.md](references/migration.md): inventory, propose
a move table, run `secret_scan.sh` on each folder before it moves, move with `/bin/mv -n` one
item at a time, then fix stale absolute paths with diffs the user approves.

## Phase 8: Hand-off

- Point the user to the rendered `QUICKSTART.md` (daily use, volumes, terminal aliases).
- Explain the survey loop: at the end of a session, ask the agent to complete
  `/workspace/hep/infrastructure/hep-devcontainer/AGENT_SURVEY.md`; review the answers in
  `scratch/agent-survey/` before changing the setup.
- Remind them of the residual risks in the repository's `docs/DESIGN.md`: agent-written code run
  on the Mac is unsandboxed; outbound network is open; agents outside the container window are
  unsandboxed.
