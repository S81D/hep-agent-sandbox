#!/bin/bash
# Scan folders for credentials before they move into the agent-visible workspace.
#
# Usage: secret_scan.sh <folder> [<folder> ...]
#
# Prints FILENAMES only, never contents. Two checks:
#   1. credential-like filenames (keys, keytabs, .env, grid proxies, shell histories, ...)
#   2. text files under 1 MB containing private-key headers or common API-token patterns
# Exits 1 if anything was found. Read-only; written for macOS's built-in bash 3.2.

[ $# -ge 1 ] || { echo "usage: $0 <folder> [<folder> ...]" >&2; exit 2; }

# Private-key headers and token formats (Slack, GitHub, Anthropic, OpenAI, AWS).
CONTENT_PATTERN='-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|xox[baprs]-[0-9A-Za-z-]{10,}|hooks\.slack\.com/services/|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}'

found=0
for dir in "$@"; do
    [ -d "$dir" ] || { echo "skip (not a folder): $dir" >&2; continue; }
    echo "== $dir"

    names=$(find "$dir" \( -name 'id_rsa*' -o -name 'id_ed25519*' -o -name 'id_ecdsa*' -o -name '*.pem' \
            -o -name '*.p12' -o -name '*.keytab' -o -name 'krb5cc*' -o -name 'x509up*' -o -name '.netrc' \
            -o -name '.env' -o -name '*.env' -o -name '.pypirc' -o -iname '*credential*' -o -iname '*secret*' \
            -o -iname '*token*' -o -name '*_history' -o -name '.*history' \) \
            -not -path '*/.git/*' -not -path '*/node_modules/*' 2>/dev/null \
            | grep -vE '\.(h|hh|hpp|c|cc|cpp|cxx|C|py|f|F|inc|md|tex)$')
    if [ -n "$names" ]; then
        echo "  credential-like filenames (check each; source files with these words are excluded):"
        echo "$names" | sed 's/^/    /'
        found=1
    fi

    hits=$(find "$dir" -type f -size -1M -not -path '*/.git/*' -not -path '*/node_modules/*' \
            -not -name '*.root' -not -name '*.hepmc*' -not -name '*.pdf' -not -name '*.png' \
            -not -name '*.jpg' -not -name '*.o' -not -name '*.so' -not -name '*.a' -print0 2>/dev/null \
            | xargs -0 grep -lIE -- "$CONTENT_PATTERN" 2>/dev/null)
    if [ -n "$hits" ]; then
        echo "  files containing a private key or API token pattern:"
        echo "$hits" | sed 's/^/    /'
        found=1
    fi
    [ -z "$names$hits" ] && echo "  nothing found"
done
exit $found
