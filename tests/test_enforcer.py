"""Pure policy tests; these do not replace the required physical I/O checks."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("enforcer", ROOT / ".githooks/pre_commit.py")
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)
RULES = json.loads((ROOT / ".githooks/ai_enforcer.json").read_text(encoding="utf-8"))


class PolicyTests(unittest.TestCase):
    def test_every_required_token_is_blocked(self):
        for token in ("mockall", "jest.mock", "httptest", "sqlmock", "testify/mock", "jest . mock"):
            with self.subTest(token=token), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "src/io/adapter/test.rs"
                source.parent.mkdir(parents=True)
                source.write_text(token, encoding="utf-8")
                self.assertIsNotNone(POLICY.audit_io(root, RULES))

    def test_pure_mocks_are_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "src/pure/parser/test.rs"
            source.parent.mkdir(parents=True)
            source.write_text("mockall", encoding="utf-8")
            self.assertIsNone(POLICY.audit_io(root, RULES))

    def test_live_scope_includes_dependencies_and_verifiers(self):
        for path in ("src/io/x/src/lib.rs", "Cargo.lock", "go/pure/x/go.mod",
                     "packages/x/package.json", "scripts/verify.py", ".githooks/pre_commit.py"):
            self.assertTrue(POLICY.requires_live([path]), path)
        self.assertFalse(POLICY.requires_live(["src/pure/jql_core/src/lib.rs", "README.md"]))

    def test_documentation_requirement(self):
        self.assertTrue(POLICY.requires_docs("src/pure/jql_core/src/lib.rs"))
        self.assertTrue(POLICY.requires_docs("docker-compose.yml"))
        self.assertFalse(POLICY.requires_docs("docs/ADR-001-AI-TESTING.md"))


if __name__ == "__main__":
    unittest.main()
