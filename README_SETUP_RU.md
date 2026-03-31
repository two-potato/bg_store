# Codex-настройка для Servio

Этот архив — стартовый комплект под проект **Servio** для миграции фронтенда на:

- Next.js (App Router)
- TypeScript
- Tailwind CSS v4
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod
- Playwright
- Storybook
- Sentry
- PostHog

## Состав команды

Команда намеренно **не раздута**. В ней только 6 проектных агентов:

1. **architect** — архитектура, границы доменов, декомпозиция задач.
2. **frontend** — Next.js storefront, App Router, SSR/RSC, интеграция с API.
3. **uiux** — дизайн-система, UX, accessibility, mobile-first, визуальная целостность.
4. **qa_metrics** — Playwright, Storybook, Sentry, PostHog, quality gates.
5. **backend** — Django/DRF, OpenSearch, Celery, API-контракты, seller/buyer flows.
6. **devops** — Docker, CI/CD, окружения, observability, release discipline.

## Главный принцип

Цель не в том, чтобы "переделать ради переделки".

Цель — **построить новый storefront на Next.js**, сохранив сильные стороны текущего backend-ядра Servio:

- Django + DRF
- OpenSearch
- Celery
- Postgres
- Redis
- observability stack

## Куда класть файлы

Содержимое архива переносится в корень репозитория Servio.

Основные файлы:

- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `.agents/skills/*/SKILL.md`
- `prompts/*.md`

## Как использовать

### 1. Скопировать файлы в репозиторий

### 2. Запустить Codex из корня проекта

### 3. Первая команда

Используй файл:

- `prompts/FIRST_MESSAGE_TO_ARCHITECT.md`

### 4. Рабочая модель

- Ты даёшь цель.
- `architect` разбивает задачу.
- Он вызывает узких агентов по необходимости.
- Все ответы, отчёты, планы и комментарии — **только на русском**.

## Что уже учтено под текущий Servio

Настройки заточены под то, что в репозитории уже есть:

- Django storefront сейчас server-rendered
- есть HTMX + шаблоны + page-scoped JS/CSS
- search уже вынесен в OpenSearch client + orchestration layer
- checkout уже частично декомпозирован, но ещё требует дальнейшего разделения
- seller-контур уже широкий, но seller OMS/WMS и post-order ещё не закрыты

## Что не нужно делать агентам

- не переписывать весь backend без причины
- не тащить бизнес-логику во фронт
- не плодить агентов поверх агентов
- не разводить несколько конкурирующих фронтов
- не делать "космический replatform" без пошаговой миграции

## Целевой результат

- новый storefront уровня лучших практик 2027
- быстрая и чистая навигация
- сильный поиск
- сильные рекомендации
- качественная мобильная UX-модель
- наблюдаемость и продуктовая аналитика по умолчанию
- строгая инженерная дисциплина

