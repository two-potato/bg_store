# Production Release Checklist

## 1. Candidate

- [ ] Candidate contains current `dev` (`git merge-base --is-ancestor origin/dev HEAD`)
- [ ] CI is green
- [ ] Security Audit is green
- [ ] Required migrations are committed and migration-safety gate passes
- [ ] New production env vars are documented in example files
- [ ] Frontend checked on desktop, mobile and Telegram WebApp where applicable
- [ ] Metrics/logging impact reviewed

## 2. Swarm preflight

- [ ] Manager/core node is `Ready` and labeled `servio.role=core`
- [ ] Worker node is `Ready` and labeled `servio.role=worker`
- [ ] `docker stack config -c deploy/swarm/stack.yml` renders successfully
- [ ] Production env files contain no placeholders or development secrets
- [ ] `24sparts.ru` resolves to the manager public address
- [ ] Backup destination on worker is reachable

## 3. Deploy

Production is explicit. Use **Deploy Production Swarm** (`workflow_dispatch`) or an approved `prod-*` tag.

- [ ] Workflow verifies candidate before publishing images
- [ ] Immutable GHCR images are published with exact commit SHA
- [ ] Release migration phase completes once
- [ ] Swarm services converge to desired replicas
- [ ] `https://24sparts.ru/health/` returns success

## 4. Post-deploy smoke

- [ ] Main page loads
- [ ] Login/auth flow works
- [ ] Catalog and product pages load
- [ ] Cart and checkout flow works
- [ ] Bot endpoints are healthy
- [ ] Celery worker is running on worker node
- [ ] Prometheus/Grafana/Alertmanager are healthy
- [ ] node-exporter and cAdvisor report both nodes

## 5. Backup/DR

- [ ] PostgreSQL backup completes
- [ ] Backup is copied to worker `192.168.0.5`
- [ ] Backup freshness is within policy
- [ ] Restore drill has been completed for the current backup mechanism

## 6. Rollback

- [ ] Previous known-good SHA is recorded in `.deploy/previous-sha`
- [ ] Code-only rollback path `scripts/swarm_rollback.sh` is available
- [ ] Database migration compatibility has been reviewed; rollback does not assume schema reversal
- [ ] Health and critical user paths are rechecked after rollback
