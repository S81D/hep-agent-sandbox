#!/usr/bin/env bash
# Verification for the HEP dev container: toolchain, ROOT, Python, LaTeX, SSH, and the
# isolation (security) checks from README §16, §31 and §33.
#
# Every check runs (deliberately no `set -e`). Each prints PASS, FAIL or WARN, and the
# script exits non-zero if anything FAILed. Nothing here writes to the host except a
# zero-byte probe file in scratch/ that is removed immediately.
#
# Usage:
#   bash verify.sh                # full verification (runs as postCreateCommand)
#   bash verify.sh --agent-probe  # identity + isolation only; ask each AI agent to run this

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE="${SCRIPT_DIR}/environment.yml"
WORKSPACE=/workspace/hep

n_pass=0; n_fail=0; n_warn=0
pass() { printf '  PASS  %s\n' "$1"; n_pass=$((n_pass + 1)); }
fail() { printf '  FAIL  %s\n' "$1"; n_fail=$((n_fail + 1)); }
warn() { printf '  WARN  %s\n' "$1"; n_warn=$((n_warn + 1)); }
section() { printf '\n== %s ==\n' "$1"; }

# check "description" cmd...      PASS if cmd succeeds
check() { local desc=$1; shift; if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi; }
# check_not "description" cmd...  PASS if cmd FAILS (for things that must be impossible)
check_not() { local desc=$1; shift; if "$@" >/dev/null 2>&1; then fail "$desc"; else pass "$desc"; fi; }
# version "label" cmd...          PASS with the first line of output, FAIL if the command fails
version() {
    local label=$1; shift
    local out
    if out=$("$@" 2>&1) && [ -n "$out" ]; then pass "${label}: ${out%%$'\n'*}"; else fail "${label}: not available"; fi
}

# ---------------------------------------------------------------------------------------
identity() {
    section "Identity (where is this running?)"
    printf '  date      %s\n' "$(date)"
    printf '  kernel    %s\n' "$(uname -srm)"
    printf '  os        %s\n' "$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
    printf '  hostname  %s\n' "$(hostname)"
    printf '  user      %s\n' "$(id)"
    printf '  cwd       %s\n' "$(pwd)"
    printf '  shell     %s\n' "$(readlink /proc/$$/exe 2>/dev/null)"

    # Walk up the process tree: shows which program (e.g. the Claude/Codex binary) launched this.
    printf '  process ancestry (this script -> PID 1):\n'
    local pid=$$
    while [ -n "$pid" ] && [ "$pid" -gt 0 ] 2>/dev/null; do
        printf '    %6s  %s\n' "$pid" "$(ps -o args= -p "$pid" 2>/dev/null | cut -c1-150)"
        [ "$pid" -eq 1 ] && break
        pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    done

    if [ "$(uname -s)" = "Linux" ]; then pass "running on Linux (not macOS)"; else fail "running on $(uname -s): this is NOT the container"; fi
}

