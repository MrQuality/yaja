# Implementation scope and acceptance evidence

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
