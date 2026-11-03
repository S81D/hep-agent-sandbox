#!/usr/bin/env python3
"""Write a self-contained side-by-side (before | after) HTML review page for
a git change set. Python 3.8+ standard library and the git CLI only.

Installed in the container as `side-by-side-diff`; on the Mac run this file with python3.

What is compared (pick one; default: the working tree against HEAD):
  side-by-side-diff -o review.html                      working tree vs HEAD
  side-by-side-diff -o review.html --staged             index vs HEAD
  side-by-side-diff -o review.html --base A --target B  commit B vs commit A
  side-by-side-diff -o review.html --base main          working tree vs main

Options:
  --repo DIR            repository (default: current directory)
  --include-untracked   also show untracked (new, not ignored) files as added
  --exclude GLOB        leave out matching paths (repeatable), e.g. 'scripts/*'
  --context N           unchanged lines shown around each change (default 4)
  --title TEXT          page heading
  --strip-prefix P      shorten displayed paths by removing leading P

Layout: per file, one table with four columns (line number and code for each
side). difflib's next-change link columns are removed, line-number columns are
narrow, the two code columns share the width equally and long lines wrap at
the column edge. Distant changes in one file are separated by a dashed rule.
"""

import argparse
import difflib
import fnmatch
import html
import os
import re
import subprocess
import sys


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=False)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr.decode(errors='replace')}")
    return r


def read_side(repo, spec, path):
    """Bytes of `path` on one side: spec is a ref, ':' (the index) or None
    (the working tree). Missing file -> None."""
    if spec is None:
        full = os.path.join(repo, path)
        return open(full, "rb").read() if os.path.isfile(full) else None
    r = git(repo, "show", f"{spec}:{path}" if spec != ":" else f":{path}", check=False)
    return r.stdout if r.returncode == 0 else None


def as_lines(data):
    return [] if data is None else data.decode("utf-8", errors="replace").splitlines()


def changes(repo, base, target, staged, include_untracked):
    """[(old_path, new_path, status, added, removed)] in git's order."""
    args = ["diff", "-M", "--name-status", "-z"]
    if staged:
        args.append("--cached")
    args.append(base)
    if target:
        args.append(target)
    fields = git(repo, *args).stdout.decode().split("\0")
    out, i = [], 0
    while i < len(fields) and fields[i]:
        st = fields[i]
        if st[0] in "RC":            # rename/copy: two paths follow
            out.append([fields[i + 1], fields[i + 2], st[0]])
            i += 3
        else:
            out.append([fields[i + 1], fields[i + 1], st[0]])
            i += 2
    # added/removed line counts ('-' for binary)
    num = git(repo, *(["diff", "-M", "--numstat", "-z"] + (["--cached"] if staged else [])
                      + [base] + ([target] if target else []))).stdout.decode().split("\0")
    counts, j = {}, 0
    while j < len(num) and num[j]:
        a, d, p = num[j].split("\t", 2)
        if p == "":                  # rename: the two paths are the next fields
            p = num[j + 2]
            j += 3
        else:
            j += 1
        counts[p] = (a, d)
    for c in out:
        c += list(counts.get(c[1], ("?", "?")))
    if include_untracked and not staged and not target:
        for p in git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout.decode().split("\0"):
            if p:
                data = read_side(repo, None, p)
                binary = data is not None and b"\0" in data[:8000]
                out.append([p, p, "A", "-" if binary else str(len(as_lines(data))), "-" if binary else "0"])
    return out


def table(old, new, labels, context):
    t = difflib.HtmlDiff(tabsize=4).make_table(old, new, labels[0], labels[1], context=True, numlines=context)
    t = re.sub(r'<td class="diff_next"[^>]*>.*?</td>', "", t)      # next-change link cells
    t = re.sub(r'<th class="diff_next">.*?</th>', "", t)
    t = re.sub(r"(<colgroup></colgroup>\s*)+",
               '<col class="ln"><col class="code"><col class="ln"><col class="code">', t)
    return t


