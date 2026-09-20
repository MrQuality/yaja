# Security policy

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
