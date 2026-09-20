"""Real temporary Git repositories verify staged enforcement and hook dispatch.

The fixture's pure Python assertion is genuinely executed, including failures.
No physical service is faked; the missing-spike case fails before network access.
Synthetic base history is assembled with Git plumbing solely as test input.
"""
from pathlib import Path
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GitGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="yaja-gate-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = os.environ.copy()
        # Hook-inherited Git variables must not redirect commands to the parent repo.
        for key in list(self.environment):
            if key.startswith("GIT_"):
                self.environment.pop(key)
        self.environment.update({"GIT_AUTHOR_NAME": "Policy Test", "GIT_COMMITTER_NAME": "Policy Test",
                                 "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_EMAIL": "test@example.invalid"})
        self.git("init", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        for relative in (".githooks/pre_commit.py", ".githooks/pre-commit", ".githooks/ai_enforcer.json"):
            self.write(relative, (ROOT / relative).read_text(encoding="utf-8"))
        hook = self.root / ".githooks/pre-commit"
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        self.write("src/pure/value.py", "assert 2 + 2 == 4\n")
        self.write("docs/spec.md", "# Fixture contract\n\nArithmetic is pure.\n")
        self.write("scripts/verify.py", "import subprocess, sys\nsubprocess.run([sys.executable, 'src/pure/value.py'], check=True)\n")
        self.git("add", "--all")
        self.git("update-index", "--chmod=+x", ".githooks/pre-commit")
        tree = self.git("write-tree").stdout.strip()
        commit = self.git("commit-tree", tree, "-m", "Synthetic test fixture").stdout.strip()
        self.git("update-ref", "refs/heads/main", commit)
        self.git("config", "core.hooksPath", ".githooks")

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.root, env=self.environment,
                              check=check, capture_output=True, text=True, timeout=30)

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def stage_docs(self):
        self.write("docs/spec.md", "# Fixture contract\n\nUpdated arithmetic acceptance criterion.\n")
        self.git("add", "docs/spec.md")

    def hook(self):
        return subprocess.run([sys.executable, ".githooks/pre_commit.py"], cwd=self.root,
                              env=self.environment, capture_output=True, text=True, timeout=60)

    def test_mock_in_staged_io_rejected_despite_unstaged_cleanup(self):
        self.write("src/io/adapter.rs", "use mockall::automock;\n")
        self.git("add", "src/io/adapter.rs")
        self.write("src/io/adapter.rs", "// clean worktree cannot hide staged violation\n")
        result = self.hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("ERR_MOCK_IN_IO", result.stderr)

    def test_missing_spike_is_exit_two(self):
        self.write("src/io/adapter.rs", "// physical adapter contract\n")
        self.git("add", "src/io/adapter.rs")
        result = self.hook()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("ERR_UNVERIFIED_ASSUMPTION", result.stderr)

    def test_failing_staged_code_cannot_be_repaired_by_unstaged_code(self):
        self.write("src/pure/value.py", "assert 2 + 2 == 5\n")
        self.git("add", "src/pure/value.py")
        self.write("src/pure/value.py", "assert 2 + 2 == 4\n")
        self.stage_docs()
        result = self.hook()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("ERR_TEST_EXECUTION_FAILED", result.stderr)

    def test_unstaged_documentation_is_not_enough(self):
        self.write("src/pure/value.py", "assert 3 + 3 == 6\n")
        self.git("add", "src/pure/value.py")
        self.write("docs/spec.md", "# Unstaged update\n")
        result = self.hook()
        self.assertEqual(result.returncode, 4, result.stderr)

    def test_deleted_documentation_is_not_enough(self):
        self.write("src/pure/value.py", "assert 3 + 3 == 6\n")
        self.git("add", "src/pure/value.py")
        self.git("rm", "docs/spec.md")
        self.assertEqual(self.hook().returncode, 4)

    def test_real_git_commit_runs_the_launcher_and_blocks_failure(self):
        previous = self.git("rev-parse", "HEAD").stdout
        self.write("src/pure/value.py", "assert False\n")
        self.git("add", "src/pure/value.py")
        self.stage_docs()
        result = self.git("commit", "-m", "Must be rejected", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERR_TEST_EXECUTION_FAILED", result.stderr)
        self.assertEqual(previous, self.git("rev-parse", "HEAD").stdout)

    def test_valid_pure_change_and_docs_commit_successfully(self):
        self.write("src/pure/value.py", "# mockall is allowed in pure code\nassert 3 + 3 == 6\n")
        self.git("add", "src/pure/value.py")
        self.stage_docs()
        result = self.git("commit", "-m", "Verified fixture", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main()
