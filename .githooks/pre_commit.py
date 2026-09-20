#!/usr/bin/env python3
"""ADR-001 enforcement on the Git index, never on unstaged source files.

Git for Windows runs the extensionless launcher using its bundled sh. The bat
launcher is provided for direct cmd use; all policy and execution live in Python.
"""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ERRORS = {1: "ERR_MOCK_IN_IO", 2: "ERR_UNVERIFIED_ASSUMPTION",
          3: "ERR_TEST_EXECUTION_FAILED", 4: "ERR_DOCS_STALE"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=30)


def fail(code, message):
    print(f"{ERRORS[code]}: {message}. Read docs/ADR-001-AI-TESTING.md", file=sys.stderr)
    return code


def audit_io(root, rules):
    """Conservative whole-file token audit, including comments and manifests.

    Cross-language regex handles whitespace around member accesses and accepts
    aliases only after the import itself has passed inspection. This deliberately
    does not claim semantic AST coverage for every language or generated code.
    """
    tokens = rules["rules"][0]["forbidden_imports"]
    patterns = [re.compile(re.escape(token).replace(r"\.", r"\s*\.\s*").replace(r"\ ", r"\s+"), re.I)
                for token in tokens]
    for prefix in rules["io_roots"]:
        for path in sorted((root / prefix).rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Symlink disallowed at I/O boundary: {path}")
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                for token, pattern in zip(tokens, patterns):
                    if pattern.search(content):
                        return f"{path.relative_to(root).as_posix()}: banned token {token}"
    return None


def requires_docs(path):
    return (path.startswith(("src/", "go/", "packages/", "scripts/", "spikes/", ".githooks/", "tests/", ".github/workflows/"))
            and not path.endswith(".md")) or path in {
                "Cargo.toml", "Cargo.lock", "go.work", "go.work.sum", "package.json",
                "pnpm-workspace.yaml", "docker-compose.yml", "scaffold.py"}


def requires_live(paths):
    manifests = {"Cargo.toml", "Cargo.lock", "go.work", "go.work.sum", "package.json",
                 "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "docker-compose.yml", "scaffold.py"}
    return any(path.startswith(("src/io/", "go/io/", "spikes/", ".githooks/", "scripts/", "tests/", ".github/workflows/"))
               or Path(path).name in manifests or path.endswith(("go.mod", "go.sum")) for path in paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="CI: compare this ancestor with checked-out HEAD")
    args = parser.parse_args()
    if args.base:
        git("rev-parse", "--verify", args.base + "^{commit}")
        if git("diff", "--cached", "--name-only"):
            return fail(3, "CI --base requires the index to match HEAD")
        diff_args = [args.base, "HEAD"]
    else:
        diff_args = ["--cached"]
    changed = git("diff", *diff_args, "--name-only", "--no-renames", "-z").decode("utf-8").split("\0")
    changed = [path for path in changed if path]
    if not changed:
        print("ADR-001: no staged changes")
        return 0
    surviving = git("diff", *diff_args, "--name-only", "--diff-filter=AM", "--no-renames", "-z").decode("utf-8").split("\0")
    tree_before = git("write-tree")
    with tempfile.TemporaryDirectory(prefix="yaja-index-") as temporary:
        snapshot = Path(temporary)
        git("checkout-index", "--all", "--force", "--prefix=" + snapshot.as_posix() + "/")
        # Reject symlinks/gitlinks in executable input, including Windows exports
        # where symlinks may otherwise look like ordinary text files.
        for entry in git("ls-files", "--stage", "-z").split(b"\0"):
            if entry and entry.split(b" ", 1)[0] not in (b"100644", b"100755"):
                return fail(3, "Symlinks and submodules are unsupported in the verified snapshot")
        rules = json.loads((snapshot / ".githooks/ai_enforcer.json").read_text(encoding="utf-8"))
        violation = audit_io(snapshot, rules)
        if violation:
            return fail(1, violation)
        live = requires_live(changed)
        # Run the actual staged spike, rather than trusting an old marker file.
        if live:
            spike = snapshot / "spikes/active_spike.py"
            if not spike.is_file():
                return fail(2, "Missing staged spikes/active_spike.py")
            try:
                subprocess.run([sys.executable, str(spike)], cwd=snapshot, check=True, timeout=30)
            except (OSError, subprocess.SubprocessError) as error:
                return fail(2, f"Fresh physical spike failed: {error}")
        if any(requires_docs(path) for path in changed) and not any(path.endswith(".md") for path in surviving):
            return fail(4, "Stage a relevant Markdown update alongside code")
        if any(requires_docs(path) for path in changed):
            command = [sys.executable, str(snapshot / "scripts/verify.py")]
            if not live:
                command.append("--pure")
            # Build cache is outside the snapshot; source still comes only from index.
            environment = os.environ.copy()
            environment["CARGO_TARGET_DIR"] = str(ROOT / "target")
            try:
                subprocess.run(command, cwd=snapshot, env=environment, check=True, timeout=600)
            except (OSError, subprocess.SubprocessError) as error:
                return fail(3, f"Staged verification failed: {error}")
        if git("write-tree") != tree_before:
            return fail(3, "Git index changed during verification; retry")
    print("ADR-001: staged snapshot verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        sys.exit(fail(3, str(error)))
