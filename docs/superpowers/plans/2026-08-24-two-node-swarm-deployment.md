# Two-Node Swarm Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the `codex/all-local-changes-20260331-110158` branch to production-grade deployment readiness on a two-node Docker Swarm cluster with gated CI/CD, dependency-aware health checks, safe release migrations, rollback, remote backups, and baseline observability.

**Architecture:** `188.225.37.132` / `192.168.0.4` is the single Swarm manager/core node and public ingress for `24sparts.ru`; `192.168.0.5` is the worker. GitHub Actions must run the application verification suite before publishing SHA-tagged images to GHCR and invoking a controlled release phase on the manager. Stateful services stay pinned to core; asynchronous work and observability run on the worker with explicit resource limits.

**Tech Stack:** Docker Engine, Docker Swarm, Docker Stack/Compose v3, GHCR, GitHub Actions, nginx, Django/Gunicorn, Celery, PostgreSQL 16, Redis 7, OpenSearch 2.19.1, Prometheus, Grafana, Alertmanager.

**Spec:** `docs/superpowers/specs/2026-08-24-two-node-swarm-deployment-design.md`

## Global Constraints

- Production domain is `24sparts.ru`; `www.24sparts.ru` is supported only when DNS exists and must be included in the same certificate.
- Swarm manager private address is `192.168.0.4`; worker private address is `192.168.0.5`.
- Stateful services remain pinned to the core node.
- GitHub Actions builds and pushes immutable SHA-tagged images; production hosts do not build application images during deploy.
- A production deploy may not run before backend tests, production settings checks, Ruff, frontend typecheck/build, deployment validation, and browser smoke succeed.
- Database migrations execute as a distinct release phase; application containers never run `migrate` in their normal startup command.
- Public health used by CI must proxy to dependency-aware Django readiness, not a static nginx response.
- Destructive migration operations require an explicit override and must not silently enter production.
- Swarm ports 2377/tcp, 7946/tcp+udp and 4789/udp are restricted to the private network.
- PostgreSQL backups must be copied off the manager to `192.168.0.5`.

---

### Task 1: Dependency-aware application health

**Files:**
- Modify: `backend/core/views/system.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/tests/test_health_and_metrics.py`
- Modify: `deploy/swarm/nginx.conf`

**Interfaces:**
- Produces: `/health/` liveness and `/ready/` dependency readiness; public `/health/` is routed by nginx to Django `/ready/`.

- [x] Add tests for healthy readiness, database failure and cache failure.
- [x] Implement readiness checks against the configured Django database and cache.
- [x] Expose `/ready/` independently from liveness.
- [ ] Route production nginx `/health/` to backend `/ready/` and expose a separate `/nginx-health` static probe.

### Task 2: Production Swarm stack hardening

**Files:**
- Modify: `deploy/swarm/stack.yml`
- Create: `deploy/swarm/prometheus.yml`
- Create: `deploy/swarm/alertmanager.yml`
- Create: `deploy/swarm/grafana-datasources.yml`

**Interfaces:**
- Produces: healthchecked services, explicit replica controls, memory/CPU limits, and a worker observability baseline.

- [ ] Remove migration execution from backend startup.
- [ ] Add container healthchecks for backend, PostgreSQL, Redis, OpenSearch and bots.
- [ ] Add explicit resource limits/reservations for the 4/8 core and 2/2 worker.
- [ ] Add Prometheus, Grafana, Alertmanager and global node-exporter services with worker placement where appropriate.
- [ ] Keep search/recommendation sidecars disabled until explicitly enabled.

### Task 3: Safe migration and release phase

**Files:**
- Modify: `scripts/swarm_deploy.sh`
- Create: `scripts/check_migration_safety.sh`

**Interfaces:**
- Consumes: current/previous deployment SHA and production env.
- Produces: preflight validation, migration plan, one-off migration execution, static collection, rollout and recorded deployment metadata.

- [ ] Reject destructive migration patterns unless `ALLOW_RISKY_MIGRATIONS=1` is explicitly provided.
- [ ] Validate production env placeholders before touching the stack.
- [ ] Wait for stateful dependencies before running migrations.
- [ ] Execute `manage.py migrate --plan` and `manage.py migrate --noinput` in a one-off release container.
- [ ] Run `collectstatic` in the release container.
- [ ] Only mark a SHA successful after application readiness passes.

### Task 4: CI gate before image publication/deploy

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy.yml`

**Interfaces:**
- Produces: deployment branch receives the same verification as dev/main; deploy workflow has a verification job that must succeed before build/push/deploy.

- [ ] Include `codex/all-local-changes-20260331-110158` in CI triggers.
- [ ] Run backend tests, production settings check, Ruff, frontend typecheck/build and browser smoke before publish/deploy.
- [ ] Validate shell syntax and `docker stack config` using temporary env files.
- [ ] Add a branch drift guard requiring current `dev` to be an ancestor of the production candidate.
- [ ] Build/push images only after verification succeeds.

### Task 5: Swarm-aware PostgreSQL backup and off-node copy

**Files:**
- Create: `scripts/swarm_backup_postgres.sh`
- Create: `scripts/install_swarm_backup_cron.sh`

**Interfaces:**
- Consumes: `servio_db` task, `/opt/servio/shared/.env.prod`, SSH access to `root@192.168.0.5`.
- Produces: compressed local dump, retention cleanup, remote copy and freshness marker.

- [ ] Locate the active PostgreSQL task without Docker Compose.
- [ ] Run `pg_dump` inside the task and gzip atomically.
- [ ] Copy completed dumps to the worker and enforce retention locally and remotely.
- [ ] Install a daily cron entry and preserve the existing freshness-check contract.

### Task 6: TLS and domain consistency

**Files:**
- Modify: `scripts/swarm_deploy.sh`
- Modify: `backend/.env.prod.example`
- Modify: `deploy/swarm/README.md`

**Interfaces:**
- Produces: certificate SANs match configured production hosts.

- [ ] Detect whether `www.24sparts.ru` resolves before requesting it.
- [ ] Issue/renew a certificate covering every configured public host that resolves.
- [ ] Keep nginx and Django host/origin defaults aligned.

### Task 7: Rollback and deployment diagnostics

**Files:**
- Modify: `scripts/swarm_healthcheck.sh`
- Modify: `scripts/swarm_rollback.sh`
- Modify: `deploy/swarm/README.md`

**Interfaces:**
- Produces: readiness-based rollout verification, task diagnostics on failure, code rollback to previous immutable image.

- [ ] Verify required replicas and Docker health status where available.
- [ ] Query real public Django readiness through nginx.
- [ ] Print stack/service/task diagnostics on failure.
- [ ] Document that schema rollback is not automatic and production migrations follow expand/contract compatibility.

### Task 8: Synchronize production candidate with dev

**Files:**
- Git history only.

**Interfaces:**
- Consumes: current `dev` head.
- Produces: production candidate containing all current dev fixes plus Swarm hardening.

- [ ] Merge `dev` into `codex/all-local-changes-20260331-110158` without discarding production hardening.
- [ ] Resolve conflicts explicitly if GitHub cannot perform the merge automatically.
- [ ] Re-run comparison and confirm the candidate is no longer behind `dev`.

### Task 9: Verification and release readiness review

**Files:**
- All files above.

**Interfaces:**
- Produces: evidence-backed release readiness rating.

- [ ] Run/inspect CI for the final candidate SHA.
- [ ] Verify shell syntax, stack rendering, image builds and application tests.
- [ ] Review the final diff for critical/important deployment defects.
- [ ] Do not claim production readiness until verification evidence is available.
