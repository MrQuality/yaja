# Contributing to YAJA

Keep changes focused and explain the problem they solve. Discuss architectural
changes in an issue before implementing them. Follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Setup and testing

Follow the [development setup](README.md#development-setup), then run:

```text
python scripts/verify.py
```

Use `python scripts/verify.py --pure` when working on pure logic without the
development services. Integration changes need the full suite against running
services. See [the testing guide](docs/TESTING.md) for coverage and limitations.

Add tests for changed behavior and relevant failure cases. Update documentation
when commands, contracts, or supported behavior change. Run `cargo fmt --all`
and `gofmt` on changed Rust and Go files.

Pure Rust code lives in `src/pure/` and adapters in `src/io/`. Go uses `go/pure/`
and `go/io/`. Add new Go modules to `go.work` and the test runner.

## Pull requests and review

Describe the resulting behavior, tests run, and any remaining limitations.
Include relevant service versions and results for integration changes. Keep
credentials, local environment files, and unrelated changes out of the PR.

The local commit hook tests staged source files in an isolated directory. Stage
test fixes before retrying a failed commit. CI runs the full suite for pull
requests and pushes to `main`.

Changes to `main` require passing CI and one approving review. The maintainer
reviews changes to architecture, dependencies, CI, and test coverage. Do not
bypass required review. Ownership is recorded in `.github/CODEOWNERS`.

## License and attribution

Contributions are licensed under Apache-2.0. Retain third-party license notices
and credit contributors using their preferred public name or handle. Report
vulnerabilities privately through [SECURITY.md](SECURITY.md).