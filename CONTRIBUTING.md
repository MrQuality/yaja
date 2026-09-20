# Contributing to YAJA

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
