
TEST_ARGS ?=

.PHONY: dev dev-metrics prod prod-setup predeploy-check prod-check check-local docker-validate migrate superuser collectstatic loaddata clean rebuild test test-fast lint stop stop-metrics status logs logs-metrics setup restart restart-metrics metrics tailwind tailwind-watch
clean:
	docker compose down -v

rebuild:
	docker compose build --no-cache

test:
	docker compose --profile test run --rm backend-test /app/.venv/bin/pytest $(TEST_ARGS)

test-fast:
	docker compose --profile test run --rm backend-test /app/.venv/bin/pytest -o addopts='' $(TEST_ARGS)

lint:
	docker compose --profile test run --rm backend-test /app/.venv/bin/ruff .

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-metrics:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up --build

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-setup:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend /app/.venv/bin/python manage.py migrate --noinput
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend /app/.venv/bin/python manage.py collectstatic --noinput

predeploy-check:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend /app/.venv/bin/python manage.py check --deploy
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend /app/.venv/bin/python manage.py migrate --check

prod-check:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
	docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend /app/.venv/bin/python manage.py check --deploy
	docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backend /app/.venv/bin/python manage.py migrate --check

check-local:
	docker compose --profile test run --rm --no-deps backend-test /app/.venv/bin/python manage.py check

docker-validate:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet
	docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml config --quiet
	docker compose -f docker-compose.glitchtip.yml config --quiet
	python3 scripts/check_deploy_compose_drift.py

stop:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down || true
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down || true
	# если метрики поднимались вместе с dev/prod, выключим и их
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml down || true
	docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.metrics.yml down || true

stop-metrics:
	# останавливает только стек метрик
	docker compose -f docker-compose.metrics.yml down || true

status:
	docker compose ps

logs:
	docker compose logs --since=10m --tail=200

logs-metrics:
	docker compose -f docker-compose.metrics.yml logs --since=10m --tail=200

setup:
	# права на каталог статики и миграции + collectstatic
	docker compose exec -u 0 backend sh -lc 'mkdir -p /app/staticfiles && chown -R app:app /app/staticfiles'
	docker compose exec backend /app/.venv/bin/python manage.py migrate --noinput
	docker compose exec backend /app/.venv/bin/python manage.py collectstatic --noinput

restart:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

metrics:
	# Запустить стек с метриками и GlitchTip (можно комбинировать с dev)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up -d --build prometheus loki grafana alertmanager promtail nginx-exporter postgres-exporter redis-exporter opensearch-exporter node-exporter cadvisor blackbox glitchtip-postgres glitchtip-redis glitchtip

restart-metrics:
	# перезапуск стека метрик вместе с GlitchTip
	docker compose -f docker-compose.metrics.yml down || true
	docker compose -f docker-compose.metrics.yml up -d --build

migrate:
	docker compose exec backend python manage.py migrate

superuser:
	docker compose exec backend python manage.py createsuperuser

collectstatic:
	docker compose exec backend python manage.py collectstatic --noinput

loaddata:
	docker compose exec backend python manage.py loaddata catalog/fixtures.json

# Tailwind build helpers (requires Node + dev deps installed locally)
tailwind:
	npx tailwindcss -i ./assets/tw.css -o ./backend/static/css/app.css --minify

tailwind-watch:
	npx tailwindcss -i ./assets/tw.css -o ./backend/static/css/app.css --watch
