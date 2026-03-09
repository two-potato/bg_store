# Production Deploy

Этот проект деплоится через GitHub Actions и `scripts/deploy_prod.sh`.

Ключевая идея:
- `dev` для активной разработки
- merge/push в `main` запускает production deploy workflow
- сервер получает конкретный commit SHA и раскатывает его через `docker compose`

## 1. Что должно быть готово до первого деплоя

На сервере:
- Docker Engine
- `docker compose` plugin
- `git`
- открыты порты `80/tcp` и `443/tcp`
- домены `potatofarm.ru` и `www.potatofarm.ru` указывают на сервер

Рекомендуемый каталог приложения:
- `/opt/servio`

Важно:
- workflow использует secret `PROD_APP_DIR`
- не полагайся на fallback-путь, задай `PROD_APP_DIR` явно

## 2. GitHub Secrets

В `Repository -> Settings -> Secrets and variables -> Actions` задай:
- `PROD_SSH_HOST`
- `PROD_SSH_PORT`
- `PROD_SSH_USER`
- `PROD_SSH_PRIVATE_KEY`
- `PROD_APP_DIR`

Пример:
- `PROD_SSH_HOST=185.207.65.192`
- `PROD_SSH_PORT=22`
- `PROD_SSH_USER=root`
- `PROD_APP_DIR=/opt/servio`

## 3. Первичная подготовка сервера

```bash
apt-get update
apt-get install -y git curl docker.io docker-compose-plugin
systemctl enable --now docker

mkdir -p /opt/servio
git clone <YOUR_REPOSITORY_URL> /opt/servio
cd /opt/servio

cp backend/.env.prod.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
```

После этого обязательно заполни:
- `backend/.env`
- `bot/.env`
- `bot/.env.notify`

## 4. Обязательные production env values

Минимально обязательные для backend:
- `DJANGO_SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `POSTGRES_PASSWORD`
- `INTERNAL_TOKEN`
- `ORDER_APPROVE_SECRET`
- `METRICS_TOKEN`
- `TELEGRAM_BOT_TOKEN`

Дополнительно для production обычно нужны:
- SMTP-параметры
- `ADMIN_NOTIFY_EMAILS`
- `ADMIN_NOTIFY_TELEGRAM_IDS`
- `TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`
- `POSTHOG_API_KEY`
- `POSTHOG_HOST`
- `CLARITY_PROJECT_ID`
- `SENTRY_DSN`

Важно:
- при `DEBUG=0` и `config.settings.prod` проект теперь валит старт, если заданы слабые значения для:
  - `DJANGO_SECRET_KEY`
  - `INTERNAL_TOKEN`
  - `ORDER_APPROVE_SECRET`
  - `METRICS_TOKEN`
- также production guard теперь требует:
  - явный `CSRF_TRUSTED_ORIGINS`
  - только `https://` origins в `CSRF_TRUSTED_ORIGINS`
  - отсутствие `localhost` в `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`

## 5. Compose stack

Production deploy использует:
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `docker-compose.metrics.yml`

Основные сервисы:
- `backend`
- `nginx`
- `db`
- `redis`
- `es`
- `bot`
- `bot-notify`
- `celery-worker`
- `celery-beat`

Runtime container names:
- `servio-backend`
- `servio-nginx`
- `servio-db`
- `servio-redis`
- `servio-es`
- `servio-bot`
- `servio-bot-notify`
- `servio-worker`
- `servio-beat`

## 6. Как работает production deploy

Workflow `.github/workflows/deploy.yml`:
1. подключается по SSH
2. переходит в `PROD_APP_DIR`
3. делает `git fetch --all --prune`
4. делает `git reset --hard` на конкретный `github.sha`
5. запускает `bash ./scripts/deploy_prod.sh`

Скрипт deploy:
1. проверяет/получает Let's Encrypt сертификат
2. поднимает compose stack
3. применяет миграции
4. прогоняет `seed_sellers`, если команда доступна
5. чистит кэш
6. чинит права на `staticfiles`
7. выполняет `collectstatic`
8. делает health-check `http://localhost/health/`
9. включает UFW с allow только для SSH/80/443

## 7. Ручной production preflight

Перед ручным деплоем полезно проверить:

```bash
cd /opt/servio
docker compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null
docker compose -f docker-compose.yml -f docker-compose.prod.yml build backend bot nginx
```

Если стек уже поднят:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend /app/.venv/bin/python manage.py check --deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend /app/.venv/bin/python manage.py migrate --check
```

## 8. CI quality gate

В CI теперь есть отдельный production settings preflight:

```bash
python manage.py check --deploy --fail-level WARNING
```

Он запускается под `config.settings.prod` с production-like env и ловит:
- слабые секреты
- wildcard `ALLOWED_HOSTS`
- отсутствующий `CSRF_TRUSTED_ORIGINS`
- локальные origin/host значения в production

## 9. Ручной deploy

Если нужен ручной запуск на сервере:

```bash
cd /opt/servio
bash ./scripts/deploy_prod.sh
```

## 10. Smoke-check после деплоя

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS http://localhost/health/
curl -H "X-Metrics-Token: ${METRICS_TOKEN}" -fsS http://localhost/metrics >/dev/null
```

Проверить публичные страницы:

```bash
curl -I https://potatofarm.ru/
curl -I https://potatofarm.ru/admin/
curl -I https://potatofarm.ru/health/
```

## 11. Логи

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend nginx celery-worker celery-beat bot bot-notify
```

Если используется metrics stack:

```bash
docker compose -f docker-compose.metrics.yml logs --since=10m --tail=200
```

## 12. Типовые проблемы

`ImproperlyConfigured` на старте backend:
- проверь `DJANGO_SECRET_KEY`
- проверь `INTERNAL_TOKEN`
- проверь `ORDER_APPROVE_SECRET`
- проверь `METRICS_TOKEN`
- проверь `ALLOWED_HOSTS`
- проверь `CSRF_TRUSTED_ORIGINS`

`bot-notify` отвечает `401 Invalid internal token`:
- проверь, что `INTERNAL_TOKEN` совпадает в `backend/.env` и `bot/.env.notify`

`collectstatic` не может писать в volume:
- повторно запусти `scripts/deploy_prod.sh`
- он сам чинит владельца `/app/staticfiles`

`Let's Encrypt` не выпускается:
- проверь DNS-записи
- проверь доступность `80/tcp` и `443/tcp`
- проверь, что `potatofarm.ru` и `www.potatofarm.ru` смотрят на нужный сервер
