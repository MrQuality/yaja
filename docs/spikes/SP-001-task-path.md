# SP-001 — First task create/update/read path

| Field | Value |
| --- | --- |
| Status / outcome | Planned / no experiment results |
| Owner / assessor | To assign before execution; may be the same maintainer during the sole-contributor phase |
| Created / last updated | 2026-09-25 |
| Related work | [B-002](../product/backlog.md#b-002), [R-001](../product/requirements.md#r-001), [D-015](../product/decisions.md#d-015) |
| Questions | [Q-001](../product/open-questions.md#q-001), [Q-002](../product/open-questions.md#q-002), [Q-019](../product/open-questions.md#q-019) |
| Effort limit / stopping condition | Effort limit to set; stop when the bounded path has sufficient evidence for a design recommendation or a specific blocker/inconclusive result is recorded |
| Prior evidence | [Current implementation and limitations](../IMPLEMENTATION.md); connection checks do not establish durable delivery |

Use the approved [spike procedure](README.md). B-002 remains the source for the
task's acceptance criteria; this record will hold its cases, evidence, and handoff.

## Question and scope

Can the reference stack support one locally usable task create/update/read path,
with explicit save, delivery, visibility, error, and recovery contracts?

Start with PostgreSQL through FerretDB, NATS, OpenSearch, and the reference CDC
approach. Validate database mapping and event connections with actual services.
An engine comparison, production capacity benchmark, full UI, complete resource
lifecycle, and Kubernetes are outside this spike. Record prerequisites for later
consistent resource releases and cost adjustments without implementing that scope.

The existing stack is a hypothesis to investigate. Delayed query visibility and
retries need explicit behavior. No replacement architecture or stalled-pipeline
HTTP response has been selected by this record.

## Proposed cases

Freeze fixture shape, workload size, versions, and timing limits before execution.
Resolve the stalled-pipeline response before implementing/testing that route.

| Case | Variable / condition | Expected observation | Current state |
| --- | --- | --- | --- |
| C01 | Create, update, read one synthetic task | Defined fields and versions survive the round trip; save and query visibility are recorded separately | Not run |
| C02 | Worker stops immediately after acknowledged save | Independent change capture eventually delivers the saved change | Not run |
| C03 | CDC stops and restarts with its durable state retained | Resume from checkpoint; saved changes are not lost | Not run |
| C04 | Duplicate delivery or retry of the same operation | No duplicated logical effect; operation identity and acknowledgment rules are explicit | Not run |
| C05 | Indexer stalled, then resumed | Defined pending/error response, followed by correct search visibility; no write authorization dependency on search | Not run |
| C06 | Competing updates to one task | Defined conflict/version behavior, without silent loss of an accepted update | Not run |

For C02-C05, define a deterministic interruption point and observable event
identity/version before testing. Record expected ordering and any time bound
instead of relying on arbitrary sleeps. Add narrowly scoped cases only when
needed to settle the linked questions.

## Environment and reproduction

All application and supporting services run in Podman containers. Test commands
run on the host/CI runner. Verify `podman-compose` as the selected provider.
The existing Compose stack contains four supporting services; CDC and the
applicable API/worker path still need experimental implementation. The current
Docker CI job does not establish Podman compatibility.

Preflight must check current resources, software versions, Podman/Compose,
WSL/Linux runtime where applicable, ports, image access, and OpenSearch settings.
The historical workstation observations in B-002 are not a fresh passing check.
Size the expanded stack before starting its workload. Identify any missing host
tools according to where builds and tests will actually run.

No spike runner, fixtures, images, or reproduction commands have been created.
Use `experiments/SP-001/` when adding executable artifacts, with isolated data,
explicit timeouts, and cleanup scoped to the run. Record actual tested versions
and commands here once available. Preserve required data during restart cases.

## Run summaries

None. Prior workstation inspection is preparation, not integration evidence.

## Conclusion and reuse boundary

No conclusion yet. Results will apply only to the observed stack versions,
configuration, platform, workload, and failure cases. Database mapping, CDC,
delivery or projection changes require reconsidering the affected evidence.

## Decision and follow-up

No new decision accepted. Link any resulting D-record and update the affected
Q-records after review. B-002 requires a concrete design and evidence, even if
this spike concludes that part of the reference path needs revision.

## Handoff

- Completed: initial scope, candidate cases, environment constraints, and record.
- Blockers: preflight not run for execution; owner/effort limit, fixture and timing
  limits, runtime/access choices, and stalled-pipeline response remain to settle.
- Next action: perform static resource/software preflight, record gaps, and set
  the bounded experiment plan before bootstrapping services. Capture the first
  attempted run as `SP-001-R01`, including blocked cases when applicable.
