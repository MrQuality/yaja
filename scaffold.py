#!/usr/bin/env python3
"""Generate and verify the YAJA baseline using Python's standard library only.

Run from the intended repository root: python scaffold.py
Existing differing files are never overwritten. A failed verification never commits.
"""
from pathlib import Path
import os
import stat
import subprocess
import sys
import argparse

FILES = {}

FILES['.gitignore'] = r'''/target/
**/__pycache__/
*.py[cod]
node_modules/
.env
.env.*
!.env.example
*.log
.yaja/
'''
FILES['.gitattributes'] = r'''* text=auto eol=lf
*.bat text eol=crlf
'''
FILES['Cargo.toml'] = r'''[workspace]
members = ["src/pure/*", "src/io/*"]
resolver = "2"

[workspace.package]
version = "0.1.0"
edition = "2021"
rust-version = "1.75"
license = "Apache-2.0"

[workspace.lints.rust]
unsafe_code = "forbid"
'''
FILES['src/pure/jql_core/Cargo.toml'] = r'''[package]
name = "jql_core"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true

[lints]
workspace = true
'''
FILES['src/pure/jql_core/src/lib.rs'] = r'''//! Track A: a deliberately small, typed equality grammar, without I/O or regex.
//! Supported input: ASCII identifier = single-quoted nonempty value.
//! This is not yet the full isomorphic JQL/Rhai/Wasm compiler.

#[derive(Debug, PartialEq, Eq)]
pub struct Filter {
    pub field: String,
    pub value: String,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ParseError {
    MissingEquals,
    InvalidField,
    InvalidValue,
}

/// Parse the complete input; reject trailing clauses and ambiguous quoting.
pub fn parse_filter(input: &str) -> Result<Filter, ParseError> {
    let (field, value) = input.split_once('=').ok_or(ParseError::MissingEquals)?;
    let field = field.trim();
    let mut chars = field.chars();
    if !chars
        .next()
        .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        || !chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
    {
        return Err(ParseError::InvalidField);
    }
    let value = value.trim();
    let inner = value
        .strip_prefix('\'')
        .and_then(|s| s.strip_suffix('\''))
        .ok_or(ParseError::InvalidValue)?;
    if inner.is_empty()
        || inner
            .chars()
            .any(|c| c == '\'' || c == '\\' || c.is_control())
    {
        return Err(ParseError::InvalidValue);
    }
    Ok(Filter {
        field: field.to_owned(),
        value: inner.to_owned(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_complete_filter() {
        assert_eq!(
            parse_filter(" status = 'In Progress' "),
            Ok(Filter {
                field: "status".into(),
                value: "In Progress".into(),
            })
        );
    }

    #[test]
    fn rejects_invalid_or_unsupported_grammar() {
        for input in [
            "",
            "status",
            "1status = 'Open'",
            "status == 'Open'",
            "status = Open",
            "status = ''",
            "status = 'Open' OR project = 'X'",
            "status = 'Open' trailing",
            "status = 'a\\b'",
            "status = 'a\nb'",
        ] {
            assert!(parse_filter(input).is_err(), "accepted {input:?}");
        }
    }

    #[test]
    fn preserves_unicode_values_and_equals() {
        assert_eq!(parse_filter("_field = 'שלום=x'").unwrap().value, "שלום=x");
    }
}
'''
FILES['src/io/event_dispatcher/Cargo.toml'] = r'''[package]
name = "event_dispatcher"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true

[lints]
workspace = true
'''
FILES['src/io/event_dispatcher/src/lib.rs'] = r'''//! Track C: live NATS connection boundary. No substitute transports.
//! This bootstrap probe is not a production publisher or JetStream client SDK.
use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

pub struct JetStreamConnection {
    reader: BufReader<TcpStream>,
}

impl JetStreamConnection {
    /// Connect to a live server and complete the NATS INFO/CONNECT/PING exchange.
    pub fn connect(address: SocketAddr, timeout: Duration) -> io::Result<Self> {
        let stream = TcpStream::connect_timeout(&address, timeout)?;
        stream.set_read_timeout(Some(timeout))?;
        stream.set_write_timeout(Some(timeout))?;
        let mut connection = Self {
            reader: BufReader::new(stream),
        };
        if !connection.read_line()?.starts_with("INFO {") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "expected NATS INFO",
            ));
        }
        connection.reader.get_mut().write_all(
            b"CONNECT {\"verbose\":false,\"pedantic\":true,\"lang\":\"rust\",\"version\":\"0.1.0\"}\r\n",
        )?;
        connection.ping()?;
        Ok(connection)
    }

    fn read_line(&mut self) -> io::Result<String> {
        let mut bytes = Vec::new();
        self.reader
            .by_ref()
            .take(65537)
            .read_until(b'\n', &mut bytes)?;
        if bytes.len() > 65536 || !bytes.ends_with(b"\r\n") {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid NATS line",
            ));
        }
        String::from_utf8(bytes).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
    }

    /// Check a real broker round trip; fail on protocol errors or bounded timeout.
    pub fn ping(&mut self) -> io::Result<()> {
        self.reader.get_mut().write_all(b"PING\r\n")?;
        for _ in 0..32 {
            let line = self.read_line()?;
            match line.trim_end() {
                "PONG" => return Ok(()),
                "PING" => self.reader.get_mut().write_all(b"PONG\r\n")?,
                "+OK" => (),
                other if other.starts_with("INFO ") => (),
                _ => return Err(io::Error::new(io::ErrorKind::InvalidData, line)),
            }
        }
        Err(io::Error::new(
            io::ErrorKind::TimedOut,
            "no PONG after 32 frames",
        ))
    }
}
'''
FILES['src/io/event_dispatcher/tests/live_nats.rs'] = r'''//! Always runs against live infrastructure; unavailable infrastructure is a failure.
use event_dispatcher::JetStreamConnection;
use std::time::Duration;

#[test]
fn live_nats_handshake_and_second_round_trip() {
    let address = std::env::var("YAJA_NATS_ADDRESS").unwrap_or_else(|_| "127.0.0.1:4222".into());
    let mut connection = JetStreamConnection::connect(
        address
            .parse()
            .expect("YAJA_NATS_ADDRESS must be an IP:port"),
        Duration::from_secs(3),
    )
    .expect("live NATS required: python scripts/setup_env.py --start");
    connection
        .ping()
        .expect("second physical broker round trip");
}
'''
FILES['go.work'] = 'go 1.22.0\n\nuse ./go/pure/sync_contract\n'
FILES['go/pure/sync_contract/go.mod'] = 'module yaja.local/sync_contract\n\ngo 1.22.0\n'
FILES['go/pure/sync_contract/epoch.go'] = r'''// Package synccontract contains pure schema-epoch decisions, with no I/O.
package synccontract

// CanEvaluate permits provisional evaluation only at the exact current epoch.
func CanEvaluate(compiled, current uint64, pure bool) bool {
	return pure && compiled == current
}
'''
FILES['go/pure/sync_contract/epoch_test.go'] = r'''package synccontract

import "testing"

func TestCanEvaluate(t *testing.T) {
	for _, c := range []struct {
		compiled, current uint64
		pure, want        bool
	}{
		{1, 1, true, true}, {1, 2, true, false},
		{2, 1, true, false}, {1, 1, false, false},
	} {
		if got := CanEvaluate(c.compiled, c.current, c.pure); got != c.want {
			t.Fatalf("CanEvaluate(%d, %d, %v) = %v", c.compiled, c.current, c.pure, got)
		}
	}
}
'''
FILES['package.json'] = r'''{
  "name": "yaja", "version": "0.1.0", "private": true,
  "license": "Apache-2.0",
  "workspaces": ["packages/*"],
  "scripts": {"test": "python scripts/verify.py", "healthcheck": "python scripts/healthcheck.py"}
}
'''
FILES['pnpm-workspace.yaml'] = "packages:\n  - 'packages/*'\n"
FILES['packages/contracts/package.json'] = r'''{
  "name": "@yaja/contracts", "version": "0.1.0", "private": true,
  "license": "Apache-2.0", "types": "index.d.ts"
}
'''
FILES['packages/contracts/index.d.ts'] = r'''/** Provisional artifacts are valid only for their exact schema epoch. */
export interface CompiledJqlArtifact {
  epoch: number;
  is_pure: boolean;
  rhai_script: string;
}
export type SSEEvent =
  | { type: "SYNC_TOKEN"; payload: { actionId: string; esOffset: number } }
  | { type: "SCHEMA_ADVANCED"; payload: { projectId: string; newEpoch: number; diff: unknown[] } }
  | { type: "SAGA_PROGRESS"; payload: { sagaId: string; completed: number; total: number } };
'''
FILES['docker-compose.yml'] = r'''# Local disposable development infrastructure only. See SECURITY.md.
name: yaja
services:
  postgres:
    image: docker.io/library/postgres:16.13
    environment:
      POSTGRES_DB: yaja
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    command: ["postgres", "-c", "wal_level=logical", "-c", "max_replication_slots=10"]
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d yaja"]
      interval: 5s
      timeout: 3s
      retries: 30
  ferretdb:
    # 1.x supports stock Postgres; 2.x requires a different backend.
    image: ghcr.io/ferretdb/ferretdb:1.24.2
    environment:
      FERRETDB_POSTGRESQL_URL: postgres://postgres:postgres@postgres:5432/yaja
      FERRETDB_TELEMETRY: disabled
    ports: ["27017:27017"]
    depends_on:
      postgres:
        condition: service_healthy
  nats:
    image: docker.io/library/nats:2.10.26-alpine
    command: ["-js", "-m", "8222", "-sd", "/data/jetstream"]
    ports: ["4222:4222", "8222:8222"]
  opensearch:
    image: docker.io/opensearchproject/opensearch:2.19.1
    environment:
      discovery.type: single-node
      DISABLE_SECURITY_PLUGIN: "true"
      DISABLE_INSTALL_DEMO_CONFIG: "true"
      OPENSEARCH_JAVA_OPTS: -Xms512m -Xmx512m
    ports: ["9200:9200"]
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
'''
FILES['scripts/healthcheck.py'] = r'''#!/usr/bin/env python3
"""Probe all requested TCP ports; additionally verify OpenSearch HTTP readiness."""
import argparse
import json
import socket
import sys
import time
import urllib.request

PORTS = {"PostgreSQL": 5432, "FerretDB": 27017, "NATS": 4222, "OpenSearch": 9200}


def probe(host):
    errors = []
    for name, port in PORTS.items():
        try:
            with socket.create_connection((host, port), timeout=2):
                pass
        except OSError as error:
            errors.append(f"{name} {host}:{port}: {error}")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://{host}:9200/_cluster/health", timeout=3) as response:
            status = json.load(response)
        if status.get("status") not in ("yellow", "green"):
            errors.append(f"OpenSearch cluster not ready: {status.get('status')}")
    except (OSError, ValueError) as error:
        errors.append(f"OpenSearch HTTP: {error}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--wait", type=float, default=0, help="Readiness deadline in seconds")
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        errors = probe(args.host)
        if not errors:
            print(json.dumps({"ok": True, "tcp_ports": PORTS, "opensearch_http": "ready"}))
            return 0
        if time.monotonic() >= deadline:
            print(json.dumps({"ok": False, "errors": errors}), file=sys.stderr)
            return 1
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
'''
FILES['spikes/active_spike.py'] = r'''#!/usr/bin/env python3
"""Hypothesis: the local NATS server speaks NATS and exposes JetStream account info.

Observe INFO.jetstream, CONNECT/PING/PONG, then a real $JS.API.INFO response.
No saved success flag or mocked server can substitute for this execution.
"""
import json
import os
import socket
import sys


def probe():
    host = os.environ.get("YAJA_NATS_HOST", "127.0.0.1")
    port = int(os.environ.get("YAJA_NATS_PORT", "4222"))
    with socket.create_connection((host, port), timeout=3) as conn:
        conn.settimeout(3)
        with conn.makefile("rb") as reader:
            def line():
                value = reader.readline(65537)
                if len(value) > 65536 or not value.endswith(b"\r\n"):
                    raise ValueError("Invalid or oversized NATS frame")
                return value

            greeting = line()
            if not greeting.startswith(b"INFO "):
                raise ValueError("NATS INFO greeting missing")
            info = json.loads(greeting[5:])
            if info.get("jetstream") is not True:
                raise ValueError("JetStream is not enabled")
            conn.sendall(b'CONNECT {"verbose":false,"pedantic":true,"lang":"python","version":"0.1.0"}\r\nPING\r\n')
            for _ in range(32):
                frame = line()
                if frame == b"PONG\r\n":
                    break
                if frame == b"PING\r\n":
                    conn.sendall(b"PONG\r\n")
                elif not (frame.startswith(b"INFO ") or frame == b"+OK\r\n"):
                    raise ValueError(f"Unexpected handshake: {frame!r}")
            else:
                raise ValueError("No PONG received")
            inbox = ("_INBOX.yaja." + os.urandom(12).hex()).encode("ascii")
            conn.sendall(b"SUB " + inbox + b" 1\r\nUNSUB 1 1\r\nPUB $JS.API.INFO " + inbox + b" 0\r\n\r\n")
            for _ in range(32):
                frame = line()
                if frame.startswith(b"MSG "):
                    parts = frame.split()
                    if len(parts) != 4 or parts[1] != inbox or parts[2] != b"1":
                        raise ValueError("Unexpected JetStream response subject")
                    size = int(parts[-1])
                    if not 0 < size <= 65536:
                        raise ValueError("Invalid JetStream payload length")
                    payload = reader.read(size)
                    if len(payload) != size or reader.read(2) != b"\r\n":
                        raise ValueError("Truncated JetStream payload")
                    account = json.loads(payload)
                    if account.get("error") or account.get("type") != "io.nats.jetstream.api.v1.account_info_response":
                        raise ValueError(f"JetStream account check failed: {account}")
                    return {"ok": True, "server_id": info["server_id"],
                            "version": info["version"], "jetstream": True,
                            "response_type": account["type"]}
                if frame == b"PING\r\n":
                    conn.sendall(b"PONG\r\n")
                elif not (frame.startswith(b"INFO ") or frame == b"+OK\r\n"):
                    raise ValueError(f"Unexpected NATS response: {frame!r}")
            raise ValueError("No JetStream account response received")


if __name__ == "__main__":
    try:
        print(json.dumps(probe()))
    except (OSError, ValueError, KeyError) as error:
        print(f"ERR_UNVERIFIED_ASSUMPTION: {error}", file=sys.stderr)
        sys.exit(2)
'''
FILES['scripts/setup_env.py'] = r'''#!/usr/bin/env python3
"""Configure hooks, optionally start disposable infrastructure, and check readiness."""
from pathlib import Path
import argparse
import os
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, check=True, timeout=600, **kwargs)


def compose_command(preferred="auto"):
    for engine, compose in (("podman", ["podman", "compose"]), ("docker", ["docker", "compose"])):
        if preferred != "auto" and engine != preferred:
            continue
        if not shutil.which(engine):
            continue
        try:
            subprocess.run([engine, "info"], check=True, capture_output=True, timeout=15)
            subprocess.run(compose + ["version"], check=True, capture_output=True, timeout=15)
            return compose
        except (subprocess.SubprocessError, OSError):
            continue
    raise RuntimeError("Start Podman (podman machine start on Windows) and install a Compose provider, or start Docker.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="Start the four local containers")
    parser.add_argument("--hooks-only", action="store_true")
    parser.add_argument("--engine", choices=("auto", "podman", "docker"), default="auto")
    args = parser.parse_args()
    for executable in ("git", "cargo", "go"):
        if not shutil.which(executable):
            raise RuntimeError(f"Required tool missing: {executable}")
    run(["git", "config", "core.hooksPath", ".githooks"])
    hook = ROOT / ".githooks/pre-commit"
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if args.hooks_only:
        return
    if args.start:
        run(compose_command(args.engine) + ["-f", "docker-compose.yml", "up", "-d"])
    run([sys.executable, "scripts/healthcheck.py", "--wait", "180"])
    run([sys.executable, "spikes/active_spike.py"])


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"SETUP_FAILED: {error}", file=sys.stderr)
        sys.exit(1)
'''
FILES['scripts/verify.py'] = r'''#!/usr/bin/env python3
"""The shared local/CI verification matrix; missing tools and skipped I/O fail closed."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pure", action="store_true", help="Only Track A; not sufficient for I/O commits")
    args = parser.parse_args()
    commands = [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]]
    if not args.pure:
        commands += [[sys.executable, "scripts/healthcheck.py"], [sys.executable, "spikes/active_spike.py"]]
    commands += [["cargo", "test", "--locked", "-p", "jql_core"] if args.pure
                 else ["cargo", "test", "--locked", "--workspace"],
                 [sys.executable, "scripts/go_test.py"]]
    for command in commands:
        print("VERIFY:", " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True, timeout=300)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.SubprocessError) as error:
        print(f"ERR_TEST_EXECUTION_FAILED: {error}", file=sys.stderr)
        sys.exit(3)
'''
FILES['scripts/go_test.py'] = r'''#!/usr/bin/env python3
"""Run real Go tests; retry only temporary-directory cleanup on Windows locks."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    temporary_root = Path(tempfile.gettempdir()).resolve()
    work = Path(tempfile.mkdtemp(prefix="yaja-go-", dir=temporary_root)).resolve()
    if work.parent != temporary_root or not work.name.startswith("yaja-go-"):
        raise RuntimeError("Refusing cleanup outside the allocated temporary directory")
    environment = os.environ.copy()
    environment["GOTMPDIR"] = str(work)
    try:
        # -work delegates deletion to us; it does not skip compilation or tests.
        command = ["go", "test", "-count=1", "-work", *(sys.argv[1:] or ["./go/pure/sync_contract/..."])]
        result = subprocess.run(command, cwd=ROOT, env=environment, timeout=300, check=False)
        return result.returncode
    finally:
        deadline = time.monotonic() + 30
        while work.exists():
            try:
                shutil.rmtree(work)
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)


if __name__ == "__main__":
    sys.exit(main())
'''
FILES['.githooks/ai_enforcer.json'] = r'''{
  "version": 1,
  "io_roots": ["src/io/", "go/io/"],
  "rules": [
    {
      "id": "ERR_MOCK_IN_IO", "exit_code": 1,
      "scope": "src/io/**",
      "forbidden_imports": ["mockall", "jest.mock", "httptest", "sqlmock", "testify/mock", "unittest.mock", "unittest import mock"],
      "message": "Remove I/O mocks and verify against a real container."
    },
    {"id": "ERR_UNVERIFIED_ASSUMPTION", "exit_code": 2, "required_files": ["spikes/active_spike.py"], "message": "Execute a fresh live spike before committing I/O or dependency changes."},
    {"id": "ERR_TEST_EXECUTION_FAILED", "exit_code": 3, "message": "Fix the failing staged test suite."},
    {"id": "ERR_DOCS_STALE", "exit_code": 4, "message": "Stage a relevant Markdown specification update with code changes."}
  ]
}
'''
FILES['.githooks/pre-commit'] = '#!/bin/sh\nexec python .githooks/pre_commit.py\n'
FILES['.githooks/pre-commit.bat'] = '@echo off\r\npython .githooks/pre_commit.py\r\nexit /b %errorlevel%\r\n'
FILES['.githooks/pre_commit.py'] = r'''#!/usr/bin/env python3
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
'''
FILES['tests/test_enforcer.py'] = r'''"""Pure policy tests; these do not replace the required physical I/O checks."""
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
'''
FILES['README.md'] = r'''# YAJA — Yet Another Jira Alternative

![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)
![Stage: scaffold](https://img.shields.io/badge/stage-scaffold-orange)

YAJA is an open-source foundation for a dynamic-field, event-driven project
management system. This repository implements the ADR-001 engineering protocol,
a small Rust equality parser, a live NATS boundary probe, and typed synchronization
contracts. The full YAJA application is a roadmap, not a delivered feature.
CI badge: add the repository-specific Actions badge after publishing a remote.

## Architecture

```mermaid
flowchart LR
    UI[React + Rust Wasm] --> Edge[Go edge]
    Edge --> Bus[NATS JetStream / KV]
    Bus --> Worker[Rust worker]
    Worker --> Ferret[FerretDB]
    Ferret --> PG[PostgreSQL: source of record]
    PG --> CDC[Debezium: durable WAL checkpoint]
    CDC --> Indexer[Projection worker via NATS]
    Indexer --> Search[OpenSearch: read projection]
    Indexer --> Bus
    Bus --> SSE[Go SSE multiplexer]
    SSE --> UI
```

The diagram shows the target architecture. Debezium, the indexer, Go edge, React,
Rhai, and Wasm emitters are not implemented by this baseline. See
[the roadmap and limits](docs/IMPLEMENTATION.md) and the supplied
[v0.2 design reference](docs/reference/YAJA-v0.2.md).

Architectural invariants:

- Mutate one document atomically; use asynchronous sagas for multi-document work.
- Never synchronously consult OpenSearch to authorize or validate a write.
- Compile JQL once in shared Rust; do not duplicate client evaluation logic.
- Stamp compiled artifacts and provisional mutations with an exact schema epoch.
- Treat optimistic UI state as provisional until authoritative SSE reconciliation.
- Checkpoint CDC against PostgreSQL WAL, independently of worker lifetime.
- Use typed BSON and the MongoDB driver's `doc!` macro for future database queries.
- Place pure Rust logic in `src/pure/`, physical Rust boundaries in `src/io/`.
  Go pure contracts live in `go/pure/`; future Go adapters belong in `go/io/`,
  which the same hook audits. This separate Go tree keeps Cargo's required
  `src/pure/*` and `src/io/*` workspace globs valid.

## Quickstart (Windows 11 and Ubuntu)

Install Python 3.10+, Git, Rust stable with Cargo, Go 1.22+, and Podman with a
Compose provider (`podman-compose` or Docker Compose). The runtime needs Internet
access for initial image pulls, about 4 GiB available memory, and free ports
5432, 27017, 4222, 8222, and 9200. npm/pnpm is optional for the declarations-only
JavaScript workspace. No third-party Python packages are required.

For an empty directory containing the generator:

```text
python scaffold.py
```

The generator writes complete files without overwriting differences, initializes
`main`, starts the local stack, runs verification, and commits only on success.
For an existing checkout:

```text
python scripts/setup_env.py --start
python scripts/verify.py
```

On Windows, start the Podman VM first with `podman machine start`. Linux hosts
and the Linux VM need `vm.max_map_count` at least 262144 for OpenSearch; the
Python CI preparation helper configures this in the disposable Ubuntu runner.
Read [SECURITY.md](SECURITY.md) before exposing development ports.

Equivalent direct Podman commands:

```text
podman compose -f docker-compose.yml up -d
python scripts/healthcheck.py --wait 180
python spikes/active_spike.py
cargo test --locked --workspace
go test ./go/pure/sync_contract/...
podman compose -f docker-compose.yml logs
podman compose -f docker-compose.yml down
```

`podman-compose -f docker-compose.yml up -d` is also supported. Container data
is ephemeral and is lost on container removal. PostgreSQL uses the requested
local database/user/password: `yaja` / `postgres` / `postgres`.

## Enforcement and contribution

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [ADR-001](docs/ADR-001-AI-TESTING.md).
Git's hooks path is `.githooks`. On Windows, Git uses its bundled POSIX launcher;
on Ubuntu it uses `/bin/sh`. The two-line launcher only invokes Python. The `.bat`
launcher supports direct Windows invocation. No shell logic implements policy.

The hook scans every staged I/O file for banned tokens, executes a fresh physical
spike for boundary/dependency changes, requires staged Markdown with code, and
tests an isolated export of the Git index. Rust and Go tests fail if their tools
are absent. A Track A-only run (`python scripts/verify.py --pure`) is available
while working on pure logic. It does not certify I/O changes.

The FerretDB 1.24.2 compatibility line is intentional: the supplied stock
PostgreSQL 16 requirement matches the [1.x PostgreSQL backend](https://docs.ferretdb.io/v1.24/quickstart-guide/docker/).
This is not an endorsement of that legacy line for deployment. Review supported
versions, image digests, TLS, authentication, and backend migration before release.

## Publish

```text
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

Before accepting public reports, enable GitHub private vulnerability reporting
and define the community reporting channel described in SECURITY.md and the
Code of Conduct. Code is Apache-2.0; Contributor Covenant text retains its
upstream CC-BY-4.0 attribution.
'''
FILES['docs/ADR-001-AI-TESTING.md'] = r'''# ADR-001: YAJA AI Engineering Protocol

Status: accepted for the repository scaffold.

## Decision and precedence

The supplied ADR is preserved in [the original reference](reference/ADR-001-original.md).
The user's scaffold request supersedes its Bash/ripgrep and `.sh` spike examples:
all policy, setup, verification, and test helpers use Python's standard library.
Only Git's mandatory thin launchers use shell/batch syntax. Boundary-first
filesystem separation replaces guesses based on adjacent driver imports.

## Seven-step loop

1. **Plan:** describe behavior, acceptance criteria, risks, and measurable limits.
2. **Design:** define ownership, typed contracts, security, and failure behavior.
   Stop unverified boundary assumptions here; run an isolated physical spike.
3. **Test Dev:** write executable acceptance tests for the change.
4. **Test Fail:** execute the new tests and retain the actual expected failure.
5. **Execution:** implement the smallest complete change that meets the criteria.
6. **Test Pass:** rerun tests, repair implementation or mistaken assertions until
   all relevant checks pass, including real boundary checks.
7. **Docs:** update relevant Markdown to describe the resulting behavior and limits.

No completion claim may rest on a skipped or mocked physical test. A baseline
generator validates its emitted repository; it does not fabricate red-phase
history. Feature PRs must report their observed red and green evidence.

## Testing tracks and spike mandate

Track A (`src/pure/`, `go/pure/`) contains pure logic. Unit tests and test doubles
are permitted there. Track C (`src/io/`, future `go/io/`) contains network,
storage, event bus, and CDC boundaries; physical verification is mandatory and
mocking is forbidden. Keep tests alongside the boundary they exercise.

A spike states a falsifiable hypothesis, prerequisites, commands, observed
response, and limitations. `spikes/active_spike.py` checks the actual NATS greeting,
CONNECT/PING/PONG exchange, and JetStream account API. It runs afresh against the
staged script for every I/O, verification-tool, or dependency change. No existence
check or saved success marker counts as execution. Additional adapters must add
their own physical acceptance checks to the shared verification matrix.

## Commit gate

| Exit | Symbol | Required correction |
| --- | --- | --- |
| 1 | ERR_MOCK_IN_IO | Remove prohibited tokens from the I/O tree and use a live service. |
| 2 | ERR_UNVERIFIED_ASSUMPTION | Add/fix the staged spike and start live infrastructure. |
| 3 | ERR_TEST_EXECUTION_FAILED | Fix staged tests, missing tools, invalid policy, or index races. |
| 4 | ERR_DOCS_STALE | Stage an added/modified relevant Markdown specification. |

The gate exports the index to a temporary directory; untracked and unstaged
source files cannot repair the tested snapshot. It scans all indexed I/O text,
including manifests and comments, using case-insensitive token patterns. Deleted
Markdown does not satisfy the documentation rule. Renames count as delete/add.
Symlinks and submodules fail closed in the verified snapshot. Source/dependency
changes run tests; docs-only commits still audit I/O tokens.

The spike runs before the documentation check; the documentation check runs
before the test matrix for actionable feedback. CI uses `--base` to compare PR
or push changes against their actual base, with a clean index. Root-commit CI
uses the same staged-change contract by removing HEAD only in its disposable
checkout before invoking the hook.

## Limits and trust model

The regex gate is conservative, not a multi-language semantic proof. Review must
catch alternate mocking APIs, dynamic imports, generated code, and policy edits.
The hook detects an added/modified Markdown file but cannot prove its relevance.
It cannot prove a developer ran a failing test before implementation. PR evidence
and review cover those properties. Contributors can disable local hooks; protect
`main` with required CI and reviews, and treat enforcement changes as sensitive.
Do not use `--no-verify` to declare compliance. Pin/update CI and image dependencies
through reviewed changes. A green handshake does not certify durable publication,
delivery, CDC replay, or production resilience.
'''
FILES['docs/IMPLEMENTATION.md'] = r'''# Implementation scope and acceptance evidence

This initial repository is an executable engineering baseline, not a deployable
project-management product. Its acceptance matrix is:

| Component | Implemented contract | Verification |
| --- | --- | --- |
| JQL Rust core | Complete `identifier = 'nonempty value'` input; rejects ambiguous/trailing grammar | 3 unit tests |
| Rust NATS boundary | Bounded TCP connection, INFO, CONNECT, two PING/PONG round trips | Always-on live integration test |
| Python NATS spike | INFO JetStream flag plus actual `$JS.API.INFO` response | Runs fresh in setup and I/O commit gate |
| Infrastructure | Four TCP ports; OpenSearch HTTP health | healthcheck.py |
| Go pure contract | Provisional evaluation requires exact epoch and purity | Table-driven unit test |
| JS workspace | Shared TypeScript declarations | Declarations only; no runtime test claim |
| Enforcement | Prohibited tokens, physical spike, staged suites, Markdown update | Policy tests plus Git acceptance checks |

Rust currently has no external crates. The small synchronous boundary probe
exposes connection signatures but does not pretend to be an asynchronous
JetStream publishing implementation. Add an official NATS client and physical
publish/ack/replay acceptance tests when implementing the event dispatcher.

The Go verification helper runs `go test -work` in an owned temporary directory
and preserves the exact test exit status. Python then removes that directory,
retrying permission-related file locks for at most 30 seconds. This addresses an
observed Go 1.27/Windows executable-cleanup race without skipping tests, ignoring
test failures, or leaving build directories behind. No delay is needed when the
first cleanup succeeds. Only cleanup is retried; failing tests are never retried.

Deferred product milestones from the supplied v0.2 specification: full JQL grammar
and typed OpenSearch/Rhai emission; Wasm bindings; MongoDB/BSON single-document
mutations; authoritative schema KV; sagas; durable Debezium WAL-to-NATS delivery;
idempotent projection worker; Go auth/API/SSE multiplexing; React optimistic
overlay state; reconciliation and crash-isolation acceptance tests.

The supplied v0.2 error table describes `CDC_PIPELINE_STALLED` as both HTTP 503
and a 200 response with a null token. Resolve that API contract before implementing
the route. This scaffold does not choose silently between contradictory outcomes.

Infrastructure is a local disposable topology. Stock PostgreSQL uses logical WAL
settings, but no replication slot or CDC connector is created yet. FerretDB is a
standalone proxy container backed by the PostgreSQL service, not an in-process
embedded store. TCP health establishes reachability; it does not prove database
query correctness. OpenSearch HTTP and NATS handshake checks are stronger but
still intentionally limited. Supply adapter-specific physical tests as those
boundaries are implemented.
'''
FILES['CONTRIBUTING.md'] = r'''# Contributing to YAJA

All contributions follow [ADR-001](docs/ADR-001-AI-TESTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Open a feature or spike proposal before
changing architecture. Keep each PR focused and describe observable behavior.

## Development environment

Use Python 3.10+, Git, Rust stable, Go 1.22+, and a running Podman/Docker engine
with Compose. Run `python scripts/setup_env.py --start` after cloning; Git does
not automatically install hooks from a clone. `python scripts/verify.py` executes
the shared full matrix. `python scripts/verify.py --pure` is a Track A iteration
tool. See README for port requirements and container lifecycle commands.

## Required development loop

1. Plan acceptance criteria, affected boundaries, performance/security risks.
2. Design typed interfaces and error behavior. Run a real spike before depending
   on uncertain network, storage, concurrency, or library behavior.
3. Develop tests that express the acceptance criteria, including failure paths.
4. Run tests and record the expected red result; do not invent test evidence.
5. Implement the behavior without weakening tests to hide defects.
6. Run the relevant tests to green, then the complete required verification gate.
7. Update relevant Markdown, including contract changes and known limitations.

Track A pure logic may use unit tests and mocks. Track C physical boundaries must
never use mocks, in-memory replacements, or ignored tests as evidence. Extend the
live suite for each new adapter. NATS handshake success does not establish a
Postgres mapping or CDC crash-recovery contract. Record those as separate spikes.

## Review and commit

Use descriptive conventional commit subjects. Stage source, tests, and relevant
Markdown together. The hook checks the index, so stage test fixes before retrying.
Read its symbolic error and correct the cause; never bypass the gate. Run
`cargo fmt --all` and `gofmt` on changed Go files before staging. Pure Rust and I/O
Rust crates live under the two Cargo workspace globs. Go modules live in the
separate pure/I/O Go tree; add every module to `go.work` and the test matrix.

The PR should show the hypothesis, exact red/green commands, live service versions,
observed output, documentation changes, and remaining limitations. Maintainers
review architectural invariants and relevance of documentation, which token
checks cannot prove. Changes to policy or CI require careful maintainer review.
Configure required CI and protected `main` when publishing the repository.

## License and attribution

By submitting code, you agree to license your contribution under Apache-2.0.
Retain third-party license notices; do not paste incompatible code or secrets.
Add yourself to CONTRIBUTORS.md using the public name/handle you want recognized.
Report vulnerabilities privately through SECURITY.md, not a public issue.
'''
FILES['CONTRIBUTORS.md'] = r'''# Contributors

| Contributor | Contribution |
| --- | --- |
| YAJA project author | Original v0.2 architecture and ADR-001 requirements |
| OpenAI Codex, at the project author's direction | Initial repository generator and verification baseline |

This ledger records contributions rather than asserting legal copyright ownership.
Add your preferred public name or handle in the PR containing your contribution.
Git history remains the detailed authorship record.
'''
FILES['SECURITY.md'] = r'''# Security policy

## Supported scope

Only the current main branch receives scaffold fixes. No supported production
release exists yet. Development Compose publishes the explicitly requested host
ports with default PostgreSQL credentials and disabled OpenSearch authentication.
Run it only on a trusted, firewalled workstation or disposable CI runner. Do not
use this configuration for Internet-facing or production data. Containers are
ephemeral; removing them can remove data.

## Private reporting

Once the project is published, use its GitHub **Security → Report a vulnerability**
private reporting feature. Maintainers must enable this feature before soliciting
public reports. Before publication, contact the repository owner through the
private channel already used to collaborate on the project. If no private channel
is available, open a public issue asking only for a private contact method; do not
include vulnerability details, credentials, or a working exploit there.

Include affected revision, environment, prerequisites, reproduction, impact, and
proposed mitigation. Share only the minimum sanitized evidence needed to reproduce.

## Response targets (SLA policy)

Maintainers target acknowledgment within 3 business days, initial triage within
7 calendar days, and a mitigation plan within 14 calendar days for confirmed
critical/high issues. These are volunteer project service targets, not a paid
contractual guarantee. Give weekly updates while a confirmed high-impact issue
remains open. Agree on disclosure timing with the reporter, normally within
90 days; do not publish unpatched details without coordinated assessment.

Before release, review supported FerretDB/backend versions and all image pins;
configure TLS, credentials, least privilege, backups, resource limits, tenancy,
dependency scanning, signed releases, and protected required CI. Never commit
tokens or `.env` secrets. The local hook is a developer aid, not a security sandbox.
'''
FILES['spikes/README.md'] = r'''# Physical spikes

A spike resolves one uncertain external behavior before implementation depends
on it. Write it in standard-library Python, with the hypothesis in its docstring,
the exact service/version and prerequisites, bounded timeouts, raw observable
output, nonzero failure status, and a clear cleanup procedure. Do not substitute
fixtures or mock servers for a physical target. Add lasting knowledge to docs.

Run `python scripts/setup_env.py --start`, then `python spikes/active_spike.py`.
The active hypothesis is that the real local NATS server advertises JetStream,
accepts CONNECT/PING, returns PONG, and serves a JetStream account-info request.
The script uses a random private inbox and auto-unsubscribes after one reply.
It writes no stream or application data; closing the socket completes cleanup.
Connection and read deadlines are 3 seconds, with bounded frame counts and sizes.

Success reports JSON with the observed server ID/version and response type. This
proves handshake/account API reachability, not durable message storage or delivery.
The hook executes it fresh from the Git index and does not trust cached markers.
For future database, CDC, or search work, introduce a new concrete physical spike
and add its acceptance checks to scripts/verify.py before claiming the boundary.
'''
FILES['.github/pull_request_template.md'] = r'''## Behavior and motivation

Describe the concrete problem, resulting behavior, and affected contracts.

## Verification evidence

Provide red/green commands and output, live service versions, spike observations,
and remaining limitations. Explain any item below that does not apply.

- [ ] Followed Plan → Design → Test Dev → Test Fail → Execution → Test Pass → Docs.
- [ ] Kept pure logic and physical I/O in their designated trees.
- [ ] Introduced no I/O mocks or substituted services.
- [ ] Executed active spikes against live infrastructure for boundary/dependency changes.
- [ ] Passed the staged hook and relevant full test matrix without bypassing checks.
- [ ] Updated relevant Markdown to reflect implemented behavior.
- [ ] Preserved CQRS isolation, single-document atomicity, epoch strictness, and durable CDC design.
- [ ] Reviewed security implications and third-party licensing.
'''
FILES['.github/ISSUE_TEMPLATE/bug_report.md'] = r'''---
name: Bug report
about: Report reproducible unexpected behavior
title: "Bug: "
labels: bug
---

## Observed and expected behavior

Describe both outcomes and the user impact. Report vulnerabilities privately.

## Reproduction

List minimal steps, exact commands, revision, OS, tool versions, and live container
versions. Include sanitized logs and whether the failure is consistent.

## Verification boundary

Identify Track A or Track C, affected invariants, and a candidate acceptance test.
'''
FILES['.github/ISSUE_TEMPLATE/feature_request.md'] = r'''---
name: Feature proposal
about: Propose behavior with measurable acceptance criteria
title: "Feature: "
labels: enhancement
---

## Problem and desired outcome

Explain the user workflow, motivation, and concrete observable change.

## Design and alternatives

Describe affected contracts, pure/I/O ownership, security and performance limits,
alternatives considered, and any uncertain behavior requiring a physical spike.

## Acceptance and documentation

List executable acceptance criteria, required live services, and docs to update.
'''
FILES['.github/ISSUE_TEMPLATE/spike_proposal.md'] = r'''---
name: Physical spike proposal
about: Resolve an unverified infrastructure or library assumption
title: "Spike: "
labels: documentation
---

## Falsifiable hypothesis

State exactly what external behavior must be observed before design can proceed.

## Physical setup and executable probe

Specify service images, ports, Python script, commands, bounded deadlines, and
cleanup. No mocked I/O is permitted.

## Observations and decision

Attach actual sanitized output, pass/fail criteria, known limits, and the resulting
design decision. Link the Markdown contract updated with the findings.
'''
FILES['scripts/ci_prepare.py'] = r'''#!/usr/bin/env python3
"""Prepare only the disposable Ubuntu CI host for OpenSearch."""
import subprocess
import sys

if sys.platform != "linux":
    raise SystemExit("ci_prepare.py is only for the disposable Linux CI host")
subprocess.run(["sudo", "sysctl", "-w", "vm.max_map_count=262144"], check=True)
'''
FILES['scripts/ci_enforce.py'] = r'''#!/usr/bin/env python3
"""Select the actual GitHub event base and exercise the same commit gate."""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
base = event.get("pull_request", {}).get("base", {}).get("sha") or event.get("before")
if base and set(base) != {"0"}:
    subprocess.run([sys.executable, ".githooks/pre_commit.py", "--base", base], cwd=ROOT, check=True)
else:
    # Root push: simulate the initial staged commit only inside a disposable clone.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="yaja-ci-root-") as temporary:
        subprocess.run(["git", "clone", "--no-hardlinks", str(ROOT), temporary], check=True)
        subprocess.run(["git", "update-ref", "-d", "HEAD"], cwd=temporary, check=True)
        subprocess.run([sys.executable, ".githooks/pre_commit.py"], cwd=temporary, check=True)
'''
FILES['.github/workflows/ci.yml'] = r'''name: ADR-001 verification
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  verify:
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false
          # Compare exactly the PR head to its base, not an unrelated merge index.
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22.x'
          cache: false
      - name: Install Rust stable
        run: rustup toolchain install stable --profile minimal
      - name: Select Rust stable
        run: rustup default stable
      - name: Prepare disposable host
        run: python scripts/ci_prepare.py
      - name: Start infrastructure and check physical readiness
        run: python scripts/setup_env.py --start --engine docker
      - name: Test Python policy, cargo, Go, and physical boundaries
        run: python scripts/verify.py
      - name: Validate commit policy against event base
        run: python scripts/ci_enforce.py
      - name: Container diagnostics
        if: failure()
        run: docker compose -f docker-compose.yml logs --no-color
      - name: Tear down ephemeral containers
        if: always()
        run: docker compose -f docker-compose.yml down --volumes --remove-orphans
'''

