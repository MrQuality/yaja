#!/usr/bin/env python3
"""Check current project naming; factual third-party references are allowed."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
# Split spellings so the checker can check its own source.
RETIRED = re.compile("|".join(re.escape(term) for term in (
    "Yet Another " + "Jira Alternative",
    "jql" + "_core",
    "Compiled" + "JqlArtifact",
    "yaja" + "-jql",
)), re.IGNORECASE)


def check_paths(root, paths):
    errors = []
    for name in sorted(paths):
        if RETIRED.search(name):
            errors.append(f"{name}: retired identifier in path")
        data = (root / name).read_bytes()
        if b"\x00" in data:
            continue
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line, text in enumerate(content.splitlines(), 1):
            if RETIRED.search(text):
                errors.append(f"{name}:{line}: retired project naming")
    return errors


def main():
    # Explicit source roots also work in the commit hook's Git-free snapshot.
    files = [path for path in ROOT.iterdir() if path.is_file() and not path.name.startswith(".")]
    for directory in ("src", "packages", "go", "docs", "scripts", "tests", ".github"):
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    paths = [path.relative_to(ROOT).as_posix() for path in files]
    # Only the checker's regression fixtures intentionally contain retired names.
    paths = [name for name in paths if name != "tests/test_branding.py"]
    errors = check_paths(ROOT, paths)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Current project naming verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
