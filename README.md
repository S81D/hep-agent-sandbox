# hep-agent-sandbox

A sandboxed VS Code dev container for AI coding agents (Claude Code, Codex) doing
high-energy-physics work on a Mac. Agents run inside a Linux container that sees **only your
research folder** (default `~/hep`), with the tools HEP work needs, instead of running directly on
your Mac with access to everything.

**What you get**

- **HEP tooling:** Python 3.14 with ROOT 6.40, uproot, awkward, hist, iminuit, pyhepmc, jupyterlab
  (pinned via conda-forge); gcc/clang/cmake/gdb; a TeX Live subset (REVTeX, biber, LuaLaTeX,
  XeLaTeX); poppler for PDFs; Node.js; pandoc, KaTeX and python-pptx; headless Chromium with
  `page-check`, which reports problems in agents' HTML pages as text instead of token-hungry
  screenshots; the Claude Code and Codex CLIs.
- **Isolation:** one bind mount of your research folder, with optional read-only dataset folders.
  No sudo, all Linux capabilities dropped, no Docker socket, no Mac credentials.
- **GitHub over SSH:** through your Mac's forwarded ssh-agent; your key never enters the container.
- **Optional remote-access presets:** none, Fermilab via Kerberos (host-only), or SSH-key clusters.
- **A verification script:** checks the toolchain and the isolation from inside the container.
- **An agent policy:** instructions every agent session loads: scientific safety, provenance,
  grid stewardship.
- **An agent survey** to improve the setup from your agents' actual experience.

Read [docs/DESIGN.md](docs/DESIGN.md) for the security model: what is enforced, what is only an
instruction, and the risks that remain.

## Quick start with Claude Code (guided)

You need Docker Desktop, VS Code with the Dev Containers extension, and Claude Code on the Mac;
see the prerequisites linked below. In Claude Code on the Mac:

```text
/plugin marketplace add S81D/hep-agent-sandbox
/plugin install hep-sandbox@hep-agent-sandbox
```

Then ask: *"Set up the HEP agent sandbox"* (or run `/hep-sandbox:setup-sandbox`).

The skill takes you through these steps, asking before anything that changes your Mac:
1. a read-only check of the Mac
2. a few decisions
3. generating the configuration
4. building and verifying the container
5. optionally, migrating project folders and carrying over your Claude instructions and memories

## Manual setup (no Claude needed)

Follow [docs/MANUAL_SETUP.md](docs/MANUAL_SETUP.md). The only tools you need are on any Mac with
Xcode Command Line Tools: `bash` and `python3`.

## Before you start

- [Prerequisites](plugins/hep-sandbox/skills/setup-sandbox/references/prerequisites.md):
  - what to install, including Docker Desktop licensing for large organizations
  - two required VS Code settings
  - backups
  - the folder plan
- [Decisions](plugins/hep-sandbox/skills/setup-sandbox/references/decisions.md): read-only folders,
  remote access, Python pins.
- [Troubleshooting](plugins/hep-sandbox/skills/setup-sandbox/references/troubleshooting.md):
  every problem met while building this setup, with fixes.

## Repository layout

```text
.claude-plugin/marketplace.json      plugin marketplace manifest
plugins/hep-sandbox/
  skills/setup-sandbox/
    SKILL.md                         the guided workflow
    template/                        the container: Dockerfile, .devcontainer/, setup/, QUICKSTART.md
    scripts/                         preflight.sh, render.py, secret_scan.sh, answers.example.json
    references/                      prerequisites, decisions, migration, agent memory, troubleshooting
docs/                                DESIGN.md, MANUAL_SETUP.md
.github/workflows/ci.yml             builds and verifies the image on linux/arm64 and linux/amd64
```

## Status

Tested on:
- an Apple Silicon Mac: macOS 26, Docker Desktop 29.6, VS Code 1.135, Claude Code 2.1.291
- Intel (linux/amd64): the conda environment solves, and CI builds and verifies the image, but no
  Intel Mac has been tested end to end yet

OrbStack should work with Dev Containers but is untested.

Issues and suggestions are welcome.

## License

MIT