CSS = """
:root { color-scheme: light dark; --bg:#fff; --fg:#111; --muted:#777; --rule:#ddd; --head:#f0f0f0;
  --add:#d8f5d8; --chg:#fff0a8; --sub:#fadcdc; --ln:#999; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#16181b; --fg:#e6e6e6;
  --muted:#999; --rule:#383b40; --head:#24272b; --add:#1d3d22; --chg:#4a4216; --sub:#4a2224; --ln:#777; } }
body { background:var(--bg); color:var(--fg); font:14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin:16px; }
h1 { font-size:20px; } h2 { font-size:15px; margin:28px 0 6px; } h2 small { color:var(--muted); font-weight:400; }
p.note { color:var(--muted); max-width:110ch; }
ul.toc { columns:3 240px; padding-left:18px; } ul.toc small { color:var(--muted); }
a { color:inherit; }
table.diff { width:100%; table-layout:fixed; border-collapse:collapse; margin-bottom:24px;
  font:12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; border:1px solid var(--rule); }
table.diff col.ln { width:3.6em; }
table.diff th { background:var(--head); text-align:left; padding:4px 6px; font:600 12px -apple-system, sans-serif; }
table.diff td { padding:0 6px; vertical-align:top; white-space:pre-wrap; overflow-wrap:anywhere; }
table.diff td.diff_header { color:var(--ln); text-align:right; padding-right:8px; border-right:1px solid var(--rule);
  user-select:none; }
table.diff tbody + tbody { border-top:2px dashed var(--rule); }
.diff_add { background:var(--add); } .diff_chg { background:var(--chg); } .diff_sub { background:var(--sub); }
"""


def main():
    # --help prints the whole docstring: the options below have no help= text of their own
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--repo", default=".")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--target")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--include-untracked", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--context", type=int, default=4)
    ap.add_argument("--title", default="Code changes for review")
    ap.add_argument("--strip-prefix", default="")
    a = ap.parse_args()
    repo = git(a.repo, "rev-parse", "--show-toplevel").stdout.decode().strip()

    after_spec = a.target if a.target else (":" if a.staged else None)
    after_name = a.target or ("staged (index)" if a.staged else "working tree")
    base_desc = git(repo, "rev-parse", "--short", a.base).stdout.decode().strip()
    base_name = a.base if a.base == base_desc else f"{a.base} ({base_desc})"

    rows = [c for c in changes(repo, a.base, a.target, a.staged, a.include_untracked)
            if not any(fnmatch.fnmatch(c[1], pat) or fnmatch.fnmatch(c[0], pat) for pat in a.exclude)]
    if not rows:
        sys.exit("no changes to show")

    shown = lambda p: p[len(a.strip_prefix):] if a.strip_prefix and p.startswith(a.strip_prefix) else p  # noqa: E731
    word = {"A": "added", "D": "deleted", "M": "modified", "R": "renamed", "C": "copied", "T": "type changed"}
    parts, toc, skipped = [], [], []
    tot_add = tot_del = 0
    for k, (old_p, new_p, st, add, rem) in enumerate(rows):
        old = read_side(repo, a.base, old_p) if st != "A" else None
        new = read_side(repo, after_spec, new_p) if st != "D" else None
        if any(x is not None and b"\0" in x[:8000] for x in (old, new)):
            skipped.append(shown(new_p))
            continue
        tot_add += int(add) if add.isdigit() else 0
        tot_del += int(rem) if rem.isdigit() else 0
        name = shown(new_p) if old_p == new_p else f"{shown(old_p)} → {shown(new_p)}"
        stat = f"{word.get(st, st)}, +{add} −{rem}"
        anchor = f"f{k}"
        parts.append(f'<h2 id="{anchor}">{html.escape(name)} <small>{html.escape(stat)}</small></h2>'
                     + table(as_lines(old), as_lines(new), (html.escape(base_name), html.escape(after_name)),
                             a.context))
        toc.append(f'<li><a href="#{anchor}">{html.escape(name)}</a> <small>+{add} −{rem}</small></li>')
    skip_note = (f"<p class='note'>Binary files not shown: {html.escape(', '.join(skipped))}.</p>"
                 if skipped else "")
    # joined outside the f-string: before Python 3.12 an f-string expression
    # may not reuse the string's own quote character
    toc_html, parts_html = "".join(toc), "".join(parts)
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Code Diff Review</title><style>{CSS}</style></head><body>
<h1>{html.escape(a.title)}</h1>
<p class="note">Before = {html.escape(base_name)}. After = {html.escape(after_name)}.
{len(parts)} files, +{tot_add} −{tot_del} lines. Changed lines with {a.context} lines of context; dashed rules
separate distant changes in a file; new files show as all added. Green: added, red: removed, yellow: changed
within a line.</p>{skip_note}
<ul class="toc">{toc_html}</ul>
{parts_html}
</body></html>"""
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"{len(parts)} files (+{tot_add} -{tot_del}) -> {a.out}"
          + (f"; {len(skipped)} binary skipped" if skipped else ""))


if __name__ == "__main__":
    main()
