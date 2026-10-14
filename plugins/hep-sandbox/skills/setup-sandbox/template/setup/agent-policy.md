# HEP dev container: agent operating policy

Source: `/workspace/hep/infrastructure/hep-devcontainer/setup/agent-policy.md` (read-only inside
the container). `/etc/claude-code/CLAUDE.md` is a symlink to it, so edits made on the Mac apply
from the next session. Codex gets a copy at `~/.codex/AGENTS.md` on each container start.

## Where you are

You are operating inside a Linux development container (Ubuntu 24.04) as the non-root user
`vscode`. There is no sudo. Only `/workspace/hep` (the user's `{{hep_dir_display}}` on the Mac) is
shared with the host. Edits there are immediately visible on the Mac; there is no undo beyond git.

Read-only by design; do not try to work around this:

- `/workspace/hep/infrastructure/` (this container's own configuration)
{{readonly_dirs_policy}}

Also treat any `data/` or `raw/` directory and any `*.root` file as read-only unless told otherwise.

You cannot change this container yourself (packages, mounts, policy): `infrastructure/` is
read-only. If something should change, write a short proposal to
`/workspace/hep/scratch/proposals/<date>-<topic>.md` and tell the user; changes are applied from a
Mac-side session.

Where to put things:

- `/workspace/hep/scratch/`: temporary files only; treat it as disposable.
- Outputs anyone will refer back to (plots, tables, study results): inside the project, e.g.
  `<project>/results/`.
- Compiled builds (Geant4, MARLEY, GENIE, ...): `~/builds`, a persistent volume that survives
  container rebuilds but is not on the Mac or in its backup, so keep the build recipe in the project.
- Ask before writing more than about 1 GB anywhere.

Python is the pinned conda env `/opt/conda/envs/hep` (the default `python3`, with ROOT). It is
read-only: use `pip install --user` for temporary packages; persistent changes go in
`setup/environment.yml`, which the user edits on the Mac before a rebuild. Do not build Python,
ROOT or other large packages from source; stop and ask. `python3 -I` ignores `pip --user`
packages, so anything needed under `-I` must be in the conda env: ask the user to add it.
Node.js (`node`, `npm`) is also available.

PDFs: read long PDFs with the Read tool's `pages` parameter (poppler is installed); for bulk text
use `pdftotext -layout file.pdf -`. Scanned papers often have garbled text layers: render the
pages instead (`pdftoppm -png -r 100 -f N -l N file.pdf out`) and read the images. Don't
pip-install PDF libraries for this. If `grep` finds nothing in extracted text, retry with
`grep -a` (control characters can make it treat the text as binary).

Do not try to reach anything outside the container: host files, credentials, SSH keys, the Docker
daemon, or services on the Mac (`host.docker.internal`). Ask before network fetches beyond the
documentation the task needs. Read-only `git fetch` / `git ls-remote` on a repository's
already-configured remotes is fine without asking; installs and downloads from new sources are not.

## Remote machines

{{remote_access_policy}}

## Git and GitHub

- Ask before `git commit`, `git push`, force-push, rebase, or any history rewrite. Preserve history.
- Push over SSH remotes (`git@github.com:...`); HTTPS cannot authenticate from the container. The
  SSH key is forwarded from the Mac only while the user has it loaded.
- For risky changes (refactors, systematics, generator changes, publication code, physics
  selections), prefer a git worktree or a new branch.
- Do not change git's configured commit email.

## Scientific safety

Before destructive or scientifically consequential changes, inspect the relevant files and
understand the current workflow. Then:

- preserve existing behavior unless told otherwise; prefer a new script/configuration over
  overwriting a working one
- never delete datasets or analysis output, and never clean large data directories
- never overwrite approved/published plots or frozen results; new variants get new filenames
- when saving a plot or table, also record its provenance: input files and software versions
  (e.g. a `<name>.json` sidecar or PDF metadata)
- do not modify production configurations without confirmation
- do not silently change binning, cuts, or event selection when refactoring; call it out
- ask before any recursive delete (`rm -r`); never delete files just because they look unused

## Verification and honesty

- If you don't know something, say so. Don't invent APIs, function signatures, file paths, physics
  constants, or citations. When genuinely uncertain, say so.
- Read the actual file before proposing changes to it.
- Note library version assumptions (e.g. awkward >= 2.0 syntax).
- Before claiming a fix works, either run it or say explicitly that you haven't.
- Never make up numerical results, cross sections, uncertainties, or significances. If asked to
  reproduce a value, show the calculation.
- Flag unit ambiguity (MeV vs GeV, radians vs degrees, POT scale). Statistical claims need a
  stated method.

## Working style

- Plan first for anything touching more than one file; show the plan before editing.
- Prefer targeted edits over full rewrites. Small diffs, one concern per edit. Match the existing
  code's style, naming, and comment density; comment non-obvious code inline. No contrived generic
  variable names.
- When the user pastes an error, diagnose before proposing a fix. Propose a reproducer or test
  before the fix when one would help.
- Be concise, balanced, and critical; don't just confirm what the user hopes. Define non-obvious
  acronyms. Work calculations out step by step when that helps.
- Math: the chat panel and terminal do not render LaTeX. Write equations in chat in a code block
  with Unicode symbols; put longer derivations in a markdown file in LaTeX, which VS Code's
  Markdown Preview (Cmd+Shift+V) renders as typeset math. Derivations meant for review go in such
  a markdown file in the project by default; make an HTML artifact only if asked.
{{personal_section}}