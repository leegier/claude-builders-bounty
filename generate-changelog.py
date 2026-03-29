#!/usr/bin/env python3
"""
generate-changelog.py â€” Generate a structured CHANGELOG from git history.

Usage:
    python generate-changelog.py                     # from current dir
    python generate-changelog.py --repo /path/to/repo
    python generate-changelog.py --from v1.0 --to v2.0
    python generate-changelog.py --output CHANGELOG.md

Categories (auto-detected from conventional commits):
    feat:     âœ¨ Features
    fix:      ðŸ› Bug Fixes
    perf:     âš¡ Performance
    refactor: â™»ï¸ Refactoring
    docs:     ðŸ“ Documentation
    test:     ðŸ§ª Tests
    chore:    ðŸ”§ Chores
    ci:       ðŸ¤– CI/CD
    (other):  ðŸ“¦ Other Changes
"""

import argparse
import subprocess
import re
import sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path


CATEGORIES = {
    "feat":     ("âœ¨", "Features"),
    "fix":      ("ðŸ›", "Bug Fixes"),
    "perf":     ("âš¡", "Performance"),
    "refactor": ("â™»ï¸",  "Refactoring"),
    "docs":     ("ðŸ“", "Documentation"),
    "test":     ("ðŸ§ª", "Tests"),
    "chore":    ("ðŸ”§", "Chores"),
    "ci":       ("ðŸ¤–", "CI/CD"),
    "build":    ("ðŸ—ï¸",  "Build System"),
    "style":    ("ðŸ’„", "Style"),
    "revert":   ("âª", "Reverts"),
}

BREAKING_MARKER = "BREAKING CHANGE"


def run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=cwd
    )
    if result.returncode != 0:
        print(f"git error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def parse_commit(line: str) -> dict | None:
    """Parse a git log line: 'HASH DATE SUBJECT BODY'"""
    # Format: hash<SEP>date<SEP>subject<SEP>body
    parts = line.split("\x1f")
    if len(parts) < 3:
        return None

    sha, date_str, subject = parts[0], parts[1], parts[2]
    body = parts[3] if len(parts) > 3 else ""

    # Parse conventional commit: type(scope): description
    m = re.match(r'^(\w+)(\(([^)]+)\))?(!)?:\s*(.+)$', subject)
    if m:
        commit_type = m.group(1).lower()
        scope = m.group(3) or ""
        breaking = bool(m.group(4)) or BREAKING_MARKER in body
        description = m.group(5)
    else:
        commit_type = "other"
        scope = ""
        breaking = BREAKING_MARKER in body
        description = subject

    # Try to extract issue refs
    issues = re.findall(r'#(\d+)', subject + " " + body)

    return {
        "sha": sha[:8],
        "date": date_str,
        "type": commit_type,
        "scope": scope,
        "breaking": breaking,
        "description": description,
        "issues": issues,
        "raw": subject,
    }


def get_commits(repo: str, from_ref: str | None, to_ref: str | None) -> list[dict]:
    fmt = "%H\x1f%cs\x1f%s\x1f%b"  # hash, date, subject, body
    range_arg = ""
    if from_ref and to_ref:
        range_arg = f"{from_ref}..{to_ref}"
    elif from_ref:
        range_arg = f"{from_ref}..HEAD"
    elif to_ref:
        range_arg = to_ref

    cmd = ["log", "--pretty=format:" + fmt]
    if range_arg:
        cmd.append(range_arg)

    output = run_git(cmd, repo)
    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        c = parse_commit(line)
        if c:
            commits.append(c)
    return commits


def get_version_tags(repo: str) -> list[tuple[str, str]]:
    """Return [(tag, date), ...] sorted newest first."""
    output = run_git(["tag", "--sort=-version:refname", "--format=%(refname:short)\x1f%(creatordate:short)"], repo)
    tags = []
    for line in output.split("\n"):
        if "\x1f" in line:
            tag, date = line.split("\x1f", 1)
            tags.append((tag, date))
    return tags


def format_entry(commit: dict) -> str:
    scope_str = f"**{commit['scope']}**: " if commit['scope'] else ""
    breaking_str = "**âš  BREAKING CHANGE** â€” " if commit['breaking'] else ""
    issue_str = ""
    if commit['issues']:
        issue_str = " (" + ", ".join(f"#{i}" for i in commit['issues']) + ")"
    return f"- {breaking_str}{scope_str}{commit['description']}{issue_str} ([`{commit['sha']}`])"


def generate_changelog(
    repo: str,
    from_ref: str | None,
    to_ref: str | None,
    version: str,
) -> str:
    commits = get_commits(repo, from_ref, to_ref)
    if not commits:
        return f"## {version} â€” No changes found\n"

    # Group by category
    grouped = defaultdict(list)
    breaking = []

    for c in commits:
        if c['breaking']:
            breaking.append(c)
        cat = c['type'] if c['type'] in CATEGORIES else "other"
        grouped[cat].append(c)

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"## {version} ({today})\n"]

    if breaking:
        lines.append("### âš  Breaking Changes\n")
        for c in breaking:
            lines.append(format_entry(c))
        lines.append("")

    # Emit in defined order
    order = list(CATEGORIES.keys()) + ["other"]
    for cat in order:
        if cat not in grouped:
            continue
        emoji, label = CATEGORIES.get(cat, ("ðŸ“¦", "Other Changes"))
        lines.append(f"\n### {emoji} {label}\n")
        for c in grouped[cat]:
            lines.append(format_entry(c))

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate CHANGELOG from git history")
    parser.add_argument("--repo",    default=".", help="Path to git repo (default: .)")
    parser.add_argument("--from",    dest="from_ref", default=None, help="Start ref/tag (exclusive)")
    parser.add_argument("--to",      dest="to_ref",   default=None, help="End ref/tag (inclusive, default HEAD)")
    parser.add_argument("--version", default="Unreleased", help="Version label for this section")
    parser.add_argument("--output",  default=None, help="Output file (default: print to stdout)")
    parser.add_argument("--full",    action="store_true", help="Generate full CHANGELOG across all tags")
    args = parser.parse_args()

    repo = str(Path(args.repo).resolve())

    if args.full:
        # Generate one section per tag range
        tags = get_version_tags(repo)
        sections = []
        if tags:
            # Unreleased: latest tag â†’ HEAD
            unreleased = generate_changelog(repo, tags[0][0], None, "Unreleased")
            if "No changes found" not in unreleased:
                sections.append(unreleased)
            # Each tag range
            for i in range(len(tags) - 1):
                newer, older = tags[i], tags[i + 1]
                section = generate_changelog(repo, older[0], newer[0], newer[0])
                sections.append(section)
            # First tag
            first = generate_changelog(repo, None, tags[-1][0], tags[-1][0])
            sections.append(first)
        else:
            sections.append(generate_changelog(repo, None, None, "v0.1.0"))

        header = "# CHANGELOG\n\nAll notable changes to this project.\n\n"
        content = header + "\n---\n\n".join(sections)
    else:
        content = generate_changelog(repo, args.from_ref, args.to_ref, args.version)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"âœ“ Written to {args.output}")
    else:
        print(content)


if __name__ == "__main__":
    main()