FILES['tests/test_git_gate.py'] = r'''"""Real temporary Git repositories verify staged enforcement and hook dispatch.

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
'''

# Canonical legal text and supplied design references are embedded below.

FILES['LICENSE'] = '\n                                 Apache License\n                           Version 2.0, January 2004\n                        http://www.apache.org/licenses/\n\n   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n   1. Definitions.\n\n      "License" shall mean the terms and conditions for use, reproduction,\n      and distribution as defined by Sections 1 through 9 of this document.\n\n      "Licensor" shall mean the copyright owner or entity authorized by\n      the copyright owner that is granting the License.\n\n      "Legal Entity" shall mean the union of the acting entity and all\n      other entities that control, are controlled by, or are under common\n      control with that entity. For the purposes of this definition,\n      "control" means (i) the power, direct or indirect, to cause the\n      direction or management of such entity, whether by contract or\n      otherwise, or (ii) ownership of fifty percent (50%) or more of the\n      outstanding shares, or (iii) beneficial ownership of such entity.\n\n      "You" (or "Your") shall mean an individual or Legal Entity\n      exercising permissions granted by this License.\n\n      "Source" form shall mean the preferred form for making modifications,\n      including but not limited to software source code, documentation\n      source, and configuration files.\n\n      "Object" form shall mean any form resulting from mechanical\n      transformation or translation of a Source form, including but\n      not limited to compiled object code, generated documentation,\n      and conversions to other media types.\n\n      "Work" shall mean the work of authorship, whether in Source or\n      Object form, made available under the License, as indicated by a\n      copyright notice that is included in or attached to the work\n      (an example is provided in the Appendix below).\n\n      "Derivative Works" shall mean any work, whether in Source or Object\n      form, that is based on (or derived from) the Work and for which the\n      editorial revisions, annotations, elaborations, or other modifications\n      represent, as a whole, an original work of authorship. For the purposes\n      of this License, Derivative Works shall not include works that remain\n      separable from, or merely link (or bind by name) to the interfaces of,\n      the Work and Derivative Works thereof.\n\n      "Contribution" shall mean any work of authorship, including\n      the original version of the Work and any modifications or additions\n      to that Work or Derivative Works thereof, that is intentionally\n      submitted to Licensor for inclusion in the Work by the copyright owner\n      or by an individual or Legal Entity authorized to submit on behalf of\n      the copyright owner. For the purposes of this definition, "submitted"\n      means any form of electronic, verbal, or written communication sent\n      to the Licensor or its representatives, including but not limited to\n      communication on electronic mailing lists, source code control systems,\n      and issue tracking systems that are managed by, or on behalf of, the\n      Licensor for the purpose of discussing and improving the Work, but\n      excluding communication that is conspicuously marked or otherwise\n      designated in writing by the copyright owner as "Not a Contribution."\n\n      "Contributor" shall mean Licensor and any individual or Legal Entity\n      on behalf of whom a Contribution has been received by Licensor and\n      subsequently incorporated within the Work.\n\n   2. Grant of Copyright License. Subject to the terms and conditions of\n      this License, each Contributor hereby grants to You a perpetual,\n      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n      copyright license to reproduce, prepare Derivative Works of,\n      publicly display, publicly perform, sublicense, and distribute the\n      Work and such Derivative Works in Source or Object form.\n\n   3. Grant of Patent License. Subject to the terms and conditions of\n      this License, each Contributor hereby grants to You a perpetual,\n      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n      (except as stated in this section) patent license to make, have made,\n      use, offer to sell, sell, import, and otherwise transfer the Work,\n      where such license applies only to those patent claims licensable\n      by such Contributor that are necessarily infringed by their\n      Contribution(s) alone or by combination of their Contribution(s)\n      with the Work to which such Contribution(s) was submitted. If You\n      institute patent litigation against any entity (including a\n      cross-claim or counterclaim in a lawsuit) alleging that the Work\n      or a Contribution incorporated within the Work constitutes direct\n      or contributory patent infringement, then any patent licenses\n      granted to You under this License for that Work shall terminate\n      as of the date such litigation is filed.\n\n   4. Redistribution. You may reproduce and distribute copies of the\n      Work or Derivative Works thereof in any medium, with or without\n      modifications, and in Source or Object form, provided that You\n      meet the following conditions:\n\n      (a) You must give any other recipients of the Work or\n          Derivative Works a copy of this License; and\n\n      (b) You must cause any modified files to carry prominent notices\n          stating that You changed the files; and\n\n      (c) You must retain, in the Source form of any Derivative Works\n          that You distribute, all copyright, patent, trademark, and\n          attribution notices from the Source form of the Work,\n          excluding those notices that do not pertain to any part of\n          the Derivative Works; and\n\n      (d) If the Work includes a "NOTICE" text file as part of its\n          distribution, then any Derivative Works that You distribute must\n          include a readable copy of the attribution notices contained\n          within such NOTICE file, excluding those notices that do not\n          pertain to any part of the Derivative Works, in at least one\n          of the following places: within a NOTICE text file distributed\n          as part of the Derivative Works; within the Source form or\n          documentation, if provided along with the Derivative Works; or,\n          within a display generated by the Derivative Works, if and\n          wherever such third-party notices normally appear. The contents\n          of the NOTICE file are for informational purposes only and\n          do not modify the License. You may add Your own attribution\n          notices within Derivative Works that You distribute, alongside\n          or as an addendum to the NOTICE text from the Work, provided\n          that such additional attribution notices cannot be construed\n          as modifying the License.\n\n      You may add Your own copyright statement to Your modifications and\n      may provide additional or different license terms and conditions\n      for use, reproduction, or distribution of Your modifications, or\n      for any such Derivative Works as a whole, provided Your use,\n      reproduction, and distribution of the Work otherwise complies with\n      the conditions stated in this License.\n\n   5. Submission of Contributions. Unless You explicitly state otherwise,\n      any Contribution intentionally submitted for inclusion in the Work\n      by You to the Licensor shall be under the terms and conditions of\n      this License, without any additional terms or conditions.\n      Notwithstanding the above, nothing herein shall supersede or modify\n      the terms of any separate license agreement you may have executed\n      with Licensor regarding such Contributions.\n\n   6. Trademarks. This License does not grant permission to use the trade\n      names, trademarks, service marks, or product names of the Licensor,\n      except as required for reasonable and customary use in describing the\n      origin of the Work and reproducing the content of the NOTICE file.\n\n   7. Disclaimer of Warranty. Unless required by applicable law or\n      agreed to in writing, Licensor provides the Work (and each\n      Contributor provides its Contributions) on an "AS IS" BASIS,\n      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or\n      implied, including, without limitation, any warranties or conditions\n      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A\n      PARTICULAR PURPOSE. You are solely responsible for determining the\n      appropriateness of using or redistributing the Work and assume any\n      risks associated with Your exercise of permissions under this License.\n\n   8. Limitation of Liability. In no event and under no legal theory,\n      whether in tort (including negligence), contract, or otherwise,\n      unless required by applicable law (such as deliberate and grossly\n      negligent acts) or agreed to in writing, shall any Contributor be\n      liable to You for damages, including any direct, indirect, special,\n      incidental, or consequential damages of any character arising as a\n      result of this License or out of the use or inability to use the\n      Work (including but not limited to damages for loss of goodwill,\n      work stoppage, computer failure or malfunction, or any and all\n      other commercial damages or losses), even if such Contributor\n      has been advised of the possibility of such damages.\n\n   9. Accepting Warranty or Additional Liability. While redistributing\n      the Work or Derivative Works thereof, You may choose to offer,\n      and charge a fee for, acceptance of support, warranty, indemnity,\n      or other liability obligations and/or rights consistent with this\n      License. However, in accepting such obligations, You may act only\n      on Your own behalf and on Your sole responsibility, not on behalf\n      of any other Contributor, and only if You agree to indemnify,\n      defend, and hold each Contributor harmless for any liability\n      incurred by, or claims asserted against, such Contributor by reason\n      of your accepting any such warranty or additional liability.\n\n   END OF TERMS AND CONDITIONS\n\n   APPENDIX: How to apply the Apache License to your work.\n\n      To apply the Apache License to your work, attach the following\n      boilerplate notice, with the fields enclosed by brackets "[]"\n      replaced with your own identifying information. (Don\'t include\n      the brackets!)  The text should be enclosed in the appropriate\n      comment syntax for the file format. We also recommend that a\n      file or class name and description of purpose be included on the\n      same "printed page" as the copyright notice for easier\n      identification within third-party archives.\n\n   Copyright [yyyy] [name of copyright owner]\n\n   Licensed under the Apache License, Version 2.0 (the "License");\n   you may not use this file except in compliance with the License.\n   You may obtain a copy of the License at\n\n       http://www.apache.org/licenses/LICENSE-2.0\n\n   Unless required by applicable law or agreed to in writing, software\n   distributed under the License is distributed on an "AS IS" BASIS,\n   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n   See the License for the specific language governing permissions and\n   limitations under the License.\n'

