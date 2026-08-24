# Servio: two-node Docker Swarm production

Production domain: `24sparts.ru`.

## Nodes

- Core/manager: `sergey@188.225.37.132`, private IPv4 `192.168.0.4`, 4 CPU / 8 GB RAM.
- Worker: `root@[2a03:6f01:1:2::2:13c7]`, private IPv4 `192.168.0.5`, 2 CPU / 2 GB RAM.
- Cluster transport uses only `192.168.0.0/24`.

## 1. Docker and firewall

Install Docker Engine on both nodes. The GitHub Actions deploy user `sergey` must run Docker without sudo:

```bash
id sergey
docker info
```

If necessary, as root:

```bash
usermod -aG docker sergey
```

Then log in again before testing Docker access.

Allow between `192.168.0.4` and `192.168.0.5` only:

- `2377/tcp` — Swarm manager control plane
- `7946/tcp` and `7946/udp` — node discovery
- `4789/udp` — overlay VXLAN

Do not expose those ports publicly. The manager additionally exposes SSH, `80/tcp` and `443/tcp`.

## 2. Clone the production candidate on the manager

```bash
sudo mkdir -p /opt/servio
sudo chown -R sergey:sergey /opt/servio
git clone -b codex/all-local-changes-20260331-110158 https://github.com/two-potato/servio.git /opt/servio/current
cd /opt/servio/current
chmod +x scripts/swarm_*.sh scripts/check_migration_safety.sh scripts/install_swarm_backup_cron.sh
```

## 3. Initialize the manager

```bash
cd /opt/servio/current
MANAGER_ADDR=192.168.0.4 WORKER_ADDR=192.168.0.5 ./scripts/swarm_bootstrap_manager.sh
```

The script validates that `192.168.0.4` exists locally, initializes Swarm, labels the manager `servio.role=core`, creates core storage and prints the worker join token.

## 4. Join the worker

On `192.168.0.5`, place `scripts/swarm_bootstrap_worker.sh` or clone the repository and run:

```bash
MANAGER_ADDR=192.168.0.4 \
WORKER_ADDR=192.168.0.5 \
SWARM_WORKER_TOKEN='SWMTKN-1-...' \
./scripts/swarm_bootstrap_worker.sh
```

Then rerun on the manager:

```bash
MANAGER_ADDR=192.168.0.4 WORKER_ADDR=192.168.0.5 ./scripts/swarm_bootstrap_manager.sh
```

Verify:

```bash
docker node ls
docker node ls -q | xargs -n1 docker node inspect \
  --format '{{.Description.Hostname}} {{.Status.Addr}} {{.Status.State}} {{.Spec.Labels}}'
```

Expected: exactly one Ready manager/core and one Ready worker.

## 5. Production environment files

Create only on the manager:

```text
/opt/servio/shared/.env.prod
/opt/servio/shared/.env.bot
/opt/servio/shared/.env.bot-notify
```

Start from:

```text
backend/.env.prod.example
bot/.env.example
bot/.env.notify.example
```

`swarm_deploy.sh` fails closed if required production values are empty or still use placeholders. Required application/infrastructure secrets include:

```dotenv
DJANGO_SECRET_KEY=<strong random secret>
POSTGRES_DB=shop
POSTGRES_USER=shop
POSTGRES_PASSWORD=<strong random password>
INTERNAL_TOKEN=<strong random token>
ORDER_APPROVE_SECRET=<strong random token>
METRICS_TOKEN=<strong random token>
TELEGRAM_BOT_TOKEN=<real token>
OPENSEARCH_INITIAL_ADMIN_PASSWORD=<strong random password>
GRAFANA_ADMIN_PASSWORD=<strong random password>
ALLOWED_HOSTS=24sparts.ru,www.24sparts.ru
CSRF_TRUSTED_ORIGINS=https://24sparts.ru,https://www.24sparts.ru
POSTGRES_HOST=db
REDIS_URL=redis://redis:6379/0
CACHE_URL=redis://redis:6379/1
OPENSEARCH_URL=http://opensearch:9200
```

Bot settings:

```dotenv
BACKEND_URL=http://backend:8000
TWA_WEBAPP_URL=https://24sparts.ru/twa/
```

Protect them:

```bash
chmod 600 /opt/servio/shared/.env.*
```

## 6. DNS and TLS

Required:

```text
24sparts.ru -> 188.225.37.132
```

If `www.24sparts.ru` resolves, the deploy script automatically includes it in the same Let's Encrypt certificate. nginx and Django are already configured for both names.

Certificate state is kept under:

```text
/opt/servio/shared/letsencrypt
/opt/servio/shared/letsencrypt-lib
/opt/servio/shared/certbot-www
```

## 7. GitHub Actions and release policy

Normal pushes to `codex/all-local-changes-20260331-110158` run CI and security checks but **do not deploy production**.

Production deployment runs only via:

- manual **Deploy Production Swarm** (`workflow_dispatch`), selecting the production-candidate branch; or
- a tag matching `prod-*` created from the verified candidate SHA.

The deploy workflow has its own mandatory verification job before GHCR publication. It checks:

- current `dev` is an ancestor of the candidate;
- backend pytest suite;
- Django `check --deploy --fail-level WARNING`;
- Ruff;
- legacy storefront build;
- Next.js typecheck + production build;
- migration safety;
- shell syntax of production scripts;
- `docker stack config` rendering;
- Playwright browser smoke.

