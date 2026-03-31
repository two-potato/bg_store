# Operations Runbook

## Деплой

Production deploy выполняется через:

- `.github/workflows/deploy.yml`
- `scripts/deploy_prod.sh`

Перед релизом:

1. Убедиться, что `CI` зеленый
2. Проверить миграции и changelog
3. Проверить секреты и env

## Откат

Минимальный safe rollback:

1. Зафиксировать текущий SHA
2. Вернуться на предыдущий рабочий SHA
3. Перезапустить `scripts/deploy_prod.sh`
4. Проверить `/health/`, ключевые HTML/API сценарии и лог ошибок

## Бэкапы

Для PostgreSQL добавлены скрипты:

- `scripts/backup_postgres.sh`
- `scripts/restore_postgres_backup.sh`
- `scripts/check_backup_freshness.sh`
- `scripts/install_backup_cron.sh`

Рекомендуемая практика:

1. Ежедневный backup по cron/systemd timer
2. Retention не меньше 14 дней
3. Еженедельный restore smoke test в отдельной среде

Рекомендуемый bootstrap на сервере:

```bash
chmod +x scripts/backup_postgres.sh scripts/restore_postgres_backup.sh scripts/check_backup_freshness.sh scripts/install_backup_cron.sh
scripts/install_backup_cron.sh
```

Retention policy (source-of-truth):

- backup каждые 24 часа (`02:10`)
- freshness-check каждый час (`15 * * * *`)
- удаление backup старше `14` дней (`RETENTION_DAYS=14`)
- критичный порог stale backup: `>26` часов (`MAX_AGE_HOURS=26`)

Prometheus alerting:

- `BackupTooOld` — срабатывает при `servio_backup_age_hours > 26`
- `BackupMetricMissing` — нет метрики свежести backup > 2 часов

## Проверки после релиза

- `curl -fsS http://localhost/health/`
- открыть главную, каталог, PDP, checkout
- проверить Grafana / GlitchTip / Alertmanager
- проверить артефакты `Nightly Load Budget` workflow (p95/error budgets)

## Что смотреть при инциденте

- `docker compose ps`
- `docker compose logs --tail=200 backend`
- `docker compose logs --tail=200 nginx`
- `docker compose logs --tail=200 db`
- GlitchTip issues
- Prometheus / Grafana alerts
