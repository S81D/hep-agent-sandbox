#!/bin/bash
# Read-only report on a Mac's readiness for the HEP dev container.
#
# Usage: preflight.sh [hep_dir]      (default hep_dir: ~/hep)
#
# Changes nothing, installs nothing, and makes no network requests. It prints only counts and
# settings, never key material or tokens. Written for macOS's built-in bash 3.2.

HEP_DIR="${1:-$HOME/hep}"
VSCODE_USER="$HOME/Library/Application Support/Code/User"
n_ok=0; n_warn=0; n_missing=0

ok()      { printf '  OK       %s\n' "$1"; n_ok=$((n_ok + 1)); }
warn()    { printf '  WARN     %s\n' "$1"; n_warn=$((n_warn + 1)); }
missing() { printf '  MISSING  %s\n' "$1"; n_missing=$((n_missing + 1)); }
info()    { printf '           %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

section "Mac"
if [ "$(uname -s)" != "Darwin" ]; then missing "this script is for macOS (found $(uname -s))"; fi
ok "macOS $(sw_vers -productVersion 2>/dev/null), $(uname -m) ($(sysctl -n machdep.cpu.brand_string 2>/dev/null))"
mem_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
if [ "$mem_gb" -ge 16 ]; then ok "RAM ${mem_gb} GB"; else warn "RAM ${mem_gb} GB (16 GB or more recommended)"; fi
free_gb=$(df -g "$HOME" | awk 'NR==2 {print $4}')
if [ "${free_gb:-0}" -ge 15 ]; then ok "free disk ${free_gb} GB"; else warn "free disk ${free_gb} GB (about 15 GB needed for the image)"; fi

section "Container runtime"
if [ -d /Applications/Docker.app ]; then ok "Docker Desktop installed"; docker_app=1; else docker_app=0; fi
if [ -d /Applications/OrbStack.app ] || [ -d "$HOME/Applications/OrbStack.app" ]; then
    ok "OrbStack installed (should work; less tested than Docker Desktop)"; orb_app=1
else orb_app=0; fi
[ "$docker_app$orb_app" = "00" ] && missing "no Docker Desktop or OrbStack (see prerequisites.md)"
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        ok "docker daemon running: $(docker info --format '{{.OperatingSystem}}, {{.Architecture}}, {{.NCPU}} CPUs' 2>/dev/null)"
        vm_gb=$(( $(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0) / 1073741824 ))
        if [ "$vm_gb" -ge 8 ]; then ok "Docker VM memory ${vm_gb} GB"; else warn "Docker VM memory ${vm_gb} GB (8 GB or more recommended)"; fi
    else
        warn "docker CLI found, but the daemon is not running (start Docker Desktop)"
    fi
else
    missing "docker CLI not found"
fi

section "VS Code"
if [ -d "/Applications/Visual Studio Code.app" ]; then ok "VS Code installed"; else missing "VS Code not found in /Applications"; fi
if ls -d "$HOME"/.vscode/extensions/ms-vscode-remote.remote-containers-* >/dev/null 2>&1; then
    ok "Dev Containers extension installed"
else
    missing "Dev Containers extension (ms-vscode-remote.remote-containers)"
fi
settings="$VSCODE_USER/settings.json"
for key in dev.containers.gitCredentialHelperConfigLocation dev.containers.dockerCredentialHelper; do
    if grep -q "\"$key\"" "$settings" 2>/dev/null; then
        ok "user setting $key: $(grep -o "\"$key\"[^,}]*" "$settings" | sed 's/.*: *//')"
    else
        warn "user setting $key not set: credentials would be forwarded into the container"
    fi
done

section "Developer tools"
if xcode-select -p >/dev/null 2>&1; then ok "Xcode Command Line Tools"; else missing "Xcode Command Line Tools (xcode-select --install)"; fi
for tool in git python3 gh claude; do
    if command -v "$tool" >/dev/null 2>&1; then
        ok "$tool: $("$tool" --version 2>&1 | head -1)"
    else
        case "$tool" in
            gh) info "gh (GitHub CLI) not found: optional" ;;
            claude) info "claude CLI not found: needed only for the guided (skill) path" ;;
            *) missing "$tool not found" ;;
        esac
    fi
done

section "SSH and git credentials"
key_count=$(ls "$HOME"/.ssh/id_* 2>/dev/null | grep -vc '\.pub$')
if [ "$key_count" -gt 0 ]; then ok "$key_count SSH private key file(s) in ~/.ssh (contents not read)"; else warn "no SSH key in ~/.ssh (needed for GitHub over SSH)"; fi
ssh-add -l >/dev/null 2>&1; agent_rc=$?
case $agent_rc in
    0) ok "ssh-agent holds $(ssh-add -l 2>/dev/null | wc -l | tr -d ' ') key(s)" ;;
    1) warn "ssh-agent is running but holds no keys (ssh-add -t 4h ~/.ssh/<key> when needed)" ;;
    *) warn "ssh-agent not reachable" ;;
esac
helpers=$(git config --get-all credential.helper 2>/dev/null | tr '\n' ' ')
if [ -n "$helpers" ]; then
    info "git credential helper on the Mac: $helpers(fine on the Mac; the VS Code setting above keeps it out of the container)"
fi

section "Backup and iCloud"
if [ -L "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Desktop" ]; then
    warn "iCloud Desktop & Documents sync appears ON: moving folders out of ~/Desktop removes them from iCloud"
else
    ok "iCloud Desktop sync not detected"
fi
if tmutil destinationinfo 2>/dev/null | grep -q 'Name'; then
    ok "Time Machine has a destination"
else
    warn "Time Machine has no destination: set up a backup before migrating folders into $HEP_DIR"
fi

section "Workspace ($HEP_DIR)"
if [ -d "$HEP_DIR" ]; then
    ok "$HEP_DIR exists ($(ls -A "$HEP_DIR" | wc -l | tr -d ' ') entries)"
    if [ -d "$HEP_DIR/infrastructure/hep-devcontainer" ]; then
        info "an existing configuration is at $HEP_DIR/infrastructure/hep-devcontainer (render.py will diff, not overwrite)"
    fi
else
    warn "$HEP_DIR does not exist yet (create it, then move projects in; see migration.md)"
fi

printf '\n=== %d ok, %d warnings, %d missing ===\n' "$n_ok" "$n_warn" "$n_missing"
[ "$n_missing" -eq 0 ]