FILES['CODE_OF_CONDUCT.md'] = '+++\nversion = "2.1"\naliases = ["/version/2/1"]\nreportingPlaceholder = "[INSERT CONTACT METHOD]"\n+++\n\n# Contributor Covenant Code of Conduct\n\n## Our Pledge\n\nWe as members, contributors, and leaders pledge to make participation in our community a harassment-free experience for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, caste, color, religion, or sexual identity and orientation.\n\nWe pledge to act and interact in ways that contribute to an open, welcoming, diverse, inclusive, and healthy community.\n\n## Our Standards\n\nExamples of behavior that contributes to a positive environment for our community include:\n\n* Demonstrating empathy and kindness toward other people\n* Being respectful of differing opinions, viewpoints, and experiences\n* Giving and gracefully accepting constructive feedback\n* Accepting responsibility and apologizing to those affected by our mistakes, and learning from the experience\n* Focusing on what is best not just for us as individuals, but for the overall community\n\nExamples of unacceptable behavior include:\n\n* The use of sexualized language or imagery, and sexual attention or advances of any kind\n* Trolling, insulting or derogatory comments, and personal or political attacks\n* Public or private harassment\n* Publishing others\' private information, such as a physical or email address, without their explicit permission\n* Other conduct which could reasonably be considered inappropriate in a professional setting\n\n## Enforcement Responsibilities\n\nCommunity leaders are responsible for clarifying and enforcing our standards of acceptable behavior and will take appropriate and fair corrective action in response to any behavior that they deem inappropriate, threatening, offensive, or harmful.\n\nCommunity leaders have the right and responsibility to remove, edit, or reject comments, commits, code, wiki edits, issues, and other contributions that are not aligned to this Code of Conduct, and will communicate reasons for moderation decisions when appropriate.\n\n## Scope\n\nThis Code of Conduct applies within all community spaces, and also applies when an individual is officially representing the community in public spaces. Examples of representing our community include using an official e-mail address, posting via an official social media account, or acting as an appointed representative at an online or offline event.\n\n## Enforcement\n\nInstances of abusive, harassing, or otherwise unacceptable behavior may be reported to the community leaders responsible for enforcement at [INSERT CONTACT METHOD]. All complaints will be reviewed and investigated promptly and fairly.\n\nAll community leaders are obligated to respect the privacy and security of the reporter of any incident.\n\n## Enforcement Guidelines\n\nCommunity leaders will follow these Community Impact Guidelines in determining the consequences for any action they deem in violation of this Code of Conduct:\n\n### 1. Correction\n\n**Community Impact**: Use of inappropriate language or other behavior deemed unprofessional or unwelcome in the community.\n\n**Consequence**: A private, written warning from community leaders, providing clarity around the nature of the violation and an explanation of why the behavior was inappropriate. A public apology may be requested.\n\n### 2. Warning\n\n**Community Impact**: A violation through a single incident or series of actions.\n\n**Consequence**: A warning with consequences for continued behavior. No interaction with the people involved, including unsolicited interaction with those enforcing the Code of Conduct, for a specified period of time. This includes avoiding interactions in community spaces as well as external channels like social media. Violating these terms may lead to a temporary or permanent ban.\n\n### 3. Temporary Ban\n\n**Community Impact**: A serious violation of community standards, including sustained inappropriate behavior.\n\n**Consequence**: A temporary ban from any sort of interaction or public communication with the community for a specified period of time. No public or private interaction with the people involved, including unsolicited interaction with those enforcing the Code of Conduct, is allowed during this period. Violating these terms may lead to a permanent ban.\n\n### 4. Permanent Ban\n\n**Community Impact**: Demonstrating a pattern of violation of community standards, including sustained inappropriate behavior, harassment of an individual, or aggression toward or disparagement of classes of individuals.\n\n**Consequence**: A permanent ban from any sort of public interaction within the community.\n\n## Attribution\n\nThis Code of Conduct is adapted from the [Contributor Covenant][homepage], version 2.1, available at [https://www.contributor-covenant.org/version/2/1/code_of_conduct.html][v2.1].\n\nCommunity Impact Guidelines were inspired by [Mozilla\'s code of conduct enforcement ladder][Mozilla CoC].\n\nFor answers to common questions about this code of conduct, see the FAQ at [https://www.contributor-covenant.org/faq][FAQ]. Translations are available at [https://www.contributor-covenant.org/translations][translations].\n\n[homepage]: https://www.contributor-covenant.org\n[v2.1]: https://www.contributor-covenant.org/version/2/1/code_of_conduct.html\n[Mozilla CoC]: https://github.com/mozilla/diversity\n[FAQ]: https://www.contributor-covenant.org/faq\n[translations]: https://www.contributor-covenant.org/translations\n'

