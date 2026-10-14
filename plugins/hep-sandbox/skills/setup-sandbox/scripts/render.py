#!/usr/bin/env python3
"""Render the HEP dev container configuration from the template and an answers file.

Usage:
    python3 render.py --answers answers.json [--out DIR] [--dry-run] [--force]

The answers file is JSON (see answers.example.json next to this script). By default the
output goes to <hep_dir>/infrastructure/hep-devcontainer. Existing files are never replaced
silently: a differing file is shown as a diff and only overwritten with --force. Nothing in
the output directory is ever deleted.

Standard library only, Python 3.9+ (the python3 that ships with macOS's Xcode tools).
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "template"
PRESETS = ("none", "fermilab-kerberos-host-only", "ssh-key-hpc")
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)\}\}")
# Characters that would break Docker's comma-separated --mount syntax or the JSON strings.
UNSAFE_PATH_CHARS = re.compile(r'[,"\\]')


def fail(message):
    sys.exit(f"render.py: error: {message}")


def detect_timezone():
    """macOS stores the zone as a symlink, e.g. /etc/localtime -> .../zoneinfo/America/Chicago."""
    try:
        target = os.readlink("/etc/localtime")
    except OSError:
        return "UTC"
    return target.split("zoneinfo/", 1)[1] if "zoneinfo/" in target else "UTC"


def load_answers(path):
    try:
        answers = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as err:
        fail(f"cannot read answers file {path}: {err}")

    home = Path.home()
    hep_dir = Path(os.path.expanduser(answers.get("hep_dir", "~/hep"))).resolve()
    if home not in hep_dir.parents:
        fail(f"hep_dir must be inside your home folder ({home}), got {hep_dir}")
    if not hep_dir.is_dir():
        fail(f"hep_dir {hep_dir} does not exist; create it first")
    answers["hep_dir"] = hep_dir
    answers["hep_rel"] = str(hep_dir.relative_to(home))

    answers.setdefault("timezone", detect_timezone())
    answers.setdefault("container_name", "hep-dev")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", answers["container_name"]):
        fail(f"container_name {answers['container_name']!r} is not a valid Docker name")

    readonly = [d.strip("/") for d in answers.get("readonly_dirs", [])]
    for d in readonly:
        if UNSAFE_PATH_CHARS.search(d) or d.startswith(".") or ".." in Path(d).parts:
            fail(f"readonly_dirs entry {d!r} must be a plain path inside hep_dir")
        if d == "infrastructure":
            fail("'infrastructure' is always read-only; don't list it in readonly_dirs")
        # Docker refuses to start a container whose bind-mount source is missing.
        if not (hep_dir / d).is_dir():
            fail(f"readonly_dirs entry {d!r} does not exist under {hep_dir}")
    answers["readonly_dirs"] = readonly

    preset = answers.get("remote_access", "none")
    if preset not in PRESETS:
        fail(f"remote_access must be one of {', '.join(PRESETS)}, got {preset!r}")
    answers["remote_access"] = preset
    hosts = answers.get("hpc_hosts", [])
    if preset == "ssh-key-hpc" and not hosts:
        fail("remote_access 'ssh-key-hpc' needs at least one entry in hpc_hosts")
    for h in hosts:
        if not all(h.get(k) for k in ("alias", "hostname", "user")):
            fail(f"each hpc_hosts entry needs alias, hostname and user: {h}")
    answers["hpc_hosts"] = hosts if preset == "ssh-key-hpc" else []
    return answers


def read_preset(template_dir, name):
    """Split a preset file into its policy / ssh_config / quickstart parts."""
    text = (template_dir / "_presets" / f"{name}.md").read_text()
    parts = {}
    for key in ("policy", "ssh_config", "quickstart"):
        match = re.search(rf"<!-- {key} -->\n(.*?)(?=\n<!-- [a-z_]+ -->|\Z)", text, re.S)
        if not match:
            fail(f"preset {name} has no '{key}' section")
        parts[key] = match.group(1).rstrip("\n")
    return parts


def known_hosts_lines(hostname):
    """Public host keys for a host, from the user's ~/.ssh/known_hosts (never private keys)."""
    known = Path.home() / ".ssh" / "known_hosts"
    result = subprocess.run(["ssh-keygen", "-F", hostname, "-f", str(known)],
                            capture_output=True, text=True)
    lines = [l for l in result.stdout.splitlines() if l and not l.startswith("#")]
    if not lines:
        fail(f"no host key for {hostname} in {known}. Connect once from a Mac terminal "
             f"(ssh {hostname}), check the fingerprint with the site's documentation, then rerun.")
    return lines


