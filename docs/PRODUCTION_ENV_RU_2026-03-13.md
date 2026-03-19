# Production Env

Короткая памятка по production env для Servio.

## Что использовать

Для production-like запуска и predeploy-проверок используем:

- `backend/.env.prod.example` как шаблон
- `backend/.env.prod` как локальный рабочий production env

`backend/.env` не должен быть источником production-настроек. Это dev/local файл.

## Обязательные переменные

- `DJANGO_SECRET_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `INTERNAL_TOKEN`
- `ORDER_APPROVE_SECRET`
- `METRICS_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

## Значения, восстановленные из истории деплоев

Для production домена проект стабильно использовал:

- `ALLOWED_HOSTS=potatofarm.ru,www.potatofarm.ru`
- `CSRF_TRUSTED_ORIGINS=https://potatofarm.ru,https://www.potatofarm.ru`

Это подтверждено по истории `backend/.env.prod.example` и workflow деплоя.

## Что не восстанавливается из истории

- `METRICS_TOKEN`

Это секрет. В git был только placeholder, а не реальное значение. Его нужно генерировать и хранить отдельно.

## Чего нельзя делать

- не использовать `localhost`, `127.0.0.1` и локальные origin'ы при `DEBUG=0`
- не смешивать production env с `backend/.env`
- не коммитить реальные секреты в `*.env`

## Рекомендуемый порядок

1. Скопировать шаблон:

```bash
cp backend/.env.prod.example backend/.env.prod
```

2. Заполнить секреты и production host values.

3. Прогнать проверки:

```bash
make prod-check
```

4. Только после этого запускать rollout.

## Что уже проверено локально

Для текущего состояния проекта уже подтверждено:

- `docker compose ... config --quiet` проходит
- `manage.py check --deploy` проходит
- `manage.py migrate --check` проходит

Значит текущий production env workflow для репозитория рабочий.
