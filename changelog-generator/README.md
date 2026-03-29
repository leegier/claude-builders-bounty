# CHANGELOG Generator

Auto-generates a structured, categorized CHANGELOG from git history using conventional commits.

## Features

- **Conventional commit parsing** â€” `feat:`, `fix:`, `perf:`, `refactor:`, `docs:`, `test:`, `chore:`, etc.
- **Scope support** â€” `feat(auth): add OAuth` â†’ grouped under scope `auth`
- **Breaking change detection** â€” `!` suffix or `BREAKING CHANGE` in body â†’ flagged prominently
- **Issue linking** â€” `#123` refs auto-extracted from commit messages
- **Full changelog mode** â€” scans all version tags and generates one section per tag range
- **Zero dependencies** â€” pure Python 3.11 stdlib only

## Usage

```bash
# Print unreleased changes since last tag
python generate-changelog.py

# Generate for specific range
python generate-changelog.py --from v1.0.0 --to v2.0.0 --version v2.0.0

# Write to file
python generate-changelog.py --output CHANGELOG.md

# Full changelog across all version tags
python generate-changelog.py --full --output CHANGELOG.md

# Different repo
python generate-changelog.py --repo /path/to/repo --full --output CHANGELOG.md
```

## Output Example

```markdown
## v2.0.0 (2026-03-28)

### âš  Breaking Changes

- **auth**: replace session tokens with JWTs â€” requires DB migration (#42) [`a1b2c3d4`]

### âœ¨ Features

- **payments**: add Stripe subscription billing (#38) [`e5f6g7h8`]
- add dark mode toggle (#35) [`i9j0k1l2`]

### ðŸ› Bug Fixes

- fix race condition in queue processor (#40) [`m3n4o5p6`]
```

## Install as Claude Code hook (optional)

Add to `.claude/settings.json` to auto-run on each session:

```json
{
  "hooks": {
    "PostSession": [
      {
        "type": "command",
        "command": "python generate-changelog.py --output CHANGELOG.md"
      }
    ]
  }
}
```

## Requirements

- Python 3.10+
- Git in PATH
- Conventional commit messages (recommended but not required â€” non-conventional commits go to "Other Changes")
