# Docker Guide

## Compose Layers

- `docker-compose.yml`: base services
- `docker-compose.dev.yml`: local development overrides
- `docker-compose.prod.yml`: production-oriented stack
- `docker-compose.metrics.yml`: observability stack

## Typical Local Run

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Typical Production Run

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Notes

- Backend, bot, Redis, PostgreSQL, OpenSearch and Nginx are part of the main stack
- Metrics services are optional for local work but expected in production-like environments
- `scripts/check_deploy_compose_drift.py` should stay green when compose or deploy logic changes