# ---------------------------------------------------------------------------------------
isolation() {
    section "Privileges"
    if [ "$(id -u)" -ne 0 ]; then pass "not running as root (uid $(id -u))"; else fail "running as root"; fi
    check_not "sudo cannot be used" sudo -n true
    if grep -q '^NoNewPrivs:[[:space:]]*1' /proc/self/status; then pass "no-new-privileges is set"; else fail "no-new-privileges is NOT set"; fi
    local capbnd
    capbnd=$(awk '/^CapBnd:/ {print $2}' /proc/self/status)
    if [ "$capbnd" = "0000000000000000" ]; then pass "all Linux capabilities dropped (CapBnd=0)"; else warn "capability bounding set is $capbnd (expected 0 with --cap-drop=ALL)"; fi

    section "Docker"
    check_not "no /var/run/docker.sock" test -e /var/run/docker.sock
    check_not "no /run/docker.sock" test -e /run/docker.sock
    check_not "no docker CLI" command -v docker
    check_not "host Docker API not reachable on host.docker.internal:2375" \
        timeout 3 bash -c '</dev/tcp/host.docker.internal/2375'

    section "Host filesystem"
    pass_if_exists() { if [ -e "$1" ]; then pass "positive control exists: $1"; else fail "positive control missing: $1"; fi; }
    pass_if_exists "${WORKSPACE}/infrastructure/hep-devcontainer/.devcontainer/devcontainer.json"

    # The image creates /Users/<you>/<hep folder> -> /workspace/hep for path parity. Nothing else
    # from the Mac's home directory may exist next to it.
    local host_link="" host_home candidate
    for candidate in /Users/*/*; do
        if [ -L "$candidate" ] && [ "$(readlink "$candidate")" = "$WORKSPACE" ]; then host_link=$candidate; break; fi
    done
    if [ -n "$host_link" ]; then
        host_home=$(dirname "$host_link")
        if [ "$(readlink "$host_link")" = "$WORKSPACE" ]; then pass "$host_link is only a symlink to $WORKSPACE"; else fail "$host_link is not the expected symlink"; fi
        if [ "$(ls -A "$host_home")" = "$(basename "$host_link")" ]; then pass "$host_home contains nothing but the $(basename "$host_link") symlink"; else fail "$host_home contains: $(ls -A "$host_home" | tr '\n' ' ')"; fi
        # Canaries: real files/dirs on the Mac that must NOT be visible in the container.
        local canary
        for canary in Desktop Documents Downloads Library .ssh .ssh/id_ed25519 .zshrc .claude .codex; do
            check_not "host path not visible: ${host_home}/${canary}" test -e "${host_home}/${canary}"
        done
    else
        warn "no /Users/<you>/<folder> -> $WORKSPACE path-parity symlink found"
    fi
    check_not "~/Desktop in the container is not the Mac Desktop" test -e "$HOME/Desktop"

    # Every mount in the container, from the kernel's view. Field 4 is the source path within
    # the backing filesystem, field 5 the mount point, field 6 the mount options.
    printf '  mounts backed by host files or volumes:\n'
    awk '$5 ~ /^\/(workspace|home|run\/host-services|Users)/ {split($6, o, ","); printf "    %-55s %s  (src %s)\n", $5, o[1], $4}' /proc/self/mountinfo
    if awk '{print $4, $5}' /proc/self/mountinfo | grep -qE '/(Desktop|Documents|Downloads|Library|\.ssh)(/|$)|docker\.sock'; then
        fail "a mount references Desktop/Documents/Downloads/Library/.ssh or docker.sock"
    else
        pass "no mount references Desktop/Documents/Downloads/Library/.ssh or docker.sock"
    fi

    # Read-only overlays must reject writes (kernel-enforced); scratch must accept them.
    # The overlays are found from the kernel's mount table, so this works for any list in
    # devcontainer.json. mountinfo escapes spaces etc. as octal (\040); printf %b decodes them.
    local dir probe raw
    local readonly_dirs=()
    while read -r raw; do
        readonly_dirs+=("$(printf '%b' "$raw")")
    done < <(awk -v ws="$WORKSPACE/" 'index($5, ws) == 1 && $6 ~ /^ro(,|$)/ {print $5}' /proc/self/mountinfo)
    # infrastructure/ must always be among them: otherwise an agent could edit its own sandbox.
    if printf '%s\n' "${readonly_dirs[@]}" | grep -qx "${WORKSPACE}/infrastructure"; then
        pass "${WORKSPACE}/infrastructure is mounted read-only"
    else
        fail "${WORKSPACE}/infrastructure is NOT mounted read-only"
    fi
    for dir in "${readonly_dirs[@]}"; do
        probe="${dir}/.verify-write-probe-$$"
        if touch "$probe" 2>/dev/null; then rm -f "$probe"; fail "writable (should be read-only): $dir"; else pass "read-only: $dir"; fi
    done
    if [ -d "${WORKSPACE}/scratch" ]; then
        probe="${WORKSPACE}/scratch/.verify-write-probe-$$"
        if touch "$probe" 2>/dev/null; then rm -f "$probe"; pass "writable: ${WORKSPACE}/scratch"; else fail "not writable: ${WORKSPACE}/scratch"; fi
    else
        warn "${WORKSPACE}/scratch does not exist (create scratch/ in the hep folder on the Mac)"
    fi

    section "Credentials"
    # -xdev: search only the container's own filesystem (the ~/hep mount was scanned separately).
    local keys
    keys=$(find / -xdev \( -name 'id_rsa' -o -name 'id_ed25519' -o -name 'id_ecdsa' -o -name 'id_dsa' -o -name '*.pem' -path '*/.ssh/*' \) 2>/dev/null | head -5)
    if [ -z "$keys" ]; then pass "no SSH private key files in the container"; else fail "private key files found: $keys"; fi

    local helpers
    helpers=$(git config --get-all credential.helper 2>/dev/null)
    if [ -z "$helpers" ]; then pass "no git credential helper configured"; else fail "git credential helper(s) present: $(echo $helpers)"; fi
    # Ask git for a GitHub HTTPS credential with every interactive fallback disabled.
    if printf 'protocol=https\nhost=github.com\n\n' \
        | GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false SSH_ASKPASS=/bin/false timeout 10 git credential fill 2>/dev/null \
        | grep -q '^password='; then
        fail "git credential fill returned a GitHub password/token"
    else
        pass "git credential fill returns no GitHub token"
    fi
    local askpass
    askpass=$(env | cut -d= -f1 | grep -E 'ASKPASS' | tr '\n' ' ')
    if [ -z "$askpass" ]; then pass "no git askpass bridge in environment"; else warn "askpass variables present (VS Code git bridge?): $askpass"; fi

    # Names only, never values. SSH_AUTH_SOCK is expected.
    local suspicious
    suspicious=$(env | cut -d= -f1 | grep -iE 'TOKEN|SECRET|PASSW|API_?KEY|CREDENTIAL|AUTH' | grep -vx 'SSH_AUTH_SOCK' | tr '\n' ' ')
    if [ -z "$suspicious" ]; then pass "no credential-like environment variable names"; else warn "review these environment variable names: $suspicious"; fi

    # Fermilab access is host-only. The kinit binary itself is present (conda-forge krb5 is a
    # ROOT dependency), so check for what would actually grant access: FNAL config or tickets.
    check_not "no Kerberos config in /etc/krb5.conf (Fermilab access is host-only)" test -e /etc/krb5.conf
    check_not "no Kerberos ticket cache" klist -s
    local keytabs
    keytabs=$(find / -xdev -name '*.keytab' 2>/dev/null | head -3)
    if [ -z "$keytabs" ]; then pass "no Kerberos keytab files"; else fail "keytab files found: $keytabs"; fi

    section "SSH agent (forwarded from macOS by VS Code)"
    # VS Code's Dev Containers extension forwards the Mac ssh-agent into processes it starts
    # (terminals, extensions). Outside VS Code (e.g. plain docker exec) there is no agent.
    if [ -z "${SSH_AUTH_SOCK:-}" ]; then
        warn "no ssh-agent forwarded (expected outside VS Code; GitHub over SSH unavailable here)"
        return
    fi
    if [ -S "$SSH_AUTH_SOCK" ]; then pass "SSH_AUTH_SOCK is a socket: $SSH_AUTH_SOCK"; else fail "SSH_AUTH_SOCK is not a socket: '$SSH_AUTH_SOCK'"; fi
    local agent_out agent_rc
    agent_out=$(ssh-add -l 2>&1); agent_rc=$?
    case $agent_rc in
        0) pass "agent reachable; public fingerprints only:"; printf '%s\n' "$agent_out" | sed 's/^/          /' ;;
        1) warn "agent reachable but holds no keys (on the Mac: ssh-add -t 4h ~/.ssh/id_ed25519)" ;;
        *) fail "cannot reach the ssh-agent: $agent_out" ;;
    esac
}

# ---------------------------------------------------------------------------------------
policy_checks() {
    section "Agent policy"
    # /etc/claude-code/CLAUDE.md is a symlink into the read-only infrastructure/ mount, so the
    # Mac-side file is what agents load and they cannot edit it.
    local policy_src="${SCRIPT_DIR}/agent-policy.md"
    if [ -r /etc/claude-code/CLAUDE.md ] && [ "$(readlink -f /etc/claude-code/CLAUDE.md)" = "$policy_src" ]; then
        pass "/etc/claude-code/CLAUDE.md -> $policy_src"
    else
        fail "/etc/claude-code/CLAUDE.md missing or not linked to $policy_src"
    fi
    check_not "policy source is not writable from the container" test -w "$policy_src"
    if python3 -c 'import json, sys; json.load(open(sys.argv[1]))' /etc/claude-code/managed-settings.json 2>/dev/null; then
        pass "managed-settings.json readable and valid JSON"
    else
        fail "managed-settings.json missing or invalid"
    fi
}

# ---------------------------------------------------------------------------------------
toolchain() {
    section "Toolchain"
    version "Ubuntu" bash -c '. /etc/os-release && echo "$VERSION"'
    version "gcc" gcc --version
    version "g++" g++ --version
    version "clang" clang --version
    version "cmake" cmake --version
    version "make" make --version
    version "gdb" gdb --version
    version "git" git --version
    version "git-lfs" git lfs version
    version "ssh" ssh -V
    version "rsync" rsync --version
    version "tmux" tmux -V
    version "python3" python3 --version
    version "micromamba" micromamba --version
    version "claude" claude --version
    version "codex" codex --version
    version "node" node --version
    # Ubuntu's GNU time reports its version as "UNKNOWN", so check that it exists instead.
    check "GNU time installed (/usr/bin/time)" test -x /usr/bin/time
    check "bc works" bash -c '[ "$(echo 2+2 | bc)" = 4 ]'
}

storage_checks() {
    section "Persistent build volume (~/builds)"
    # ~/builds must be its own mount (the hep-builds Docker volume); a plain directory in the
    # container would be wiped by the next rebuild.
    if awk -v d="$HOME/builds" '$5 == d' /proc/self/mountinfo | grep -q .; then
        pass "~/builds is a separate mount (persistent volume)"
    else
        warn "~/builds is not a mounted volume: builds there would be lost on rebuild (expected outside VS Code)"
    fi
    local probe="$HOME/builds/.verify-write-probe-$$"
    if touch "$probe" 2>/dev/null; then rm -f "$probe"; pass "~/builds is writable"; else fail "~/builds is not writable"; fi
}

root_checks() {
    section "ROOT"
    local pinned
    pinned=$(sed -nE 's/^[[:space:]]*-[[:space:]]*root=([0-9.]+).*/\1/p' "$ENV_FILE")
    local got
    got=$(root-config --version 2>/dev/null)
    if [ -n "$got" ] && [ "$got" = "$pinned" ]; then pass "root-config --version: $got (matches pin)"; else fail "root-config --version: '$got' (pinned: $pinned)"; fi
    # Plain start/stop (README §33). Note: with -e, ROOT's exit code is the value of the last
    # expression, so e.g. a printf would make it exit non-zero.
    check "root -l -b -q starts and exits cleanly" root -l -b -q
    version "PyROOT" python3 -c 'import ROOT; print(ROOT.__version__)'

    # Compile and link a small program against ROOT with the system g++ (Ubuntu gcc), the way
    # standalone analysis code would be built. ROOT itself was built by conda-forge's gcc.
    local tmp
    tmp=$(mktemp -d)
    cat > "${tmp}/hist_test.cxx" <<'CXX'
#include <TH1D.h>
#include <iostream>
int main() {
    TH1D h("h", "h", 10, 0., 1.);
    h.Fill(0.5);
    std::cout << "entries: " << h.GetEntries() << std::endl;
    return h.GetEntries() == 1 ? 0 : 1;
}
CXX
    if g++ "${tmp}/hist_test.cxx" $(root-config --cflags --libs) -o "${tmp}/hist_test" >"${tmp}/build.log" 2>&1 \
        && "${tmp}/hist_test" >"${tmp}/run.log" 2>&1; then
        pass "g++ program linked against ROOT builds and runs"
    else
        fail "g++ + ROOT build/run failed:"
        sed 's/^/          /' "${tmp}/build.log" "${tmp}/run.log" 2>/dev/null | tail -8
    fi
    rm -rf "$tmp"
}

