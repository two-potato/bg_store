# Production Readiness — 24sparts.ru

This document records the release gates for the two-node Docker Swarm production environment.

## Mandatory release gates

- Production candidate contains current `dev` (`git merge-base --is-ancestor origin/dev HEAD`).
- CI is green: backend pytest/coverage, Django production checks, Ruff, storefront builds/typecheck, browser smoke, visual regression, Swarm stack rendering and migration safety checks.
- Security Audit is green for backend, bot, legacy npm project and Next.js frontend.
- Both Swarm nodes are Ready and labeled (`servio.role=core`, `servio.role=worker`).
- Production secrets contain no placeholders.
- Public `/health/` returns Django dependency readiness; `/nginx-health` is nginx-only liveness.
- Database migrations run once as a release phase, not inside application startup.
- Rollback is code-only; schema changes follow expand/contract compatibility.
- PostgreSQL backup succeeds locally and copies successfully to `192.168.0.5`; a restore drill is performed before declaring the backup path operational.
- Production deployment is explicit (`workflow_dispatch` or a `prod-*` tag), never automatic on a feature-branch push.

## Production topology

- Manager/core: `192.168.0.4` (`188.225.37.132` public), 4 CPU / 8 GB RAM.
- Worker: `192.168.0.5`, 2 CPU / 2 GB RAM.
- Stateful services stay on core.
- Celery worker and primary observability services run on worker.
- node-exporter and cAdvisor run globally.

## Release evidence

Do not assign a final readiness score of 90% or higher until the final candidate SHA has fresh successful CI and Security Audit runs and the server-side bootstrap/first-deploy smoke checks have been executed.
