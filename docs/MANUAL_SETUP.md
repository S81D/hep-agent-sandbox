# Manual setup (without Claude)

The same steps the `setup-sandbox` skill guides you through. Paths below assume the default
research folder `~/hep`.

The skill's files live in `plugins/hep-sandbox/skills/setup-sandbox/`:
- `template/`: the container
- `scripts/`: `preflight.sh`, `render.py`, `secret_scan.sh`
- `references/`: the detailed guides

## 1. Prerequisites

Work through [prerequisites.md](../plugins/hep-sandbox/skills/setup-sandbox/references/prerequisites.md):
- Docker Desktop
- VS Code with the Dev Containers extension
- the two VS Code security settings
- a backup

Then check the Mac (read-only):

```bash
git clone https://github.com/S81D/hep-agent-sandbox.git
cd hep-agent-sandbox/plugins/hep-sandbox/skills/setup-sandbox
./scripts/preflight.sh ~/hep
```

Fix every `MISSING` line; read every `WARN` line.

## 2. Create the research folder

```bash
mkdir -p ~/hep/infrastructure ~/hep/scratch
```

Move projects in now or later; see [migration.md](../plugins/hep-sandbox/skills/setup-sandbox/references/migration.md).
Never put keys, passwords or tokens in `~/hep`.

## 3. Answer the setup questions

```bash
cp scripts/answers.example.json ~/hep/infrastructure/answers.json
open -e ~/hep/infrastructure/answers.json      # or any editor
```

Each field is explained in the file and in [decisions.md](../plugins/hep-sandbox/skills/setup-sandbox/references/decisions.md).
The important ones:
- `readonly_dirs`: dataset folders agents must not modify
- `remote_access`: `none`, `fermilab-kerberos-host-only`, or `ssh-key-hpc`

## 4. Generate the configuration

```bash
python3 scripts/render.py --answers ~/hep/infrastructure/answers.json --dry-run   # preview
python3 scripts/render.py --answers ~/hep/infrastructure/answers.json             # write
```

This writes `~/hep/infrastructure/hep-devcontainer/`. Existing files are never overwritten
silently: differences are shown as a diff and need `--force`.

## 5. Build and open

Optional test build first (5–15 min the first time):

```bash
cd ~/hep/infrastructure/hep-devcontainer
docker build --build-arg HOST_HEP="$HOME/hep" -t hep-dev:candidate .
```

Then in VS Code: Cmd+Shift+P → **Dev Containers: Open Folder in Container...** → choose
`~/hep/infrastructure/hep-devcontainer`. If VS Code offers to "Add Dev Container Configuration
Files", press Escape: you picked the wrong folder.

The bottom-left corner should read **Dev Container: HEP Analysis Environment**. The first start
runs `setup/verify.sh`; its last line should report `0 failed`.

## 6. Check the sandbox

In the container window, sign in to Claude Code (panel or `claude` in the terminal), then ask it
to run:

```bash
bash /workspace/hep/infrastructure/hep-devcontainer/setup/verify.sh --agent-probe
```

The process ancestry must show Linux paths, not `darwin`, and the summary must say `0 failed`.
From a Mac terminal you can check the container's real configuration:

```bash
docker inspect hep-dev --format '{{.HostConfig.Privileged}} {{.HostConfig.CapDrop}} {{.HostConfig.SecurityOpt}}'
# expect: false [ALL] [no-new-privileges:true]
```

## 7. Daily use

Read the generated `~/hep/infrastructure/hep-devcontainer/QUICKSTART.md`. It covers:
- opening the container
- where outputs go
- the persistent volumes
- the optional `hep` / `hep-stop` terminal aliases
- the agent survey

## Updating later

```bash
cd hep-agent-sandbox && git pull
python3 plugins/hep-sandbox/skills/setup-sandbox/scripts/render.py \
  --answers ~/hep/infrastructure/answers.json --dry-run
```

Review the diffs. Re-run with `--force` to take the new versions, then
**Dev Containers: Rebuild Container**. Your files, logins and `~/builds` survive rebuilds.

## On a new Mac

Restore `~/hep` from your backup. It contains `infrastructure/answers.json` and the generated
configuration. Then:
1. Redo the prerequisites (Docker Desktop, VS Code and the extension, the two settings, your SSH key).
2. Open the folder in the container.

Logins and `~/builds` live in Docker volumes, not in `~/hep`. So sign in again, and rebuild
compiled software from its recipes.