FILES['docs/reference/YAJA-v0.2.md'] = 'Version: 0.2\n# YAJA (Yet Another Jira Alternative) — Technical Specification\n\n## 1. System Overview & Invariants\n\n* **Objective**: A high-performance, open-source project management platform built for millions of tasks with totally dynamic custom fields. YAJA provides a real-time, optimistic frontend UX backed by an asynchronous, CQRS-driven, polyglot event-driven architecture.\n* **Target Stack**:\n* **Frontend**: React, React Query (for cache state), WebAssembly (Wasm) for embedded Rhai execution and local JQL compilation.\n* **API Edge**: Go (Auth, HTTP Routing, SSE Stream Management, NATS Ingress).\n* **Worker Core**: Rust (Authoritative business logic, Native Rhai execution, Saga Orchestration, Database mutation).\n* **Primary DB (Writes/SoR)**: PostgreSQL accessed via FerretDB proxy (utilizing the official `mongodb` Rust driver).\n* **Search DB (Reads/Projection)**: OpenSearch (Apache-2.0, CQRS read model).\n* **Event Bus & State**: NATS JetStream (Sagas & CDC Pipeline) + NATS KV (Versioned Schema State).\n* **CDC Engine**: Debezium tailing PostgreSQL WAL (Logical Replication).\n\n\n* **Critical Invariants**:\n* **Single-Document Atomicity & Sagas**: All database mutations MUST be single-document atomic. Bulk/multi-document workflows MUST execute as asynchronous Event-Driven Sagas via NATS, publishing progress tokens over SSE. Database-level multi-document transactions are strictly forbidden.\n* **CQRS Availability Isolation**: The write-path (React -> Go -> NATS -> Rust -> Postgres) MUST NEVER synchronously query the read-path infrastructure (OpenSearch) to authorize or evaluate a mutation.\n* **Isomorphic Compilation**: Raw JQL MUST NOT be evaluated via regex or raw JavaScript. It must be compiled by a single Isomorphic Rust crate into either OpenSearch Query DSL (server-side) or a capability-tagged Rhai script (client-side Wasm).\n* **Schema Epoch Strictness**: Schema definitions are versioned event streams in NATS KV. Every compiled JQL artifact and optimistic UI mutation MUST be stamped with a Schema Epoch. Local Wasm evaluation is strictly *provisional* and defers to authoritative SSE sync tokens.\n* **Durable CDC Boundary**: The CDC connector (Debezium) MUST checkpoint against the database\'s native durable transaction log (Postgres WAL), entirely decoupled from the Rust worker\'s heap/process lifecycle.\n\n\n* **Anti-Requirements (MUST NOT)**:\n* Do NOT construct MongoDB queries, filters, or updates via string formatting/concatenation (e.g., `format!()`, string interpolation). All queries MUST use the official `mongodb` Rust driver\'s native `doc!` macro and typed struct serialization via `serde_bson`.\n* Do NOT implement HTTP polling mechanisms for state reconciliation; rely exclusively on Go-multiplexed SSE.\n* Do NOT evaluate view-membership via client-side AST logic duplication; use the shared Wasm-Rhai compiler.\n\n\n\n---\n\n## 2. Data Contracts & Canonical Types\n\n```rust\n// core_engine/src/models.rs (Rust Core)\n\nuse serde::{Deserialize, Serialize};\nuse bson::oid::ObjectId;\n\n/// The canonical entity payload for Tasks/Epics\n#[derive(Debug, Serialize, Deserialize)]\npub struct Action {\n    #[serde(rename = "_id")]\n    pub id: ObjectId,\n    pub project_id: String,\n    pub status: String,\n    pub created_at: u64,     // Unix epoch ms\n    pub _version: u64,       // For Optimistic Concurrency Control\n    pub custom_fields: Vec<CustomField>,\n}\n\n/// Strictly constrained custom field structure for predictable BSON/JSONB indexing\n#[derive(Debug, Serialize, Deserialize)]\n#[serde(tag = "type", content = "value")]\npub enum CustomField {\n    String { key: String, val: String },\n    Number { key: String, val: f64 },\n    Boolean { key: String, val: bool },\n    Keyword { key: String, val: String },\n}\n\n/// Schema definitions stored in NATS KV\n#[derive(Debug, Serialize, Deserialize)]\npub struct SchemaEpoch {\n    pub project_id: String,\n    pub revision: u64,       // Maps directly to NATS KV sequence revision\n    pub fields: Vec<FieldDefinition>,\n}\n\n/// Emitted by the Isomorphic JQL Compiler\n#[derive(Debug, Serialize, Deserialize)]\npub struct CompiledJqlArtifact {\n    pub epoch: u64,\n    pub is_pure: bool,       // If false, client MUST degrade to Tier 2 (Wait for SSE)\n    pub rhai_script: String, // e.g., "doc.status == \'Open\' && evaluate_num(doc, \'points\') > 5"\n}\n\n```\n\n```typescript\n// frontend/src/types/sync.ts (React Client)\n\nexport interface SSEEvent {\n    type: "SYNC_TOKEN" | "SCHEMA_ADVANCED" | "SAGA_PROGRESS";\n    payload: unknown;\n}\n\nexport interface SyncTokenPayload {\n    actionId: string;\n    esOffset: number; \n}\n\nexport interface SchemaAdvancedPayload {\n    projectId: string;\n    newEpoch: number;\n    diff: SchemaDiff[];\n}\n\nexport interface MutationResponse {\n    canonicalAction: Action;\n    syncToken: string; // Opaque token for ES reconciliation via SSE\n}\n\n```\n\n---\n\n## 3. State Machine & Execution Flow\n\n### State Transition Matrix (Optimistic UI & Schema Reconciliation)\n\n| Current State | Triggering Event | Next State | Guard Condition | Side Effects / Sidecars |\n| --- | --- | --- | --- | --- |\n| `IDLE` | `CREATE_ACTION_UI` | `WASM_EVALUATING` | `compiled_script.epoch == client.current_epoch` | Pause UI input, invoke Wasm-Rhai runtime |\n| `WASM_EVALUATING` | `RHAI_MATCH == TRUE` | `OPTIMISTIC_INJECT` | `compiled_script.is_pure == true` | Prepend to React Query overlay cache, Fire API `POST` |\n| `WASM_EVALUATING` | `RHAI_MATCH == FALSE` | `OPTIMISTIC_SUPPRESS` | `compiled_script.is_pure == true` | Suppress injection, Fire API `POST`, Show generic Toast |\n| `WASM_EVALUATING` | `SCRIPT_IMPURE` | `TIER_2_WAIT` | `compiled_script.is_pure == false` | Suppress injection, Fire API `POST`, Show generic Toast |\n| `OPTIMISTIC_INJECT` | `SSE_SYNC_RECEIVED` | `AUTHORITATIVE_SYNC` | `sse.actionId == action.id` | Drop local overlay entry, Invalidate React Query ES lists |\n| `OPTIMISTIC_INJECT` | `API_POST_FAILED` | `ROLLBACK_UI` | Network/5xx/Timeout | Drop overlay entry, display error notification |\n| `ANY_STATE` | `SSE_SCHEMA_ADVANCED` | `FLUSH_STALE_SCHEMA` | `sse.newEpoch > client.current_epoch` | Flush Wasm LRU script cache, update local schema epoch |\n\n### Sequence Flow: Batch Operations via NATS Saga & CDC Pipeline\n\n```mermaid\nsequenceDiagram\n    autonumber\n    actor User\n    participant UI as React Client\n    participant Go as Go Edge API\n    participant NATS as NATS JetStream\n    participant Rust as Rust Worker\n    participant PG as PostgreSQL (FerretDB)\n    participant Dez as Debezium (WAL)\n    participant OS as OpenSearch\n\n    User->>UI: Trigger Bulk Status Update (50 issues)\n    UI->>Go: POST /actions/batch (Saga Request)\n    Go->>NATS: Publish BulkSagaCommand\n    Go-->>UI: 202 Accepted (Saga ID)\n    \n    loop Per Action in Batch\n        NATS->>Rust: Consume ActionMutateCommand\n        Rust->>Rust: Validate single-doc payload vs Schema KV\n        Rust->>PG: mongodb::Collection::update_one()\n        Rust->>NATS: Publish SagaProgressToken\n        NATS->>Go: Route token to connected socket\n        Go-->>UI: SSE Push: SAGA_PROGRESS\n    end\n\n    PG-->>Dez: Postgres WAL Logical Replication Event\n    Dez->>NATS: Publish raw DB change payload\n    NATS->>OS: Indexer Worker applies change to OpenSearch\n    OS->>NATS: Publish INDEXED event\n    NATS->>Go: Route to connected socket\n    Go-->>UI: SSE Push: SYNC_TOKEN (Triggers UI authoritative read)\n\n```\n\n---\n\n## 4. API Surfaces & Error Matrix\n\n### Route: `POST /api/v1/projects/{project_id}/actions`\n\n* **Headers**: `Authorization: Bearer <jwt>`, `X-Schema-Epoch: <number>`, `Idempotency-Key: <uuid>`\n* **Success Schema**:\n\n```json\n{\n  "data": {\n    "canonical_action": { "_id": "64d...", "status": "Open", "custom_fields": [...] },\n    "sync_token": "os_offset_892374"\n  }\n}\n\n```\n\n### Route: `POST /api/v1/projects/{project_id}/actions/batch`\n\n* **Description**: Initiates a multi-document Saga workflow. Database-level transactions are not used.\n* **Headers**: `Authorization: Bearer <jwt>`, `X-Schema-Epoch: <number>`, `Idempotency-Key: <uuid>`\n* **Success Schema**: `202 Accepted` returning `{ "saga_id": "saga_123" }`. Updates streamed via SSE.\n\n### HTTP Error Matrix\n\n| Status Code | Error Enum | Condition / Trigger | Client Action |\n| --- | --- | --- | --- |\n| `400` | `VALIDATION_FAILED` | Payload violates current authoritative server schema | Abort, show validation error, drop optimistic UI |\n| `401` | `UNAUTHORIZED` | Missing or invalid JWT | Redirect to login |\n| `403` | `FORBIDDEN` | Valid JWT, but lacking project RBAC permissions | Abort, show access error |\n| `409` | `STALE_SCHEMA_EPOCH` | `X-Schema-Epoch` is behind Server KV Epoch | Flush Wasm cache, refetch schema from KV, prompt retry |\n| `413` | `PAYLOAD_TOO_LARGE` | Mutation exceeds custom-field entity size limits | Abort, prompt user to reduce payload |\n| `429` | `RATE_LIMIT_EXCEEDED` | Request count exceeds tenant tier thresholds | Backoff based on `Retry-After` header |\n| `503` | `CDC_PIPELINE_STALLED` | DB write succeeds, OpenSearch indexer is stalled | Return 200 with `sync_token: null`. UI degrades to Tier 2 Wait |\n\n---\n\n## 5. Executable Acceptance Criteria (TDD-Ready)\n\n```gherkin\nFeature: CDC Pipeline Crash Isolation (OSI-Compliant Document Store)\n\n  Scenario: Rust worker crashes after primary-DB write but before any downstream signal\n    Given the Rust worker successfully persists an Action to PostgreSQL via FerretDB\n    And that write is durably recorded in the PostgreSQL WAL replication slot\n    When the Rust worker process crashes immediately after the DB acknowledges the write\n    Then the independent Debezium CDC connector must still emit the change to NATS JetStream\n    And the OpenSearch indexer must eventually index the Action without requiring worker recovery\n    And restarting the Debezium connector after its own crash must resume from its last durable WAL checkpoint\n\n```\n\n```gherkin\nFeature: Isomorphic Capability-Tagged Tier Degradation\n\n  Scenario: Ad-Hoc JQL relies on index-only features (Lucene Full-Text)\n    Given the user types ad-hoc JQL "description ~ \'server crash\'"\n    When the Wasm compiler processes the string locally\n    Then the resulting CompiledJqlArtifact must set "is_pure" to false\n    And the React client must NOT evaluate the Rhai script against optimistic payloads\n    And the React client must suppress optimistic board injection\n    And the system must rely on SSE Sync Tokens for data rendering\n\n```\n\n```gherkin\nFeature: Query Safety Invariant Enforcement\n\n  Scenario: Rust code attempts string concatenation for database queries\n    Given a Rust developer implements a filter using `format!("{{\\"{}\\": {}}}", key, val)`\n    When the CI pipeline executes standard static analysis/linting\n    Then the build MUST fail citing the `String Interpolation DB Query` anti-requirement\n    And require refactoring to use the `doc! { key: val }` BSON macro\n\n```\n\n```gherkin\nFeature: Single-Document Atomicity & Saga Distribution\n\n  Scenario: A batch update payload is received\n    Given a client sends a payload to update 50 Actions\n    When the Go API processes the request\n    Then the Go API must enqueue 50 distinct NATS Command Events\n    And return a 202 Accepted with a Saga ID\n    And the Rust workers must execute exactly 50 single-document update operations without starting a multi-document database transaction\n\n```\n\n---\n\n## 6. Implementation Task DAG (Chronological Milestones)\n\n* [ ] **M1: OSI-Compliant Storage & Event Infrastructure**\n* [ ] Provision PostgreSQL and FerretDB proxy containers.\n* [ ] Provision OpenSearch and NATS JetStream/KV clusters.\n* [ ] Deploy Debezium configured for PostgreSQL logical decoding (`pgoutput`), streaming to NATS.\n* [ ] Define the Rust `Action` and `CustomField` structs with `serde` and `bson` derives.\n\n\n* [ ] **M2: The Isomorphic JQL Compiler (Rust & Wasm)**\n* [ ] Build the `yaja-jql` Rust crate using `pest` or `nom`.\n* [ ] Implement the OpenSearch Query DSL emitter (Server-target).\n* [ ] Implement the Rhai script emitter with capability-tagging (`is_pure`) (Wasm/Server-target).\n* [ ] Expose the crate via `wasm-bindgen` and implement browser-based compilation unit tests.\n\n\n* [ ] **M3: Rust Core Workers & Saga Orchestration**\n* [ ] Implement single-document `insert_one`/`update_one` mutations using the official `mongodb` Rust driver (strictly utilizing `doc!` macros).\n* [ ] Implement NATS consumer logic for processing Saga commands (bulk updates).\n* [ ] Implement the OpenSearch indexing consumer driven by Debezium CDC payloads.\n\n\n* [ ] **M4: Polyglot API Gateway & SSE Sync Pipeline**\n* [ ] Build Go API Gateway HTTP routes (`POST /actions`, `POST /actions/batch`, `GET /search`).\n* [ ] Implement the Go SSE multiplexer bridging NATS `SYNC_TOKEN`, `SAGA_PROGRESS`, and `SCHEMA_ADVANCED` events.\n* [ ] Implement the `409 STALE_SCHEMA_EPOCH` and `429 RATE_LIMIT_EXCEEDED` middlewares in Go.\n\n\n* [ ] **M5: React Frontend, Wasm Integration & Optimistic UI**\n* [ ] Integrate the compiled `yaja-jql` Wasm module into the React build pipeline.\n* [ ] Implement React Query cache isolation: create an ephemeral `OverlayCache` distinct from the `QueryCache`.\n* [ ] Implement the Tier 0 (Inject) / Tier 1 (Suppress) injection logic driven by the Wasm `is_pure` flag and Rhai evaluation.\n* [ ] Wire the SSE event listener to flush the `OverlayCache`, trigger OpenSearch refetches, and update Saga progress bars.'

