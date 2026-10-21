# Setup decisions

Ask about each of these with a recommended default. They map onto `answers.json` (see
`scripts/answers.example.json`).

## 1. Research folder (`hep_dir`)

Default `~/hep`. It must be inside the home folder. It is the **trust boundary**: everything in
it is visible to agents, and writable unless listed as read-only. Inside the container it is
always `/workspace/hep`; the image also creates `/Users/<you>/<folder>` as a symlink to it, so
absolute Mac paths written in analysis code keep working.

## 2. Read-only folders (`readonly_dirs`)

Folders inside `hep_dir` that agents may read but never modify: typically datasets, frozen
samples, published results. Each one becomes a read-only bind mount, enforced by the kernel
(even root in the container cannot remount it). `infrastructure/` is always read-only, so an
agent can never edit its own sandbox.

Cost: nothing in the container can write there, so outputs must go elsewhere (`<project>/results/`).
If a notebook writes next to its input data, that notebook will fail until its output path changes.

`extra_watch_excludes` (optional): large trees VS Code should not watch or search, such as a
Geant4 source checkout. Read-only folders and `*.root` files are excluded automatically.

## 3. Remote access (`remote_access`)

| Preset | Use when | What agents can do |
|---|---|---|
| `none` (default) | no remote computing, or you prefer to run everything remote yourself | Draft commands; you run them from a Mac terminal |
| `fermilab-kerberos-host-only` | Fermilab (gpvm) work | Same as `none`, with Fermilab/grid-specific rules. Fermilab SSH uses **Kerberos**, not SSH keys, so agent forwarding cannot reach it anyway; no Kerberos config enters the container |
| `ssh-key-hpc` | clusters that accept your SSH key | `ssh` to the hosts in `hpc_hosts` while your key is loaded on the Mac |

`ssh-key-hpc` gives agents **real** remote access whenever the key is loaded. The policy tells
them to ask before submissions, large transfers and deletions, but that is an instruction, not
an enforced boundary. Choose it only for hosts where you accept that. Each host's public key must
already be in `~/.ssh/known_hosts` (connect once from a Mac terminal and check the fingerprint);
`render.py` copies those public host keys into the container and refuses unknown hosts.

All presets keep `ForwardAgent no` (the key is never passed beyond the first host) and
`StrictHostKeyChecking yes`.

## 4. Python pins

**Default:** the tested pins in `template/setup/environment.yml` (Python 3.14, ROOT 6.40, numpy,
scipy, matplotlib, pandas, uproot, awkward, hist, vector, particle, iminuit, pyhepmc, jupyterlab,
Node.js 24, python-pptx, pandoc, KaTeX, Playwright). They solve on both `linux-aarch64` and
`linux-64`.

**Match the host:** if the user has an analysis conda env on the Mac (`conda env list`), copy its
key versions into the rendered `setup/environment.yml` so results match. Then check that it
solves for Linux **before** building (read-only; downloads only package indexes):

```bash
CONDA_OVERRIDE_GLIBC=2.39 CONDA_SUBDIR=linux-aarch64 \
  conda env create --dry-run -n test -f setup/environment.yml
```

Use `linux-64` on an Intel Mac. `CONDA_OVERRIDE_GLIBC` is needed because the Mac has no Linux
glibc; 2.39 is Ubuntu 24.04's. Some packages are not on conda-forge for every platform (e.g.
`pymupdf` for linux-aarch64), and the dry run reveals that.

Do not bump versions just because newer ones exist. The exact builds are recorded in the lock
file exported after the first build.

## 5. Personal section (`user_blurb`, `author_email`, `extra_preferences`)

Optional text added to the end of the agent policy, only in the user's local copy:
who they are (field, experience, languages they are learning), the email for author lines, and
working preferences (diff format, subagent model, ...). If they have a global
`~/.claude/CLAUDE.md`, offer to draft this from it; see [agent-memory.md](agent-memory.md).

## Not decisions (fixed by design)

- **No sudo, no capabilities, no Docker socket, no `--privileged`.** Packages are added through
  `environment.yml` or the Dockerfile and a rebuild.
- **Network is open.** Agents need their APIs, GitHub and package indexes. An outbound allowlist
  firewall is a possible later addition (see `docs/DESIGN.md`); it needs `NET_ADMIN` and is a
  deliberate exception, not a default.
- **Codex** is installed alongside Claude Code; unused, it costs only image size.
