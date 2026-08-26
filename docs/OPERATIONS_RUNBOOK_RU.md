# Operations Runbook — production 24sparts.ru

Production работает как двухузловой Docker Swarm. Каноническая схема bootstrap и placement описана в `deploy/swarm/README.md`.

## Деплой

Production deploy выполняется через `.github/workflows/deploy.yml` и `scripts/swarm_deploy.sh`.

Перед релизом обязательно:

1. Финальный SHA содержит актуальный `dev`.
2. `CI` зелёный.
3. `Security Audit` зелёный.
4. Оба Swarm-узла имеют статус `Ready` и корректные labels `servio.role=core` / `servio.role=worker`.
5. Production env не содержит placeholder-секретов.
6. Миграции прошли migration-safety gate.
7. DNS `24sparts.ru` указывает на production manager.

Production deploy запускается явно через `workflow_dispatch` либо утверждённый `prod-*` tag. Feature-branch push сам по себе production не меняет.

## Проверки после релиза

На manager:

```bash
docker node ls
docker stack services servio
docker stack ps servio --no-trunc
curl -fsS https://24sparts.ru/health/
```

`/health/` должен подтверждать readiness Django и его критичных зависимостей. Nginx-only liveness доступен отдельно как `/nginx-health` внутри proxy-контейнера.

Проверить ключевые пользовательские сценарии:

- главная;
- каталог;
- PDP;
- корзина;
- checkout;
- авторизация;
- Telegram integration, если она включена.

## Миграции

Миграции применяются один раз отдельной release phase в `scripts/swarm_deploy.sh` до rollout application services.

Перед применением выполняется `scripts/check_migration_safety.sh`. Потенциально destructive/rollback-sensitive миграции требуют явного review и expand/contract совместимости.

Не запускайте `migrate` вручную внутри нескольких backend replicas одновременно.

## Откат

Последний успешный deploy сохраняет:

```text
.deploy/current-sha
.deploy/previous-sha
```

Code-only rollback:

```bash
cd /opt/servio/current
./scripts/swarm_rollback.sh
```

Rollback приложения не означает автоматический rollback схемы БД. Database migrations должны проектироваться обратно совместимыми.

## PostgreSQL backup

Production backup использует Swarm-aware скрипты:

- `scripts/swarm_backup_postgres.sh`
- `scripts/install_swarm_backup_cron.sh`

Backup создаётся на core и копируется на worker `192.168.0.5`, чтобы потеря core-узла не уничтожила единственную копию.

После первого запуска обязательно выполнить restore drill. Наличие файла backup без проверенного восстановления не считается рабочей DR-схемой.

## Observability

Production monitoring размещён в Swarm:

- Prometheus;
- Grafana;
- Alertmanager;
- node-exporter на всех узлах;
- cAdvisor на всех узлах.

Основные monitoring services размещаются на worker, чтобы не отбирать RAM у PostgreSQL/OpenSearch/backend на core.

## Диагностика

Можно запустить workflow `.github/workflows/prod-swarm-diagnostics.yml` или выполнить на manager:

```bash
docker node ls
docker stack services servio
docker stack ps servio --no-trunc
docker service logs --tail 200 servio_backend
docker service logs --tail 200 servio_nginx
docker service logs --tail 200 servio_db
```

Для проблем конкретной task сначала смотрите `docker service ps <service> --no-trunc`, затем logs этой service/task.

## Источники истины

- `deploy/swarm/README.md` — bootstrap и topology;
- `deploy/swarm/stack.yml` — production services/placement/resources;
- `scripts/swarm_deploy.sh` — release lifecycle;
- `scripts/swarm_rollback.sh` — rollback;
- `docs/PRODUCTION_READINESS.md` — обязательные release gates.

Старый single-host Compose production flow не является production source of truth. Compose-файлы в корне используются для локальной разработки/совместимости и не должны применяться вместо Swarm production deployment.