FILES['docs/reference/ADR-001-original.md'] = '# ADR-001: YAJA AI Engineering Protocol — Technical Specification\n\n## 1. System Overview & Invariants\n\n* **Objective**: A deterministic, machine-enforceable development and testing protocol for AI coding agents operating on the YAJA v0.2 codebase. This protocol guarantees that asynchronous CQRS boundaries and CDC pipelines are verified against physical infrastructure, preventing AI hallucination of successful mocked I/O, and enforces a strict 7-step verification-driven development loop.\n* **Target Stack**:\n* **Enforcement**: Bash (Git Pre-Commit Hooks), `ripgrep` (AST/Regex auditing).\n* **Infrastructure**: `docker-compose` (Ephemeral FerretDB, PostgreSQL, NATS, OpenSearch).\n* **Test Runners**: `cargo test` (Rust), `go test` (Go), `vitest` (React/Wasm).\n\n\n* **Critical Invariants**:\n* **Zero-Assumption Rule (The Spike Mandate)**: Development MUST NOT proceed based on unverified assumptions about network, infrastructure, or library behavior. If information cannot be gathered definitively, an executable Spike MUST be written and executed against a live local container before design begins.\n* **Dual-Track TDD Integration**:\n* *Track A (Pure Logic)*: Pure functions (e.g., Wasm JQL compilation) MUST be unit-tested in isolation.\n* *Track C (I/O Boundaries)*: Components interacting with Postgres, NATS, or OpenSearch MUST be tested via executable verification scripts against persistent local Docker instances.\n\n\n* **I/O Mocking Ban**: AI agents are strictly forbidden from mocking database layers, event buses, or CDC pipelines. The use of `mockall`, `jest.mock`, or similar stubbing tools in I/O-bound modules is a fatal violation.\n\n\n* **Anti-Requirements (MUST NOT)**:\n* Do NOT bypass the git pre-commit verification hook or ignore its output directives.\n* Do NOT use mocking libraries for integration tests or I/O boundary tests.\n* Do NOT mark a task as "done" if a test fails; failure is expected in Phase 2.4, and iterative execution MUST continue until the physical test passes.\n* Do NOT commit code without updating the relevant Markdown documentation to reflect architectural reality.\n\n\n\n---\n\n## 2. Data Contracts & Canonical Types\n\n```bash\n# Pre-Commit Hook Configuration (.githooks/ai_enforcer.json)\n# Defines the exact AST/Regex rules the AI must pass to commit code.\n\n```\n\n```json\n{\n  "rules": [\n    {\n      "id": "ERR_MOCK_IN_IO",\n      "forbidden_imports": ["mockall", "jest.mock", "httptest", "sqlmock"],\n      "trigger_contexts": ["mongodb", "nats", "opensearch", "ferretdb"],\n      "message": "FATAL: AI Mocking detected in I/O boundary. Read docs/ADR-001-AI-TESTING.md. Write an executable Spike against docker-compose."\n    },\n    {\n      "id": "ERR_NO_SPIKE_FOUND",\n      "required_files": ["spikes/active_spike.sh", "spikes/active_spike.rs"],\n      "trigger_condition": "When committing to /src/io without prior spike execution",\n      "message": "FATAL: Unverified assumption. Execute a spike before committing I/O logic."\n    }\n  ]\n}\n\n```\n\n```typescript\n// AI Agent Context State (In-Memory Tracking for Coding Agents)\nexport interface DevelopmentCycle {\n  readonly phase: \n    | "PLAN"             // 2.1 Declare goals & requirements\n    | "DESIGN"           // 2.2 Elegance, scalability, testability, security\n    | "TEST_DEV"         // 2.3 Write tests\n    | "TEST_EXEC_FAIL"   // 2.4 Execute tests (Failure Expected)\n    | "EXECUTION"        // 2.5 Implement feature code\n    | "TEST_EXEC_PASS"   // 2.6 Execute tests (Must Pass)\n    | "DOCS";            // 2.7 Update documentation\n  readonly activeSpikeRequired: boolean;\n  readonly activeSpikePassed: boolean;\n  readonly testMatrixStatus: Record<string, "PENDING" | "FAILED" | "PASSED">;\n}\n\n```\n\n---\n\n## 3. State Machine & Execution Flow\n\n### State Transition Matrix\n\n| Current State | Triggering Event | Next State | Guard Condition | Side Effects / Sidecars |\n| --- | --- | --- | --- | --- |\n| `PLAN` (2.1) | `REQUIREMENTS_DECLARED` | `DESIGN` | Target metrics (Performance, Security) defined | Spin up local `docker-compose` env |\n| `DESIGN` (2.2) | `IO_DEPENDENCY_DETECTED` | `SPIKE_DEV` | Logic touches NATS/Postgres/OS | Pause design, require active spike script |\n| `DESIGN` (2.2) | `PURE_LOGIC_ONLY` | `TEST_DEV` | Code is isomorphic/pure (e.g., JQL) | Scaffold unit tests |\n| `SPIKE_DEV` | `SPIKE_EXEC_SUCCESS` | `TEST_DEV` | Container returns 2xx / valid state | Record verifiable behavior, resume design |\n| `TEST_DEV` (2.3) | `TESTS_WRITTEN` | `TEST_EXEC_FAIL` | Tests cover elegance, scalability, security | Runner invoked |\n| `TEST_EXEC_FAIL` (2.4) | `TEST_FAILS` | `EXECUTION` | Red phase of TDD | AI begins actual feature implementation |\n| `EXECUTION` (2.5) | `CODE_COMPLETE` | `TEST_EXEC_PASS` | Git Hook passes (No banned mocks) | Re-run test suite |\n| `TEST_EXEC_PASS` (2.6) | `TEST_FAILS` | `EXECUTION` | Test output parsed | Apply Step 2.6.1: Fix execution or tests |\n| `TEST_EXEC_PASS` (2.6) | `TEST_PASSES` | `DOCS` | 100% pass rate achieved | Proceed to documentation |\n| `DOCS` (2.7) | `DOCS_UPDATED` | `DONE` | MD specs match code | Commit allowed |\n\n### Sequence Flow\n\n```mermaid\nsequenceDiagram\n    autonumber\n    Actor AI Agent\n    participant Git as Pre-Commit Hook\n    participant Docker as Ephemeral Infrastructure\n    participant Runner as Test Runner\n    participant Docs as Markdown Specs\n\n    AI Agent->>Git: git commit -m "feat: NATS saga dispatcher"\n    Git->>Git: Scan for [\'mockall\', \'testify/mock\']\n    alt I/O Mocking Detected\n        Git-->>AI Agent: REJECTED (ERR_MOCK_IN_IO)\n        Note right of AI Agent: Agent reads ADR-001\n        AI Agent->>Docker: Write & Execute Spike against NATS\n        Docker-->>AI Agent: Real NATS Subject Ack\n    else Pure Code / Valid Spike\n        Git->>Runner: Execute test suite (Step 2.6)\n        alt Tests Fail\n            Runner-->>AI Agent: REJECTED (Step 2.6.1: Fix logic)\n        else Tests Pass\n            Runner->>Docs: Verify doc checksums updated (Step 2.7)\n            Docs-->>Git: Ack\n            Git-->>AI Agent: Commit Accepted\n        end\n    end\n\n```\n\n---\n\n## 4. API Surfaces & Error Matrix\n\n### System Interface: `.git/hooks/pre-commit` (AI Audit Layer)\n\n* **Standard Out**: Machine-readable violation codes intended to instruct the AI\'s next prompt action. The hook outputs terminal commands for the AI to execute.\n* **Failure Matrix (AI Action Routing)**:\n\n| Exit Code | Error Enum | Condition / Trigger | Client Action |\n| --- | --- | --- | --- |\n| `1` | `ERR_MOCK_IN_IO` | AI used a mocking library in a file importing DB/Event drivers. | Delete the mock. Run `cat docs/ADR-001.md`. Create a spike script in `spikes/` hitting the local Docker environment. |\n| `2` | `ERR_UNVERIFIED_ASSUMPTION` | New dependency introduced without a corresponding spike or architectural doc update. | Stop coding. Formulate a hypothesis, write a spike to test the dependency, execute it. |\n| `3` | `ERR_TEST_EXECUTION_FAILED` | TDD loop violation: Attempting to commit before Step 2.6 is fully green. | Read test logs. Apply fix to application code (or correct the test assertions). Re-run. |\n| `4` | `ERR_DOCS_STALE` | Code changed in `src/` but no corresponding change in `docs/` or `*.md`. | Execute Step 2.7. Update documentation to reflect the new implementation realities. |\n\n---\n\n## 5. Executable Acceptance Criteria (TDD-Ready)\n\n```gherkin\nFeature: Pre-Commit Contract Enforcement\n\n  Scenario: AI attempts to mock the CDC Pipeline (Debezium/NATS)\n    Given the AI agent is in the "EXECUTION" phase for the "Saga Orchestration" module\n    And the module imports the official "async-nats" Rust crate\n    When the AI agent writes a test using "mockall" to simulate a NATS message\n    And attempts to commit the code to the repository\n    Then the pre-commit hook must intercept the action\n    And exit with code 1 (ERR_MOCK_IN_IO)\n    And output "FATAL: AI Mocking detected. cat docs/ADR-001.md"\n    And the commit must be aborted\n\n```\n\n```gherkin\nFeature: Verification-Driven Development (Spike Mandate)\n\n  Scenario: Information cannot be gathered from standard web knowledge\n    Given the AI agent needs to implement OpenSearch CQRS projection\n    And the exact mapping of FerretDB BSON to OpenSearch JSON is unknown\n    When the AI agent reaches Step 2.1 (Plan)\n    Then the AI MUST NOT hallucinate the mapping format\n    And MUST generate a standalone script in "spikes/os_mapping_test.sh"\n    And MUST execute the script against the local Docker cluster to observe the real output\n    Before proceeding to Step 2.2 (Design)\n\n```\n\n---\n\n## 6. Implementation Task DAG (Chronological Milestones)\n\n* [ ] **M1: Core Repository & ADR Documentation**\n* [ ] Initialize git repository and create the `.githooks` directory.\n* [ ] Configure git to use the custom hooks path (`git config core.hooksPath .githooks`).\n* [ ] Save this specification document as `docs/ADR-001-AI-TESTING.md`.\n\n\n* [ ] **M2: Infrastructure Scaffolding (The Spike Target)**\n* [ ] Create `docker-compose.yml` containing FerretDB, PostgreSQL, OpenSearch, and NATS JetStream.\n* [ ] Create a `spikes/` directory with a `README.md` defining the Spike format (Executable isolated scripts that self-destruct or output raw stdout).\n* [ ] Write a health-check script that the AI can run to verify all containers are accepting connections.\n\n\n* [ ] **M3: The AI Pre-Commit Hook**\n* [ ] Write the `pre-commit` Bash script implementing the `ripgrep` regex bans for mocking libraries.\n* [ ] Map the exit codes to explicit CLI instructions telling the AI to read `ADR-001`.\n\n\n* [ ] **M4: Project Directory Scaffold (Track A vs Track C)**\n* [ ] Create `src/pure/` (Wasm, JQL parsers) where the git hook allows unit tests and mocks.\n* [ ] Create `src/io/` (Go SSE, Rust NATS consumers) where the git hook strictly enforces Spike-driven integration tests.'

