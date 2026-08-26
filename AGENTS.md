# AGENTS.md — Servio

## Миссия проекта

Servio развивается в современный B2B/B2C marketplace.

Текущая стратегическая цель:

- вынести storefront в отдельный frontend на Next.js
- сохранить Django/DRF как backend platform
- усилить поиск, рекомендации, seller-контур, checkout, observability и quality gates
- довести UX, производительность, доступность и инженерную дисциплину до уровня лучших практик 2027

Важно:

- мы **не ломаем работающую систему ради моды**
- мы делаем **поэтапную контролируемую миграцию**
- мы работаем так, чтобы итоговый продукт стал удобнее, быстрее, чище и технологичнее

## Язык работы

- Всё общение между агентами, отчёты, планы, ревью и итоговые ответы — **только на русском языке**.
- Имена технологий, пакетов, классов, файлов и API оставлять в их исходной форме.

## Состав команды

В проекте используется компактная команда из 6 ролей:

1. `architect`
2. `frontend`
3. `uiux`
4. `qa_metrics`
5. `backend`
6. `devops`

Новые проектные агенты без явной необходимости не создавать.

## Архитектурные принципы

### 1. Frontend

Целевой frontend stack:

- Next.js App Router
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

Новый frontend должен:

- стать единым storefront-контуром
- быть mobile-first
- использовать server components там, где это полезно
- использовать client components только там, где реально нужна интерактивность
- строиться вокруг SSR/RSC/streaming, а не вокруг бессмысленной клиентской перегрузки
- иметь сильную SEO-структуру, чистую навигацию и понятную информационную архитектуру

### 2. Backend

Django/DRF остаётся source of truth для:

- бизнес-логики
- API-контрактов
- каталога
- корзины
- checkout
- заказов
- seller-контуров
- auth и прав доступа
- фоновых процессов
- интеграций

Не переносить критическую бизнес-логику в Next.js.

### 3. Search и recommendations

Поиск и рекомендации — стратегическая зона.

Любые изменения в этих областях должны учитывать:

- OpenSearch
- query rewrite
- fallback behavior
- reranking
- facets
- suggestions
- business ranking
- seller relevance
- recommendation surfaces

### 4. Migration discipline

Миграция выполняется волнами:

1. foundation
2. public storefront
3. auth/cart/account
4. checkout
5. seller surfaces

Запрещено:

- переписывать всё разом
- делать параллельные противоречащие UI-паттерны
- смешивать старую и новую архитектуру без явной карты перехода

## Правила качества

Каждая нетривиальная задача должна содержать:

1. цель
2. изменяемые файлы и домены
3. риски
4. план проверки
5. последствия для API, UX, observability и release

### Definition of Done

Задача считается завершённой только если:

- код написан корректно
- архитектурные границы не сломаны
- тесты добавлены или обновлены
- есть ручной сценарий проверки
- если меняется контракт — обновлена схема/документация
- если меняется UI — учтены responsive, a11y, loading, empty, error, success states
- если меняется поведение продукта — добавлены события аналитики и наблюдаемости, где это уместно

## Правила по ролям

### architect

- разбивает большие задачи
- контролирует границы доменов
- не даёт скатиться в хаотичный rewrite
- координирует агентов

### frontend

- реализует новый storefront на Next.js
- не переносит бизнес-логику из backend во frontend
- держит сильную компонентную и роутинговую дисциплину

### uiux

- отвечает за дизайн-систему
- следит за usability, clarity, accessibility, mobile UX и visual consistency
- не занимается «декоративным дизайном ради дизайна»

### qa_metrics

- отвечает за Playwright, Storybook, quality gates, Sentry, PostHog
- ищет регрессии, сломанные сценарии, слабые UX-состояния и слепые зоны в аналитике

### backend

- отвечает за DRF, доменные сервисы, OpenSearch orchestration, checkout, seller-контур, auth и контракты
- не допускает расползания бизнес-логики

### devops

- отвечает за Docker, CI/CD, env discipline, observability, release safety
- не допускает магических окружений и скрытых зависимостей

## Приоритеты продукта

Наивысший приоритет:

1. storefront migration foundation
2. API contract discipline
3. search relevance
4. recommendations foundation
5. checkout correctness
6. seller OMS/WMS direction
7. observability and analytics
8. performance and mobile UX

## Запреты

Запрещено:

- писать отчёты на английском
- плодить лишних агентов
- делать broad refactor без карты влияния
- оставлять непроверенные гипотезы как факт
- прятать риски
- считать задачу готовой без проверки сценариев
- подменять инженерное решение маркетинговой болтовнёй

## Стиль работы

Нужен стиль senior/professional:

- коротко
- точно
- с последствиями
- с инженерной честностью
- без воды