python_checks() {
    section "Python packages (compared with setup/environment.yml pins)"
    python3 - "$ENV_FILE" <<'PY'
import importlib.metadata as md
import re, sys

# conda package name -> installed Python distribution name, where they differ
DIST_NAME = {"matplotlib-base": "matplotlib", "pyyaml": "PyYAML"}
NOT_PYTHON = {"python", "root", "nodejs"}  # not Python packages, or checked elsewhere

failures = 0
for line in open(sys.argv[1]):
    m = re.match(r"\s*-\s*([A-Za-z0-9_.-]+)=([0-9][^\s#]*)", line)
    if not m or m.group(1) in NOT_PYTHON:
        continue
    name, pinned = m.groups()
    try:
        installed = md.version(DIST_NAME.get(name, name))
    except md.PackageNotFoundError:
        print(f"  FAIL  {name}: not installed (pinned {pinned})"); failures += 1; continue
    status = "PASS" if installed == pinned else "FAIL"
    failures += status == "FAIL"
    print(f"  {status}  {name} {installed}" + ("" if status == "PASS" else f" (pinned {pinned})"))

# The imports analyses actually use must work, not just be installed.
for module in ["numpy", "scipy", "matplotlib", "pandas", "uproot", "awkward", "hist",
               "vector", "particle", "iminuit", "pyhepmc"]:
    try:
        __import__(module)
    except Exception as err:
        print(f"  FAIL  import {module}: {err}"); failures += 1
sys.exit(1 if failures else 0)
PY
    local rc=$?
    # Fold the Python block's result into the counters (it printed its own lines).
    if [ $rc -eq 0 ]; then n_pass=$((n_pass + 1)); else n_fail=$((n_fail + 1)); fi
}

