# Prerequisites (pre-work before setup)

Do these on the Mac before running the setup. `scripts/preflight.sh` checks most of them.
Nothing here is installed by the setup itself.

## 1. Mac and disk

- **Apple Silicon or Intel Mac.** The image builds natively for both (`linux/arm64`,
  `linux/amd64`). Apple Silicon is the better-tested path.
- **macOS** recent enough for the current Docker Desktop. Check Docker's page for the
  supported versions: <https://docs.docker.com/desktop/setup/install/mac-install/>.
- **RAM:** 16 GB or more recommended (Docker's VM should get 8 GB or more).
- **Disk:** about 15 GB free for the image and build cache, plus whatever you build in `~/builds`.

## 2. Software to install

| What | Why | Where |
|---|---|---|
| **Docker Desktop** (or OrbStack) | runs the Linux container | <https://www.docker.com/products/docker-desktop/> |
| **VS Code** | editor; attaches to the container | <https://code.visualstudio.com/> |
| **Dev Containers** extension (`ms-vscode-remote.remote-containers`) | builds and opens the container | VS Code → Extensions |
| **Xcode Command Line Tools** | git, python3 (for `render.py`) | `xcode-select --install` |
| **Claude Code** (optional, for the guided path) | runs this setup skill | <https://code.claude.com/docs/en/setup> |
| **GitHub CLI** `gh` (optional) | convenient GitHub access | <https://cli.github.com/> |

**Docker Desktop licensing:** Docker Desktop is free for personal use, education, small
businesses and non-commercial open source, but **larger organizations need a paid
subscription**. Check what applies to you or your institution before installing:
<https://www.docker.com/pricing/>. OrbStack has its own license terms. This setup has been
tested with Docker Desktop; OrbStack should work with Dev Containers but is less tested.

After installing Docker Desktop: Settings → Resources → give the VM **8 GB or more** of memory.
Optionally: Settings → General → *Start Docker Desktop when you sign in*.

## 3. VS Code settings (required for security)

Add to your VS Code **user** settings (Cmd+Shift+P → *Preferences: Open User Settings (JSON)*):

```json
"dev.containers.gitCredentialHelperConfigLocation": "none",
"dev.containers.dockerCredentialHelper": false
```

By default the Dev Containers extension forwards the Mac's git credential helper (e.g. your
keychain's GitHub token) and Docker credential helper into the container. These two lines stop
that. They must be user settings, not workspace settings, so an agent cannot change them.

## 4. SSH key for GitHub (if you use SSH remotes)

- Have a key in `~/.ssh` (e.g. `id_ed25519`) that is added to your GitHub account
  (<https://docs.github.com/en/authentication/connecting-to-github-with-ssh>).
- Load it when you need GitHub access from the container: `ssh-add -t 4h ~/.ssh/id_ed25519`.
  The key stays on the Mac; the container only gets signatures through the forwarded agent.
- HTTPS remotes cannot authenticate from the container (by design). Push those from the Mac,
  or switch them to SSH.

## 5. Backup (before moving any folders)

The research folder becomes the agent's writable workspace, and if your projects currently live
on an iCloud-synced Desktop, moving them out removes them from iCloud. Set up a backup that
covers the research folder **first**: Time Machine (System Settings → General → Time Machine)
or your institution's backup.

## 6. Folder plan

- Pick one research folder, default `~/hep`. Everything in it will be visible to (and, except
  read-only folders, writable by) AI agents.
- Put in: analysis code, generators, papers, notes, datasets you work on locally.
- **Never** put in: SSH or GPG keys, passwords, API tokens, `.env` files, grid proxies
  (`x509up_*`), Kerberos keytabs, browser data, email archives, personal documents.
- A typical layout (adapt freely; organizing by experiment is fine):
  ```text
  ~/hep/
  ├── analyses/  generators/  papers/  common/
  ├── scratch/          (temporary; created if missing)
  └── infrastructure/   (the container configuration; read-only inside the container)
  ```
- Create `scratch/` (agents use it for temporary files) and `infrastructure/`.
- If projects still live elsewhere, plan the move with [migration.md](migration.md); you can
  also start with a near-empty folder and move projects in later.
