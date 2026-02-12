#!/usr/bin/env python3
"""
NEXUS Version Bump Tool

Usage:
    python scripts/bump_version.py patch   # 0.1.0 → 0.1.1
    python scripts/bump_version.py minor   # 0.1.1 → 0.2.0
    python scripts/bump_version.py major   # 0.2.0 → 1.0.0
"""

import re
import sys
from pathlib import Path
from datetime import date


ROOT = Path(__file__).parent.parent

PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def get_current_version() -> str:
    text = PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown part: {part}. Use: major, minor, patch")


def update_pyproject(old: str, new: str):
    text = PYPROJECT.read_text()
    text = text.replace(f'version = "{old}"', f'version = "{new}"')
    PYPROJECT.write_text(text)
    print(f"  pyproject.toml: {old} → {new}")


def update_readme(old: str, new: str):
    text = README.read_text()
    text = text.replace(f"NEXUS-v{old}", f"NEXUS-v{new}")
    text = text.replace(f"v{old}", f"v{new}")
    README.write_text(text)
    print(f"  README.md: badges updated")


def update_changelog(new: str):
    text = CHANGELOG.read_text()
    today = date.today().isoformat()
    new_entry = f"\n## [{new}] - {today}\n\n### Changed\n\n- (describe changes here)\n\n---\n"

    # Insert after the header line "---" (first occurrence after title)
    lines = text.split("\n")
    insert_idx = None
    found_first_separator = False
    for i, line in enumerate(lines):
        if line.strip() == "---" and not found_first_separator:
            found_first_separator = True
            continue
        if found_first_separator and line.strip() == "":
            insert_idx = i + 1
            break

    if insert_idx:
        lines.insert(insert_idx, new_entry)
        CHANGELOG.write_text("\n".join(lines))
        print(f"  CHANGELOG.md: new entry [{new}] - {today}")
    else:
        print("  CHANGELOG.md: could not find insertion point, skip")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    part = sys.argv[1].lower()
    current = get_current_version()
    new = bump(current, part)

    print(f"\nNEXUS version bump: {current} → {new}\n")

    update_pyproject(current, new)
    update_readme(current, new)
    update_changelog(new)

    print(f"\nDone! Now edit CHANGELOG.md with the actual changes, then:")
    print(f"  git add pyproject.toml README.md CHANGELOG.md")
    print(f'  git commit -m "chore: bump version to {new}"')
    print(f"  git push origin main")


if __name__ == "__main__":
    main()
