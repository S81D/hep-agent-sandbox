# Design: a sandbox for AI coding agents doing HEP work on a Mac

## Goal

AI coding agents (Claude Code, Codex) run shell commands, edit files and install packages. Run
directly on a Mac, they see everything the user can see: the whole home folder, SSH keys,
browser data, other projects. This setup moves the agents' execution into a Linux container that
sees **one** folder, the research workspace, plus the tools HEP work needs.

```text
macOS (trusted)
 ├─ VS Code UI ── Dev Containers extension (runs on the Mac side)
 ├─ ssh-agent (your key stays here)      ─┐  forwarded by VS Code
 ├─ Kerberos / Fermilab ssh (host-only)   │
 └─ Docker Desktop VM (linux/arm64 or amd64)
      └─ HEP dev container  (user vscode, no sudo, cap-drop=ALL, no-new-privileges, no docker.sock)
           ├─ VS Code server + extensions (Python, Jupyter, C/C++, CMake, LaTeX Workshop,
           │   Claude Code, Codex)                         ← agents execute here
           ├─ conda env: Python + ROOT + HEP stack (pinned), Node.js, KaTeX, pandoc
           ├─ gcc/clang/cmake/gdb, TeX Live subset, poppler, headless Chromium (page-check)
           ├─ /workspace/hep            ← bind mount of ~/hep (read-write)
           │    ├─ infrastructure/      ← read-only (agents can't edit their own sandbox)
           │    └─ <dataset folders>    ← read-only (chosen per user)
           ├─ ~/.claude, ~/.codex, ~/builds  ← named Docker volumes
           └─ ssh → GitHub (and optional SSH-key clusters) via the forwarded agent
```

## The trust boundary

`~/hep` is deliberately the agents' world. Anything in it is readable by agents, and writable
unless mounted read-only. Nothing else from the Mac is mounted.

| Inside the container | Source | Access |
|---|---|---|
| `/workspace/hep` | `~/hep` on the Mac | read-write |
| `/workspace/hep/infrastructure` | the container's own configuration | **read-only** |
| `/workspace/hep/<dataset dirs>` | chosen per user | **read-only** |
| `/home/vscode/.claude`, `.codex` | volumes `hep-claude-config`, `hep-codex-home` | agent logins and state |
| `/home/vscode/builds` | volume `hep-builds` | compiled software, survives rebuilds |
| `/Users/<you>/hep` | symlink to `/workspace/hep` | path parity for absolute Mac paths |

Read-only overlays are second bind mounts on top of the workspace mount, enforced by the kernel.
Remounting them read-write needs `CAP_SYS_ADMIN`, which the container does not have, so even root
inside the container could not undo them.

## Enforced properties

- **Mounts:** only the workspace and the named volumes. Never `~`, `~/Desktop`, `~/Documents`,
  `~/Downloads`, `~/Library`, `~/.ssh`, or `/var/run/docker.sock`.
- **No privilege:** non-root `vscode` user, no sudo, `--cap-drop=ALL`,
  `--security-opt=no-new-privileges:true`, never `--privileged`.
- **No Docker control:** no socket and no docker CLI, so agents cannot start other containers
  (which could mount anything).
- **Credentials:** the Mac's git and Docker credential helpers are **not** forwarded (two VS Code
  user settings), and VS Code's git askpass bridge is disabled. SSH uses agent forwarding: the
  container can ask the Mac's ssh-agent for signatures while a key is loaded, but never receives
  the key. `ForwardAgent no` stops it travelling further.
- **Fermilab** (if chosen): Kerberos stays on the Mac. No ticket, keytab or Kerberos config enters
  the container.

`setup/verify.sh` checks all of this from inside the container (uid, capabilities,
no-new-privileges, Docker socket, canary Mac paths, mount table, read-only overlays, credential
helpers, credential-like environment variable names, ssh-agent), together with the toolchain.

## Instructions are not enforcement

The agent policy (`setup/agent-policy.md`, loaded as managed Claude Code instructions) and the
"ask" permission rules (`managed-settings.json`) shape agent behaviour: ask before pushing,
deleting, large writes, grid submissions; record provenance; keep scientific results intact. They
are **not** security boundaries: an agent can bypass a permission rule (e.g. through
`python -c`), and instructions can be ignored or overridden by prompt injection. The enforced
boundaries are the mounts, the missing privileges and the missing credentials.

The policy is a symlink into the read-only `infrastructure/` mount: edits on the Mac apply from
the next session, and agents cannot change it. `managed-settings.json` is copied into the image
instead, because Claude Code refuses to start if that file exists but cannot be read.

## Reproducibility

- Base image pinned by digest (multi-arch index), micromamba, Claude Code and Codex pinned.
- The conda env is pinned in `environment.yml`; the exact builds are exported to a lock file
  after the first build. The default pins solve on both `linux-aarch64` and `linux-64`.
- `apt-get` installs current Ubuntu 24.04 packages at build time (not pinned).
- The container is disposable: `~/hep` on the Mac is authoritative, so back it up.

## Residual risks (not removed by this design)

- **Write-back:** anything an agent writes into `~/hep` (scripts, git hooks, `.vscode/tasks.json`,
  Makefiles) runs unsandboxed if you later execute it on the Mac. Run workspace code inside the
  container; open `~/hep` on the Mac in VS Code's Restricted Mode.
- **Forwarded SSH key:** usable (not extractable) by agents while loaded. Load with a lifetime
  (`ssh-add -t 4h`).
- **Open network:** agents can reach any host, so they could upload workspace contents or fetch
  and run code, typically after prompt injection from a web page or document. They can also reach
  services listening on the Mac via `host.docker.internal`.
- **Agents' own logins** in the volumes are readable by those agents.
- **Headless Chromium without its own sandbox:** `page-check` runs Playwright's Chromium with
  `--no-sandbox`, because Chromium's sandbox needs user namespaces or a setuid helper, which
  `--cap-drop=ALL` and `no-new-privileges` rule out. A browser exploit in a page would run with
  the agent's own rights in the container, no more. `page-check` serves only the page's own
  folder and blocks requests outside the artifact CDN allowlist.
- **Agents outside the container stay unsandboxed:** desktop AI apps, and VS Code windows not
  attached to the container.

## A future network allowlist

An outbound allowlist firewall (iptables inside the container, as in Anthropic's reference
devcontainer) would close most of the network risk. It needs `NET_ADMIN`, a deliberate exception,
and a maintained list of hosts. Domains agents actually needed in the first sessions:

| Domain | Used for |
|---|---|
| Anthropic API (`api.anthropic.com`), `claude.ai` | Claude Code itself, artifacts |
| `github.com` (+ `api.github.com`, `objects.githubusercontent.com`) | git, releases |
| `pypi.org`, `files.pythonhosted.org` | temporary pip installs |
| `conda.anaconda.org` | conda packages (build time) |
| `cdn.playwright.dev` | headless Chromium for `page-check` (build time) |
| `cdnjs.cloudflare.com`, `cdn.jsdelivr.net` | JavaScript libraries (e.g. MathJax) |
| VS Code marketplace / update servers | extensions (build/attach time) |
