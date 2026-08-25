# Security Policy

Security is a release gate for `zkids`; security controls must not be bypassed to obtain a passing build.

## Supported versions

| Version | Status |
| --- | --- |
| 1.0.x | Supported |
| 0.x | Upgrade recommended |

## Reporting a vulnerability

Do not disclose exploitable vulnerabilities in public issues, pull requests, discussions, logs, analytics events, or commit messages. Use GitHub private vulnerability reporting/security advisories when enabled, or an agreed private channel with the repository owner.

Include affected versions/commits, reproduction details, impact, prerequisites, and suggested remediation when available. Never include real provider credentials in a report.

## Trust boundaries

- Browser/control-plane callers are untrusted until authenticated and authorized.
- Tenant identifiers come from signed authentication claims, not request payload authority.
- Provider and publisher credentials are environment-only and must never be persisted in episode/job/analytics/publication records.
- Media providers, S3-compatible storage, PostgreSQL, Redis and publishing destinations are external trust boundaries.
- Generated media and provider responses remain untrusted until validation/QC succeeds.

## Publication invariant

Publication must fail closed. A publish operation requires all of:

1. authenticated actor with `approve_publish` permission;
2. episode state `HUMAN_PUBLISH_APPROVED`;
3. explicit `human_approved=true`;
4. `approved_by` bound to the authenticated actor;
5. tenant-scoped idempotency key preventing replay/duplicate publication.

Generation, packaging, render completion, analytics performance, or automated QC must never imply publish approval.

## Data isolation and analytics

- Episode/job/control-plane records are tenant-scoped.
- Character versions, storyboards, QC reviews, analytics, variants and publications are tenant-scoped.
- Analytics event IDs are idempotent within a tenant.
- Do not ingest secrets, authentication tokens, children's personal data, or unnecessary identifiers into analytics payloads.

## Supply chain and CI

- Keep CodeQL, dependency review, Ruff, strict mypy, Bandit, pytest, offline E2E, Docker build and Compose validation enabled.
- Use least-privilege GitHub Actions permissions.
- Review Dependabot/security findings before release.
- CI uses fake/local providers and must not perform paid generation or external publishing.
- Never commit credentials, private keys, production `.env` files or provider responses containing secrets.

## Deployment

- Replace all development credentials before exposing a deployment.
- Enable `ZKIDS_AUTH_SECRET` for production control-plane access.
- Restrict PostgreSQL, Redis and object storage to private/trusted networks.
- Terminate TLS at the deployment ingress and require HTTPS for external provider/publisher endpoints.
- Apply database migrations before switching application traffic to a release that depends on them.
- Back up publication metadata and audit records before destructive rollback.

## Incident handling

Contain affected credentials/accounts first, disable external publishing when publication integrity is uncertain, preserve audit evidence, rotate exposed credentials through the provider, validate tenant boundaries, patch and rerun all release gates, then restore service. Reverting the final-release merge commit returns the codebase to the v0.2 baseline; metadata tables from `0002_final_release.sql` can remain read-only until safely archived or removed.
