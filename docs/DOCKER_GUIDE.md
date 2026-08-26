# Docker Guide

## Compose Layers

The root Compose files are for local development, CI and single-host production-like testing. They are **not** the source of truth for the real `24sparts.ru` deployment.

- `docker-compose.yml` — base local/CI services
- `docker-compose.dev.yml` — local development overrides
- `docker-compose.prod.yml` — single-host production-like compatibility overlay
- `docker-compose.metrics.yml` — local/CI observability overlay

## Typical Local Run

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Production-like Compose Validation

Use this only to validate production settings on one host; do not use it to deploy the real production cluster:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend frontend bot
```

## Real Production

`24sparts.ru` uses the two-node Docker Swarm configuration:

```text
deploy/swarm/stack.yml
deploy/swarm/README.md
scripts/swarm_deploy.sh
```

Deployment is performed by `.github/workflows/deploy.yml` using immutable GHCR images tagged with the exact commit SHA.

## Notes

- Backend, bot, Redis, PostgreSQL, OpenSearch and Nginx are present in the local Compose model.
- Metrics overlays remain useful for local/CI work.
- `scripts/check_deploy_compose_drift.py` validates compatibility of the Compose path; passing it does not imply Swarm production readiness.
- Production readiness gates are documented in `docs/PRODUCTION_READINESS.md`.
