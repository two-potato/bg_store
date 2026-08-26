# Two-Node Swarm Deployment Design

## Goal

Deploy Servio from `codex/all-local-changes-20260331-110158` to two Docker hosts as one orchestrated production cluster, with automated build and deployment through GitHub Actions.

## Topology

- `188.225.37.132` — Docker Swarm manager, public ingress for `24sparts.ru`, 4 CPU / 8 GB RAM.
- `192.168.0.5` — Docker Swarm worker, 2 CPU / 2 GB RAM; reachable through the private `192.168.0.0/24` network.
- Swarm control/data traffic uses the private network.
- Public HTTP/HTTPS traffic enters only through the manager.

## Orchestration

Docker Swarm is used instead of two independent Compose projects. The manager owns stack deployment and desired state. Services communicate through Swarm overlay networks and service DNS.

Node labels define placement:

- `servio.role=core` on the manager.
- `servio.role=worker` on the worker.

Stateful and singleton services remain pinned to the manager. Work that can safely run remotely is placed on the worker.

## Service Placement

Manager/core:

- nginx
- frontend
- backend
- PostgreSQL
- Redis
- OpenSearch
- Celery beat
- bot
- bot-notify

Worker:

- Celery worker
- Prometheus/Grafana/Alertmanager when the metrics stack is enabled

The initial deployment does not move PostgreSQL, Redis, or OpenSearch to the 2 GB worker. This avoids unnecessary network/state complexity and protects the small node from memory pressure.

## Images

GitHub Actions builds immutable images and pushes them to GitHub Container Registry (GHCR), tagged with the Git commit SHA. Servers do not build application images during normal deployments.

Images:

- `ghcr.io/two-potato/servio-backend:<sha>`
- `ghcr.io/two-potato/servio-frontend:<sha>`
- `ghcr.io/two-potato/servio-bot:<sha>`
- `ghcr.io/two-potato/servio-search-api:<sha>`
- `ghcr.io/two-potato/servio-recommendation-api:<sha>`

## CI/CD

The deployment workflow runs on pushes to `codex/all-local-changes-20260331-110158` and by `workflow_dispatch`.

Pipeline:

1. Checkout source.
2. Validate deployment configuration.
3. Authenticate to GHCR.
4. Build and push application images tagged with `${{ github.sha }}`.
5. Establish SSH to `188.225.37.132`.
6. Copy/update only deployment metadata needed by the manager.
7. Run the Swarm deployment script with the image SHA.
8. Wait for Swarm convergence and run HTTP health checks.
9. Fail the workflow if required services do not converge or `https://24sparts.ru/health/` fails.

Rollback uses the previous successfully deployed image SHA recorded on the manager.

## Secrets and Runtime Configuration

Production secrets are not committed to Git.

GitHub Actions requires SSH deployment secrets and GHCR permissions. Application runtime secrets remain on the manager in `/opt/servio/shared/.env.prod` and are consumed by the stack through `env_file` or generated Swarm secrets where the application supports file-based secrets.

The deployment workflow never prints production secret values.

## Domain and TLS

Production domain: `24sparts.ru`.

- DNS points `24sparts.ru` to `188.225.37.132`.
- nginx is constrained to the manager.
- TLS certificates are stored on the manager under `/opt/servio/shared/letsencrypt`.
- Certificate issuance/renewal occurs on the manager, not inside a reschedulable container.

## Networking and Firewall

Swarm traffic uses the private network. Required inter-node ports are:

- TCP 2377 — Swarm management (manager only)
- TCP/UDP 7946 — node discovery
- UDP 4789 — overlay network VXLAN

These ports must only be allowed on the private interface/network. Public ingress exposes only SSH, HTTP and HTTPS as required.

## Persistent Data

Persistent Docker volumes for PostgreSQL, Redis, OpenSearch and static files live on the core node. Services using those volumes are constrained to that node, so Swarm never reschedules them onto the worker without storage.

## Deployment Safety

- Images are immutable and SHA-tagged.
- Stateful services are singleton services pinned to `core`.
- Stateless services use Swarm rolling-update settings.
- Deployment records the currently deployed SHA before updating.
- Health checks are required before a deployment is considered successful.
- Rollback redeploys the previously recorded SHA.

## Bootstrap

Bootstrap is a one-time operation:

1. Install Docker Engine and Compose plugin on both hosts.
2. Initialize Swarm on the manager using its private address.
3. Join `192.168.0.5` as a worker.
4. Apply node labels.
5. Create required directories and persistent volumes on the manager.
6. Authenticate the manager/worker to GHCR if private images require registry credentials.
7. Install the production env file and TLS prerequisites on the manager.
8. Perform the first stack deploy from GitHub Actions.

## Success Criteria

- `docker node ls` shows one Ready manager and one Ready worker.
- `docker stack services servio` converges with all required replicas running.
- Celery worker is scheduled on the worker node.
- Core/stateful services are scheduled on the manager.
- `https://24sparts.ru/health/` returns success.
- A second GitHub Actions deployment updates services without manually logging into either server.
- The rollback script can redeploy the previously recorded SHA.
