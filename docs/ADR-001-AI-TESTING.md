# ADR-001: YAJA AI Engineering Protocol

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
uses the same staged-change contract by pointing HEAD to an unborn branch only
in its disposable clone before invoking the hook. This preserves the index and
keeps detached SHA checkouts valid Git repositories. A regression test exercises
the detached initial-push path and checks that the original checkout is unchanged.

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