def build_values(answers, template_dir):
    rel = answers["hep_rel"]
    readonly = answers["readonly_dirs"]
    preset = read_preset(template_dir, answers["remote_access"])

    mounts = [f'        "source=${{localEnv:HOME}}/{rel}/infrastructure,'
              f'target=/workspace/hep/infrastructure,type=bind,readonly",']
    mounts += [f'        "source=${{localEnv:HOME}}/{rel}/{d},target=/workspace/hep/{d},type=bind,readonly",'
               for d in readonly]
    # Watcher/search excludes: the read-only data folders plus any extra large trees (e.g. a
    # Geant4 source checkout). JSON forbids a trailing comma, so *.root goes last without one.
    extra_excludes = [x.strip("/") for x in answers.get("extra_watch_excludes", [])]
    for x in extra_excludes:
        if UNSAFE_PATH_CHARS.search(x):
            fail(f"extra_watch_excludes entry {x!r} contains an unsupported character")
    excludes = [f'                    "**/{d}/**": true,' for d in readonly + extra_excludes]
    excludes.append('                    "**/*.root": true')

    hosts = answers["hpc_hosts"]
    host_blocks = "".join(f"\nHost {h['alias']}\n    HostName {h['hostname']}\n    User {h['user']}\n"
                          for h in hosts)
    personal = []
    if answers.get("user_blurb"):
        personal.append(f"- {answers['user_blurb']}")
    if answers.get("author_email"):
        personal.append(f"- When an author email is needed (papers, notes, code headers), use "
                        f"{answers['author_email']}.")
    personal += [f"- {p}" for p in answers.get("extra_preferences", [])]

    return {
        "hep_rel": rel,
        "hep_dir_display": f"~/{rel}",
        "timezone": answers["timezone"],
        "container_name": answers["container_name"],
        "readonly_mounts": "\n".join(mounts),
        "watch_excludes": "\n".join(excludes),
        "readonly_dirs_policy": "\n".join(f"- `/workspace/hep/{d}/`" for d in readonly),
        "readonly_dirs_inline": ", ".join(["`infrastructure/`"] + [f"`{d}/`" for d in readonly]),
        "remote_access_policy": preset["policy"],
        "ssh_preset_comment": preset["ssh_config"],
        "remote_quickstart_row": preset["quickstart"],
        "ssh_hpc_hosts": host_blocks,
        "hpc_hosts_list": ", ".join(f"`{h['alias']}` ({h['user']}@{h['hostname']})" for h in hosts),
        "personal_section": ("\n## About the user\n\n" + "\n".join(personal) + "\n") if personal else "",
    }


def substitute(text, values, source):
    # Two passes: preset text may itself contain placeholders (e.g. {{hpc_hosts_list}}).
    for _ in range(2):
        text = PLACEHOLDER.sub(lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), text)
    leftover = PLACEHOLDER.findall(text)
    if leftover:
        fail(f"{source}: unknown placeholder(s) {sorted(set(leftover))}")
    return text


def render(answers, template_dir):
    values = build_values(answers, template_dir)
    outputs = {}
    for src in sorted(template_dir.rglob("*")):
        rel = src.relative_to(template_dir)
        if src.is_dir() or any(part.startswith("_") for part in rel.parts):
            continue  # _presets/ etc. are inputs, not outputs
        outputs[rel] = (substitute(src.read_text(), values, rel), os.access(src, os.X_OK))
    # Host keys for any ssh-key-hpc hosts go into the container's known_hosts.
    extra = [line for h in answers["hpc_hosts"] for line in known_hosts_lines(h["hostname"])]
    if extra:
        known = Path("setup/known_hosts")
        text, mode = outputs[known]
        outputs[known] = (text + "# Remote hosts (copied from ~/.ssh/known_hosts by render.py)\n"
                          + "\n".join(extra) + "\n", mode)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--answers", required=True, help="answers JSON file")
    parser.add_argument("--out", help="output directory (default: <hep_dir>/infrastructure/hep-devcontainer)")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="template directory")
    parser.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    parser.add_argument("--force", action="store_true", help="overwrite files that differ")
    args = parser.parse_args()

    answers = load_answers(args.answers)
    out_dir = Path(args.out).expanduser() if args.out else answers["hep_dir"] / "infrastructure/hep-devcontainer"
    outputs = render(answers, Path(args.template))

    blocked = 0
    for rel, (text, executable) in outputs.items():
        dst = out_dir / rel
        if dst.exists():
            old = dst.read_text()
            if old == text:
                print(f"unchanged  {rel}")
                continue
            diff = difflib.unified_diff(old.splitlines(True), text.splitlines(True),
                                        f"current/{rel}", f"rendered/{rel}")
            sys.stdout.writelines(diff)
            if not args.force or args.dry_run:
                print(f"DIFFERS    {rel}  (not written; use --force to replace)")
                blocked += 1
                continue
            action = "replaced "
        else:
            action = "would add" if args.dry_run else "added    "
            if args.dry_run:
                print(f"{action}  {rel}")
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)
        if executable:
            dst.chmod(dst.stat().st_mode | 0o111)
        print(f"{action}  {rel}")

    print(f"\noutput: {out_dir}")
    sys.exit(2 if blocked else 0)


if __name__ == "__main__":
    main()