FILES['CODE_OF_CONDUCT.md'] = FILES['CODE_OF_CONDUCT.md'].split('+++', 2)[2].lstrip().replace('[INSERT CONTACT METHOD]', 'the private collaboration channel used to contact the repository owner. If no channel is available, request a private reporting method in an issue without disclosing incident details')


def run(command, root, timeout=900):
    print("SCAFFOLD:", " ".join(command), flush=True)
    return subprocess.run(command, cwd=root, check=True, timeout=timeout)


def generate(root):
    """Preflight every destination before writing; never overwrite user work."""
    conflicts = []
    for relative, content in FILES.items():
        path = root / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
            conflicts.append(relative + " (symlink)")
        elif path.exists() and (not path.is_file() or path.read_bytes() != content.encode("utf-8")):
            conflicts.append(relative)
    if conflicts:
        raise RuntimeError("Refusing to overwrite differing files: " + ", ".join(conflicts))
    for relative, content in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content.encode("utf-8"))
    hook = root / ".githooks/pre-commit"
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Generated {len(FILES)} complete repository files.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-only", action="store_true", help="Write files only; does not certify or commit")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if root != Path(__file__).resolve().parent:
        raise RuntimeError("Run scaffold.py from the directory containing it")
    generate(root)
    if args.generate_only:
        print("Generation only: infrastructure, Git, tests, and commit are not yet verified.")
        return
    if not (root / ".git").exists():
        run(["git", "init", "-b", "main"], root)
    actual_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=root, text=True).strip()
    if Path(actual_root).resolve() != root:
        raise RuntimeError("The target must be its own Git repository")
    for identity in ("user.name", "user.email"):
        if subprocess.run(["git", "config", "--get", identity], cwd=root, stdout=subprocess.DEVNULL).returncode:
            raise RuntimeError(f"Configure your Git {identity} before retrying; no identity will be invented")
    # Refuse to include unrelated files in the requested 'stage all' operation.
    candidates = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root)
    unexpected = {p for p in candidates.decode("utf-8").split("\0") if p} - set(FILES) - {"scaffold.py", "Cargo.lock"}
    if unexpected:
        raise RuntimeError("Unrelated files would be staged: " + ", ".join(sorted(unexpected)))
    run([sys.executable, "scripts/setup_env.py", "--start"], root)
    run(["cargo", "generate-lockfile", "--offline"], root)
    run([sys.executable, "scripts/verify.py"], root)
    run(["git", "add", "--all"], root)
    run(["git", "update-index", "--chmod=+x", ".githooks/pre-commit"], root)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode:
        run(["git", "commit", "-m", "feat: initial repository scaffold with ADR-001 compliance"], root)
    else:
        print("Baseline already committed; no new commit needed.")
    hooks = subprocess.check_output(["git", "config", "--get", "core.hooksPath"], cwd=root, text=True).strip()
    if hooks != ".githooks":
        raise RuntimeError("Hook path verification failed")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root).strip():
        raise RuntimeError("Working tree is not clean after commit")
    run(["git", "log", "-1", "--format=%h %s"], root)
    print("Verified: live infrastructure, tests, staged hook, recorded commit, clean working tree.")
    print("git remote add origin <YOUR_GITHUB_REPO_URL>")
    print("git push -u origin main")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"SCAFFOLD_FAILED: {error}", file=sys.stderr)
        sys.exit(1)