latex_checks() {
    section "LaTeX (smoke tests built in a temporary directory, not in ~/hep)"
    version "latexmk" latexmk --version
    version "pdflatex" pdflatex --version
    version "xelatex" xelatex --version
    version "lualatex" lualatex --version
    version "bibtex" bibtex --version
    version "biber" biber --version

    local tmp
    tmp=$(mktemp -d)
    cat > "${tmp}/refs.bib" <<'BIB'
@article{Gardiner2021,
  author  = {Gardiner, S.},
  title   = {Simulating low-energy neutrino interactions with MARLEY},
  journal = {Comput. Phys. Commun.},
  volume  = {269},
  pages   = {108123},
  year    = {2021}
}
BIB
    # REVTeX 4-2 + natbib/BibTeX: the main paper setup in ~/hep.
    cat > "${tmp}/revtex.tex" <<'TEX'
\documentclass[prc,twocolumn]{revtex4-2}
\usepackage{amsmath,graphicx,booktabs,siunitx,physics,tikz,hyperref}
\begin{document}
\title{Smoke test}\author{HEP container}\maketitle
Energy $E_\nu = \SI{30}{\MeV}$, $\expval{\sigma} \propto \abs{M}^2$ \cite{Gardiner2021}.
\begin{tikzpicture}\draw (0,0) -- (1,1);\end{tikzpicture}
\bibliography{refs}
\end{document}
TEX
    # biblatex + biber
    cat > "${tmp}/biblatex.tex" <<'TEX'
\documentclass{article}
\usepackage[backend=biber]{biblatex}\addbibresource{refs.bib}
\begin{document}Test \cite{Gardiner2021}.\printbibliography\end{document}
TEX
    # XeLaTeX + unicode-math (OpenType math fonts)
    cat > "${tmp}/xetex.tex" <<'TEX'
\documentclass{article}
\usepackage{unicode-math}
\begin{document}$\nu_e + {}^{40}\mathrm{Ar} \to e^- + {}^{40}\mathrm{K}^*$, $α β γ$\end{document}
TEX
    # LuaLaTeX + tikz-feynman (its automatic diagram layout requires LuaLaTeX)
    cat > "${tmp}/luatex.tex" <<'TEX'
\documentclass{article}
\usepackage{tikz-feynman}
\begin{document}
\feynmandiagram [horizontal=a to b] { i1 -- [fermion] a -- [fermion] i2, a -- [photon] b, f1 -- [fermion] b -- [fermion] f2 };
\end{document}
TEX
    local doc engine
    for doc in "revtex:-pdf" "biblatex:-pdf" "xetex:-xelatex" "luatex:-lualatex"; do
        engine=${doc#*:}; doc=${doc%%:*}
        # Console output goes to *.console, NOT *.out: hyperref uses <jobname>.out for bookmarks.
        if (cd "$tmp" && timeout 600 latexmk "$engine" -interaction=nonstopmode -halt-on-error "${doc}.tex" >"${doc}.console" 2>&1) \
            && [ -s "${tmp}/${doc}.pdf" ]; then
            pass "latexmk ${engine} ${doc}.tex"
        else
            fail "latexmk ${engine} ${doc}.tex (last log lines:)"
            grep -E '^!|Error|not found' "${tmp}/${doc}.log" 2>/dev/null | head -5 | sed 's/^/          /'
        fi
    done

    # Poppler: Claude Code renders PDF page ranges with pdftoppm. Reuse the REVTeX PDF from above.
    section "PDF tools (poppler)"
    check "pdftoppm installed" command -v pdftoppm
    check "pdftotext installed" command -v pdftotext
    if [ -s "${tmp}/revtex.pdf" ]; then
        if pdftoppm -png -r 50 -f 1 -l 1 "${tmp}/revtex.pdf" "${tmp}/page" 2>/dev/null \
            && ls "${tmp}"/page*.png >/dev/null 2>&1; then
            pass "pdftoppm renders a PDF page to PNG"
        else
            fail "pdftoppm could not render the test PDF"
        fi
        if pdftotext -layout "${tmp}/revtex.pdf" - 2>/dev/null | grep -q 'Smoke test'; then
            pass "pdftotext extracts the text"
        else
            fail "pdftotext did not extract the expected text"
        fi
    else
        warn "no test PDF to exercise poppler (the REVTeX build failed above)"
    fi
    rm -rf "$tmp"
}

workspace_checks() {
    section "Workspace"
    if [ -d "$WORKSPACE" ]; then pass "$WORKSPACE is mounted: $(ls "$WORKSPACE" | tr '\n' ' ')"; else fail "$WORKSPACE missing"; fi
    # git must work on host-owned repositories through the bind mount.
    local repo
    repo=$(find "$WORKSPACE" -maxdepth 4 -name .git -type d -not -path '*/infrastructure/*' 2>/dev/null | head -1)
    if [ -n "$repo" ]; then
        check "git status works in $(dirname "$repo")" git -C "$(dirname "$repo")" status --short
    else
        warn "no git repository found to test"
    fi
}

# ---------------------------------------------------------------------------------------
echo "=== HEP dev container verification ==="
identity
isolation
policy_checks
if [ "${1:-}" != "--agent-probe" ]; then
    toolchain
    storage_checks
    root_checks
    python_checks
    latex_checks
    workspace_checks
fi

printf '\n=== %d passed, %d failed, %d warnings ===\n' "$n_pass" "$n_fail" "$n_warn"
[ "$n_fail" -eq 0 ]
