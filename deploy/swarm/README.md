# Servio: two-node Docker Swarm production

Production domain: `24sparts.ru`.

## Nodes

- Core/manager: `sergey@188.225.37.132`, 4 CPU / 8 GB RAM.
- Worker: `root@[2a03:6f01:1:2::2:13c7]`, private IPv4 `192.168.0.5`, 2 CPU / 2 GB RAM.
- Cluster transport must use the private `192.168.0.0/24` network.

The manager private IPv4 is intentionally not hard-coded. Determine it on the manager with:

```bash
ip -4 -br addr
```

Use that address as `MANAGER_ADDR` below.

## 1. Docker and firewall

Install Docker Engine on both nodes. The SSH user used by GitHub Actions (`sergey`) must be able to run Docker without sudo.

Between the two private addresses allow only:

- `2377/tcp`
- `7946/tcp`
- `7946/udp`
- `4789/udp`

Do not expose those Swarm ports to the public Internet.

The core node additionally needs public `80/tcp`, `443/tcp` and SSH.

## 2. Clone the deployment repository on the manager

```bash
sudo mkdir -p /opt/servio
sudo chown -R sergey:sergey /opt/servio
git clone -b codex/all-local-changes-20260331-110158 https://github.com/two-potato/servio.git /opt/servio/current
cd /opt/servio/current
chmod +x scripts/swarm_*.sh
```

## 3. Initialize the manager

Example only; replace `192.168.0.X` with the manager's real private IPv4:

```bash
cd /opt/servio/current
MANAGER_ADDR=192.168.0.X WORKER_ADDR=192.168.0.5 ./scripts/swarm_bootstrap_manager.sh
```

The script prints the worker join token/command.

## 4. Join the worker

On `192.168.0.5`:

```bash
MANAGER_ADDR=192.168.0.X \
SWARM_WORKER_TOKEN='SWMTKN-1-...' \
./scripts/swarm_bootstrap_worker.sh
```

The worker only needs the bootstrap script for this one-time step. It may also be joined directly with the `docker swarm join ...` command printed by the manager.

Then rerun on the manager so the worker gets its placement label:

```bash
MANAGER_ADDR=192.168.0.X WORKER_ADDR=192.168.0.5 ./scripts/swarm_bootstrap_manager.sh
```

Verify:

```bash
docker node ls
docker node inspect self --pretty
docker node ls -q | xargs -n1 docker node inspect --format '{{.Description.Hostname}} {{.Status.Addr}} {{.Spec.Labels}}'
```

## 5. Production environment files

Create on the manager:

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

At minimum replace all `replace-*` / `change-me` values and configure the Telegram credentials you actually use.

The Django production file must contain:

```dotenv
ALLOWED_HOSTS=24sparts.ru,www.24sparts.ru
CSRF_TRUSTED_ORIGINS=https://24sparts.ru,https://www.24sparts.ru
POSTGRES_HOST=db
REDIS_URL=redis://redis:6379/0
OPENSEARCH_URL=http://opensearch:9200
```

The bot file should use:

```dotenv
BACKEND_URL=http://backend:8000
TWA_WEBAPP_URL=https://24sparts.ru/twa/
```

Protect the files:

```bash
chmod 600 /opt/servio/shared/.env.*
```

## 6. DNS

Point `24sparts.ru` to the public address of the core node:

```text
24sparts.ru -> 188.225.37.132
```

Add `www.24sparts.ru` only if you intend to use it. Initial automatic certificate issuance is for `24sparts.ru` itself.

## 7. GitHub Actions configuration

The workflow `.github/workflows/deploy.yml` builds application images and pushes them to GHCR using the repository `GITHUB_TOKEN`, then deploys the exact commit SHA to the manager.

Repository Actions permissions must permit package writes.

Required repository secrets:

```text
PROD_SSH_HOST=188.225.37.132
PROD_SSH_PORT=22
PROD_SSH_USER=sergey
PROD_SSH_PRIVATE_KEY=<private deploy key>
PROD_APP_DIR=/opt/servio/current
LETSENCRYPT_EMAIL=<real email for Let's Encrypt>
```

The corresponding public SSH key must be in `/home/sergey/.ssh/authorized_keys` on the manager.

## 8. First deployment

Push to:

```text
codex/all-local-changes-20260331-110158
```

or run **Deploy Production Swarm** through `workflow_dispatch`.

The workflow builds and pushes:

```text
ghcr.io/two-potato/servio-backend:<git-sha>
ghcr.io/two-potato/servio-frontend:<git-sha>
ghcr.io/two-potato/servio-bot:<git-sha>
ghcr.io/two-potato/servio-search-api:<git-sha>
ghcr.io/two-potato/servio-recommendation-api:<git-sha>
```

The manager then runs `scripts/swarm_deploy.sh` and deploys stack `servio` with `--with-registry-auth`.

## 9. Verify placement and health

On the manager:

```bash
docker node ls
docker stack services servio
docker stack ps servio
curl -fsS https://24sparts.ru/health/
```

Expected placement:

- `servio_celery-worker` on the node labeled `servio.role=worker` (`192.168.0.5`).
- PostgreSQL, Redis, OpenSearch, nginx, backend, frontend, Celery beat and bots on `servio.role=core`.

Search/recommendation sidecar services are built but start at `0` replicas until their rollout modes are explicitly enabled.

## 10. Rollback

A successful deployment writes:

```text
.deploy/current-sha
.deploy/previous-sha
```

Rollback on the manager:

```bash
cd /opt/servio/current
LETSENCRYPT_EMAIL='your@email.example' ./scripts/swarm_rollback.sh
```

Swarm service-level update failures also use `failure_action: rollback` for stateless application services.

## Notes

The initial nginx routing intentionally matches the current production behavior: `/` is served by Django. The Next.js frontend service is deployed and available inside the cluster, but public routing is not switched to it as part of the infrastructure migration.
