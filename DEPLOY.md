# Production Deploy

## GitHub Actions CI/CD (potatofarm.ru)

В репозитории есть workflow `.github/workflows/deploy.yml`, который деплоит `main` на сервер по SSH.

### 0. Секреты GitHub (Repository -> Settings -> Secrets and variables -> Actions)

Добавь secrets:
- `PROD_SSH_HOST` = `185.207.65.192`
- `PROD_SSH_PORT` = `22`
- `PROD_SSH_USER` = `root`
- `PROD_APP_DIR` = `/opt/bg_shop_full`
- `PROD_SSH_PRIVATE_KEY` = приватный SSH ключ для деплоя (многострочный PEM/OpenSSH)

### 1. Первичная подготовка сервера (один раз)

```bash
apt-get update
apt-get install -y git curl docker.io docker-compose-plugin
systemctl enable --now docker
mkdir -p /opt/bg_shop_full
git clone https://github.com/two-potato/bg_store.git /opt/bg_shop_full
cd /opt/bg_shop_full
cp backend/.env.prod.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
```

Заполни реальные значения в `backend/.env`, `bot/.env`, `bot/.env.notify`.

### 2. Как работает деплой

При push в `main` workflow:
1. Подключается к серверу по SSH
2. Делает `git fetch` + `git reset --hard <sha>`
3. Запускает `scripts/deploy_prod.sh`
4. Выполняет `migrate`, `collectstatic`, health-check

## 1. Подготовка секретов

```bash
cp backend/.env.prod.example backend/.env
cp bot/.env.example bot/.env
cp bot/.env.notify.example bot/.env.notify
```

Заполни реальные значения в `backend/.env`, `bot/.env`, `bot/.env.notify`:
- `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`
- `TELEGRAM_BOT_TOKEN` (для shop бота и notify бота)
- `INTERNAL_TOKEN`, `ORDER_APPROVE_SECRET`, `METRICS_TOKEN`
- SMTP (`EMAIL_HOST_*`)
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- `ENABLE_API_DOCS=0` (рекомендуется в проде)
- cache (`CACHE_BACKEND=redis`, `CACHE_URL`, `CACHE_DEFAULT_TIMEOUT`, `CACHE_TTL_*`)
- `ALLOWED_DOC_ROOTS` для notify-бота (например: `/app/media,/tmp`)

## 2. Сборка и запуск

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 3. Проверка состояния

```bash
docker compose ps
curl -f http://localhost:8080/health/
```

## 4. Базовые smoke-checks

```bash
# приложение
curl -I http://localhost:8080/

# админка
curl -I http://localhost:8080/admin/

# метрики backend (в проде нужен токен)
curl -H "X-Metrics-Token: ${METRICS_TOKEN}" -I http://localhost:8080/metrics
```

## 5. Loki/Grafana: готовые запросы

### 5.1 Общий поток логов
```logql
{service=~".+"}
```

### 5.2 Ошибки backend за 5 минут
```logql
sum(rate({service="backend"} |= "ERROR" [5m]))
```

### 5.3 Ошибки авторизации/доступа
```logql
{service="backend"} |= "invalid initData" or {service="backend"} |= "Forbidden"
```

### 5.4 События заказов
```logql
{service="backend"} |= "order_created_" or {service="backend"} |= "order_approved" or {service="backend"} |= "order_rejected"
```

### 5.5 Ошибки уведомлений
```logql
{service="backend"} |= "notify" |= "failed"
```

### 5.6 Поиск долгих запросов (duration_ms)
```logql
{service="backend"} | json | duration_ms >= 1000
```

## 6. Рекомендуемые алерты (Grafana Alerting)
1. `HighErrorRateBackend`: `sum(rate({service="backend"} |= "ERROR" [5m])) > 1`
2. `AuthFailuresSpike`: `sum(rate({service="backend"} |= "invalid initData" [5m])) > 0.2`
3. `NotifyFailures`: `sum(rate({service="backend"} |= "notify" |= "failed" [5m])) > 0`
4. `SlowRequests`: `count_over_time({service="backend"} | json | duration_ms >= 1500 [5m]) > 20`

## 7. Полезные команды

```bash
# логи
docker compose logs -f backend nginx celery-worker celery-beat

# миграции вручную (если нужно)
docker compose exec backend python manage.py migrate --noinput

# собрать статику (если нужно)
docker compose exec backend python manage.py collectstatic --noinput
```

## 8. Обновление релиза

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
