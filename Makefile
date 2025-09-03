
.PHONY: dev prod migrate superuser collectstatic loaddata clean rebuild test lint stop stop-metrics status logs logs-metrics setup restart restart-metrics metrics
clean:
	docker compose down -v

rebuild:
	docker compose build --no-cache

test:
	docker compose exec backend python -m pytest

lint:
	docker compose exec backend python -m ruff .

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

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
	# Запустить стек с метриками (можно комбинировать с dev)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.metrics.yml up -d --build prometheus loki grafana alertmanager promtail nginx-exporter postgres-exporter redis-exporter es-exporter node-exporter cadvisor blackbox

restart-metrics:
	# перезапуск только метрик
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