Only after that gate passes are immutable SHA-tagged images pushed to GHCR and deployed.

Required repository secrets:

```text
PROD_SSH_HOST=188.225.37.132
PROD_SSH_PORT=22
PROD_SSH_USER=sergey
PROD_SSH_PRIVATE_KEY=<private deploy key>
PROD_APP_DIR=/opt/servio/current
LETSENCRYPT_EMAIL=<real Let's Encrypt email>
```

Repository Actions permissions must allow package writes. The public half of `PROD_SSH_PRIVATE_KEY` must be in `/home/sergey/.ssh/authorized_keys` on the manager.

## 8. Release lifecycle

The manager receives the exact Git SHA. The deployment script:

1. validates two Ready Swarm nodes and placement labels;
2. validates production secrets;
3. checks changed Django migrations for rollback-sensitive operations;
4. validates/renews TLS;
5. pulls the backend image before entering the maintenance phase;
6. starts stateful infrastructure while application replicas are paused;
7. waits for PostgreSQL, Redis and OpenSearch health;
8. runs `manage.py migrate --plan` in a one-off release container;
9. applies `manage.py migrate --noinput` once;
10. runs `collectstatic` once;
11. rolls out application services;
12. waits for Swarm convergence and Docker healthchecks;
13. verifies `https://24sparts.ru/health/`;
14. records current/previous SHA only after success.

Normal backend startup never runs migrations.

### Migration policy

Production schema changes must follow **expand/contract** compatibility. The deployment gate blocks migrations containing conservative rollback-risk markers (`RemoveField`, `DeleteModel`, `RunSQL`, `RunPython`, `RenameField`, `RenameModel`) unless an operator explicitly reviews them and sets:

```bash
ALLOW_RISKY_MIGRATIONS=1
```

Do not use that override as a routine bypass.

## 9. Health and placement

Public readiness:

```bash
curl -fsS https://24sparts.ru/health/
```

This is **not** a static nginx response. nginx proxies it to Django `/ready/`, which checks PostgreSQL and the configured cache.

Proxy-only liveness:

```bash
curl -fsS https://24sparts.ru/nginx-health
```

Cluster checks:

```bash
docker node ls
docker stack services servio
docker stack ps servio --no-trunc
```

Expected placement:

- `servio_celery-worker`, Prometheus, Grafana and Alertmanager on `servio.role=worker` (`192.168.0.5`).
- PostgreSQL, Redis, OpenSearch, nginx, Django backend, frontend, Celery beat and bots on `servio.role=core` (`192.168.0.4`).
- node-exporter and cAdvisor run globally on both nodes.
- search/recommendation API services default to `0` replicas until explicitly enabled.

The monitoring services are internal-only by default. Access Grafana through an SSH tunnel or add an authenticated reverse-proxy route later; do not expose port 3000 directly to the Internet.

## 10. PostgreSQL backup to the worker

Backups are Swarm-aware; do not use the legacy Compose backup script for this deployment.

First configure key-based SSH **from `sergey` on the manager to `root@192.168.0.5`** (or override `REMOTE_BACKUP_HOST` with a dedicated backup user). Verify non-interactively:

```bash
sudo -u sergey ssh -o BatchMode=yes root@192.168.0.5 true
```

Create the worker destination:

```bash
ssh root@192.168.0.5 'mkdir -p /opt/servio/backups/postgres && chmod 700 /opt/servio/backups/postgres'
```

Manual backup test on the manager:

```bash
cd /opt/servio/current
./scripts/swarm_backup_postgres.sh
```

The script performs `pg_dump`, gzip integrity validation, atomic rename, 14-day local retention and off-node copy to `192.168.0.5`.

Install daily backup at 02:10:

```bash
cd /opt/servio/current
sudo RUN_USER=sergey ./scripts/install_swarm_backup_cron.sh
```

Regularly test restoration into a disposable PostgreSQL instance. A backup that has never been restored is merely an optimistic file collection.

## 11. Rollback

Successful releases write:

```text
.deploy/current-sha
.deploy/previous-sha
```

Code rollback:

```bash
cd /opt/servio/current
LETSENCRYPT_EMAIL='your@email.example' ./scripts/swarm_rollback.sh
```

Rollback deliberately uses `SKIP_MIGRATIONS=1`: it restores the previous immutable application image but **does not reverse database migrations**. That is why expand/contract schema compatibility is mandatory.

## 12. Release checklist

Before the first real release:

```bash
# manager
docker node ls
docker info

test -f /opt/servio/shared/.env.prod
test -f /opt/servio/shared/.env.bot
test -f /opt/servio/shared/.env.bot-notify

# worker/off-node backup path
sudo -u sergey ssh -o BatchMode=yes root@192.168.0.5 true

# DNS
getent ahosts 24sparts.ru

# branch must include dev
git fetch origin dev
git merge-base --is-ancestor origin/dev HEAD
```

Then ensure CI and Security Audit are green for the candidate SHA and trigger **Deploy Production Swarm** manually.

## Notes

The first Swarm release intentionally keeps `/` routed to the existing Django storefront. The Next.js frontend is built and deployed inside the cluster but is not switched to public traffic during the infrastructure migration.
