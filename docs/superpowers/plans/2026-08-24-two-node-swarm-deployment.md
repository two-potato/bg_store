# Two-Node Swarm Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run Servio as a two-node Docker Swarm stack and deploy immutable GHCR images automatically from GitHub Actions.

**Architecture:** `188.225.37.132` is the single Swarm manager/core node and public ingress for `24sparts.ru`; `192.168.0.5` is the worker. GitHub Actions builds SHA-tagged application images in GHCR, then SSHes to the manager and performs `docker stack deploy --with-registry-auth`.

**Tech Stack:** Docker Engine, Docker Swarm, Docker Stack/Compose v3, GHCR, GitHub Actions, nginx, Django/Gunicorn, Celery, PostgreSQL, Redis, OpenSearch.

**Spec:** `docs/superpowers/specs/2026-08-24-two-node-swarm-deployment-design.md`

## Global Constraints

- Production domain is `24sparts.ru`.
- Swarm manager is `188.225.37.132` and uses a private `192.168.0.0/24` address for cluster traffic.
- Worker private address is `192.168.0.5`.
- Stateful services remain pinned to the core node.
- GitHub Actions builds and pushes immutable SHA-tagged images; production hosts do not build application images during deploy.
- Swarm ports 2377/tcp, 7946/tcp+udp and 4789/udp are restricted to the private network.

---

### Task 1: Production Swarm Stack

**Files:**
- Create: `deploy/swarm/stack.yml`
- Create: `deploy/swarm/nginx.conf`

**Interfaces:**
- Consumes: existing Dockerfiles and production environment variables.
- Produces: stack `servio`; overlay networks `servio_public`, `servio_backend`; core/worker placement constraints.

- [ ] Define services using `${IMAGE_TAG}` and `${IMAGE_PREFIX}` image references.
- [ ] Pin PostgreSQL, Redis, OpenSearch, nginx, backend, frontend, beat and bots to `node.labels.servio.role == core`.
- [ ] Pin Celery worker to `node.labels.servio.role == worker`.
- [ ] Add rolling update/restart policies and persistent named volumes.
- [ ] Configure nginx for `24sparts.ru`, TLS and Swarm service DNS.
- [ ] Validate stack syntax with `docker stack config -c deploy/swarm/stack.yml` on a Docker host.

### Task 2: Swarm Bootstrap and Deployment Scripts

**Files:**
- Create: `scripts/swarm_bootstrap_manager.sh`
- Create: `scripts/swarm_bootstrap_worker.sh`
- Create: `scripts/swarm_deploy.sh`
- Create: `scripts/swarm_healthcheck.sh`
- Create: `scripts/swarm_rollback.sh`

**Interfaces:**
- Consumes: private manager address, worker join token, `${IMAGE_TAG}`, `/opt/servio/shared/.env.prod`.
- Produces: initialized cluster, node labels, stack rollout, `.deploy/current-sha`, `.deploy/previous-sha`.

- [ ] Make bootstrap scripts idempotent where Docker permits.
- [ ] Validate required env/files before deploying.
- [ ] Deploy with `docker stack deploy --with-registry-auth --prune`.
- [ ] Wait for required replicas and HTTPS health endpoint.
- [ ] Record current/previous SHA only after a successful rollout.
- [ ] Implement rollback by redeploying the recorded previous SHA.
- [ ] Run `bash -n` on every shell script.

### Task 3: GitHub Actions CI/CD

**Files:**
- Modify: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: GitHub token/packages permission plus `PROD_SSH_*`, `PROD_APP_DIR` secrets.
- Produces: GHCR images tagged with commit SHA and a remote Swarm rollout.

- [ ] Trigger production workflow on `codex/all-local-changes-20260331-110158` and manual dispatch.
- [ ] Validate shell/YAML deployment assets before image publication.
- [ ] Login to GHCR and build/push backend, frontend, bot, search-api and recommendation-api images.
- [ ] SSH to the manager, fetch/reset the exact commit SHA, and invoke `scripts/swarm_deploy.sh` with `IMAGE_TAG=${{ github.sha }}`.
- [ ] Use workflow concurrency to prevent overlapping production deployments.

### Task 4: Production Domain Defaults and Operations Documentation

**Files:**
- Modify: `backend/.env.prod.example`
- Create: `deploy/swarm/README.md`

**Interfaces:**
- Consumes: actual server topology and GitHub secret names.
- Produces: exact bootstrap commands and deployment prerequisites.

- [ ] Change production example hosts/origins to `24sparts.ru`.
- [ ] Document manager and worker bootstrap commands.
- [ ] Document required GitHub repository secrets/permissions.
- [ ] Document GHCR login requirement, production env path, TLS directory and rollback command.
- [ ] Document verification commands: `docker node ls`, `docker stack services servio`, `docker stack ps servio`, and HTTPS health check.
