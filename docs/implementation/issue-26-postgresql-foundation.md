# Native PostgreSQL foundation: local implementation plan

Status: In progress, 2026-10-10. Related: #26/B-005, #39, #40, #41.
Base: main at 12871228bae3a1b6a45b08f188741a18631ac5d7.
Work is local only; no push, issue edit or PR update is authorized for this slice.
GitHub #26 is closed despite outstanding production deliverables; preserve that
remote state until the maintainer authorizes tracking updates. #39 remains open.

## Pre-Execution Plan

1. **Goal & Context:** Turn the reviewed project-creation schema into a versioned,
   atomic native PostgreSQL foundation with explicit ownership and service-role
   privileges. Install the corrected payload identity guard. Record selected
   representation choices without claiming an authenticated creation route.
2. **Definition of Done:**
   - [ ] Record native version-one codec/identifier choices and remaining alignment obligations.
   - [ ] Provide executable installation SQL for operations, creation/configuration/history and restricted service roles.
   - [ ] Installation is transactional and rejects unsupported servers, encoding, existing schemas or colliding roles rather than silently adopting them.
   - [ ] Real database checks cover install/reinstall/failure rollback, scalar/target constraints, payload identity/shape, irreversible retirement, history protection and serving-role privileges.
   - [ ] Required staged checks and an evidence-based review pass; documentation distinguishes completed foundation from outstanding adapters/routes and native Linux verification.
3. **Dependencies & Prerequisites:** PostgreSQL 16 UTF8, a fresh dedicated database
   and deployment administrator, Python 3.10+, existing toolchain and Podman only
   for local services. No new Python driver or external package is required.
   Native checks retain 3 GiB available host memory and bounded container resources.
4. **Risks & Mitigations:** Separate NOLOGIN ownership/service roles; no credentials
   or actor fixtures in installation. Fix SECURITY DEFINER search_path and revoke
   PUBLIC execution. Unique SQL ownership and transactional installation prevent
   partial state. Never migrate/delete legacy FerretDB data or rewrite spike evidence.
   Test actual SQLSTATEs and committed state, including privileged reassignment.
5. **Spikes & Open Questions:** No further engine spike. #40/#41 remain route
   dependencies; trusted clock, compaction, duplicate-key ingress, production
   codecs/adapter and coordinated native domain/interface/import validation remain
   delivery obligations. The identifier choice applies to new native persistence;
   legacy acceptance and historical reconstruction must not be silently narrowed.
6. **High-Level Architecture / File Changes:** storage/postgresql/ owns install SQL
   and ordered schema fragments. tests/integration/ owns native acceptance SQL;
   a Podman verification command uses isolated labelled resources and no networking.
   Architecture/implementation/testing docs record installation and scope.
7. **Verification & Testing Plan:** Write native cases before SQL and retain their
   expected failure. Run real PostgreSQL install/negative/role tests, including a
   mutation that removes the payload guard and must fail the regression. Verify
   rollback leaves no schema/roles after injected installation failure. Run staged
   verification with development services, inspect final changes and preserve local
   evidence. Stop the runtime when finished. No hosted CI is claimed for local work.

## Selected representation and enforcement boundary

The maintainer authorized this local progression on 2026-10-10 after SP-003 review.
Use version-one domain-separated binary request bytes with SHA-256; use separate
versioned JSONB saved-result/configuration envelopes and canonical decimal strings
for u64 fields. Stored-version dispatch and direct hashing dependency ownership
must be implemented before promoting the prototype into the production adapter.

New native opaque identifiers are nonempty UTF8, at most 128 bytes, without NUL;
identity uses C collation with no normalization or trimming. Operation tokens keep
the existing ASCII-graphic rule. This is a native storage contract, not permission
to silently change public String-backed wrappers or import existing values.
Authoritative native domain/interface/import enforcement must be aligned before
any supported native command path is exposed. Do not validate historical decoding
against today's mutable domain rules. Preserve the exact 90-day recorded-time
replay policy with no grace or post-commit adjustment.

## Delivery boundaries

Foundation installation provides structural integrity and database capability
separation. It does not prove a trusted seed, permission mapping or exact replay
reconstruction by an application. Those require the production codec/adapter and
#40/#41 integrations. Creation-only guards remain explicit until later migrations
supply replacement invariants. No serving compaction/revocation path is granted.
