[x] 001 - знакомство с агентами - ceo - 2026-03-27 18:17 MSK
[x] 002 - переинициализация UIUX - ceo - 2026-03-27 18:17 MSK
[x] 003 - переинициализация FRONTEND - ceo - 2026-03-27 18:17 MSK
[x] 004 - старт рабочего пакета discovery surfaces нового storefront - ceo - 2026-03-27 18:18 MSK
[x] 005 - UX-переупаковка discovery surfaces: search, category, brand, collection - uiux - 2026-03-27 18:18 MSK
[x] 006 - frontend-реализация discovery wave на Next storefront - frontend - 2026-03-27 18:18 MSK
[x] 007 - UX-архитектура migration wave для cart, orders и buyer account на Next storefront - uiux - 2026-03-27 18:45 MSK
[x] 008 - frontend partial delivery для cart, buyer account shell и orders list на Next storefront с опорой на legacy storefront - frontend - 2026-03-27 18:45 MSK
[x] 009 - архитектурный audit API gap'ов для cart, orders и buyer account migration - architect - 2026-03-27 18:45 MSK
[x] 010 - backend-расширение контрактов для cart, orders и buyer account при выявленных блокерах - backend - 2026-03-27 18:45 MSK
[x] 011 - backend bridge для full buyer orders detail, reorder и order actions в Next storefront - backend - 2026-03-27 19:09 MSK
[x] 012 - architect-декомпозиция оставшихся buyer account API gaps: favorites, lists, saved searches, account settings, analytics contract - architect - 2026-03-27 19:11 MSK
[x] 013 - frontend-дозавершение buyer account и orders detail после новых bridge-контрактов - frontend - 2026-03-27 19:09 MSK
[x] 014 - qa_metrics smoke и quality gates для Next cart/account/orders wave - qa_metrics - 2026-03-27 19:09 MSK
[x] 015 - backend phase 2 slice A для buyer account settings: settings, preferences, addresses, legal-entities, notifications - backend - 2026-03-27 19:19 MSK
[x] 016 - backend phase 2 slice B для favorites, lists, saved searches и analytics ingest - backend - 2026-03-27 19:23 MSK
[x] 017 - devops: внешний nginx route switch для Next buyer wave (`cart/account/orders/tools`) - devops - 2026-03-27 19:51 MSK
[x] 018 - backend: исправить auth return flow в storefront `login_url`, чтобы next вёл на buyer page, а не на API endpoint - backend - 2026-03-27 19:51 MSK
[x] 019 - frontend: подключить analytics ingest buyer wave и исправить buyer links в site shell - frontend - 2026-03-27 19:51 MSK
[x] 020 - qa_metrics: обязательный authenticated E2E smoke для buyer critical path - qa_metrics - 2026-03-27 19:51 MSK
[x] 021 - devops/frontend: убрать внешний login redirect blocker для buyer wave (`/account/login` не должен уводить браузер на `localhost:8000`) - devops/frontend - 2026-03-27 23:27 MSK
[x] 022 - frontend/backend: точный `next` для unauth buyer blockers (`/cart`, `/account`, tools`) вместо fallback `next=/` - frontend/backend - 2026-03-27 23:27 MSK
[x] 023 - frontend: убрать `localhost` из SSR login CTA buyer blockers и сделать same-origin fallback login URL - frontend - 2026-03-27 23:40 MSK
[x] 024 - qa_metrics: закрепить buyer critical path как automated smoke/gate в репо и CI - qa_metrics - 2026-03-27 23:40 MSK
[x] 025 - devops: провести внешний `/legacy/*` через Next rewrite, чтобы same-origin buyer login CTA не давали `404` - devops - 2026-03-27 23:50 MSK
[ ] 026 - qa_metrics/devops: подключить `npm run smoke:buyer` как обязательный CI gate на полном buyer stack - qa_metrics/devops - 2026-03-27 23:54 MSK
[x] 027 - architect: рамка полного редизайна Servio в логике Яндекс Маркета / grocery UX и этапность первого шага - architect - 2026-03-27 23:55 MSK
[x] 028 - uiux: 3 UX-концепции каталога (`A/B/C`) с единой дизайн-системой редизайна Servio - uiux - 2026-03-27 23:55 MSK
[x] 029 - frontend: реализация `/catalog-a`, `/catalog-b`, `/catalog-c` и переключателя только после утверждённого UX - frontend - 2026-03-27 23:55 MSK
[x] 030 - frontend/devops: обновление storefront на актуальные Node.js LTS и Next.js Active LTS в рамках пакета редизайна - frontend/devops - 2026-03-27 23:55 MSK
[ ] 031 - qa_metrics: comparison matrix и runtime smoke для `/catalog-a`, `/catalog-b`, `/catalog-c` на desktop/mobile - qa_metrics - 2026-03-28 00:05 MSK
[x] 032 - frontend: добавить на сайт в меню отдельные ссылки на `/catalog-a`, `/catalog-b`, `/catalog-c` - frontend - 2026-03-28 00:19 MSK
[x] 033 - devops: вывести `/catalog-a`, `/catalog-b`, `/catalog-c` наружу через localhost/nginx same-origin - devops - 2026-03-28 00:19 MSK
[x] 034 - uiux: refinement варианта `catalog-c` для grocery UX — навбар, сортировка, фильтры - uiux - 2026-03-28 00:23 MSK
[x] 035 - frontend: внедрение refinement-пакета для `catalog-c` после UX-фиксации - frontend - 2026-03-28 00:22 MSK
[x] 036 - uiux: новый `catalog-d` как mobile-only вариант без desktop-компромиссов - uiux - 2026-03-28 00:32 MSK
[x] 037 - frontend: реализация `/catalog-d` и ссылки на него после UX-фиксации - frontend - 2026-03-28 00:32 MSK
[x] 038 - frontend: добавить `catalog-d` в глобальное меню сайта, а не только во внутренний switcher - frontend - 2026-03-28 00:43 MSK
[x] 039 - devops: вывести `/catalog-d` наружу через localhost/nginx same-origin - devops - 2026-03-28 00:43 MSK
[x] 040 - architect: перезапуск редизайна каталога как desktop-only пакета из 4 новых концепций - architect - 2026-03-28 09:53 MSK
[x] 041 - uiux: 4 новых desktop-only концепции каталога с нуля, без опоры на A/B/C/D - uiux - 2026-03-28 09:53 MSK
[ ] 042 - frontend: реализация 4 новых desktop-only вариантов только после нового UX approval - frontend - 2026-03-28 09:53 MSK
[x] 043 - architect: целевая API-архитектура Servio, карта контрактов и план выноса search/recommendations в FastAPI-микросервисы - architect - 2026-03-28 10:02 MSK
[x] 044 - backend: аудит текущего API, gap-list и реализация полного контрактного слоя для search/recommendations + Swagger map - backend - 2026-03-28 10:02 MSK
[x] 045 - devops: infra/wiring для FastAPI search/recommendation services, compose/env/runtime/rollback - devops - 2026-03-28 10:02 MSK
[x] 046 - backend/docs: привести в порядок API-документацию, OpenAPI/Swagger и карту сервисов - backend - 2026-03-28 10:02 MSK
[x] 047 - backend/devops: интеграционная проверка `search/recommendation` contract slice в поднятом окружении (db/redis/opensearch/services) - backend/devops - 2026-03-28 10:21 MSK
[x] 048 - architect: parity/cutover план для FastAPI search/recommendations с shadow mode, метриками и rollback - architect - 2026-03-28 11:17 MSK
[ ] 049 - backend: довести parity FastAPI search/recommendations с Django engine (ranking, attribution, facets, fallback semantics) - backend - 2026-03-28 11:17 MSK
[x] 050 - devops: rollout/canary/shadow wiring и режимы безопасного включения FastAPI services - devops - 2026-03-28 13:02 MSK
[x] 051 - qa_metrics: parity quality gates и сравнение `django-inline` vs `fastapi` по search/recommendations - qa_metrics - 2026-03-28 11:17 MSK
[x] 052 - architect: полный управленческий аудит recommendation platform и рамка evolution roadmap в 3 этапа - architect - 2026-03-28 13:35 MSK
[x] 053 - backend: аудит recommendation data/API/business-rules и пакет backend-требований для evolution roadmap - backend - 2026-03-28 13:35 MSK
[x] 054 - architect/backend: strategy-пакет по retrieval/ranking/post-ranking, candidate sources, popularity/substitutes/accessories и personalization roadmap - architect/backend - 2026-03-28 13:35 MSK
[x] 055 - frontend: план recommendation surfaces для storefront, честные section labels, instrumentation и empty states - frontend - 2026-03-28 13:35 MSK
[x] 056 - uiux: UX-аудит recommendation sections и правила честной подачи блоков пользователю - uiux - 2026-03-28 13:35 MSK
[x] 057 - qa_metrics: метрики качества, деградации, валидации и dashboard plan для recommendation surfaces - qa_metrics - 2026-03-28 13:35 MSK
[x] 058 - devops: observability/logging/latency/rollout/prod-readiness план recommendation platform - devops - 2026-03-28 13:56 MSK
[x] 059 - architect/backend/uiux/frontend/qa_metrics/devops: выполнить Stage 1 `MVP cleanup` recommendation platform с truth-model, contract freeze, honest labels, event taxonomy и operational dashboards - cross-team - 2026-03-28 14:10 MSK
[ ] 060 - architect/backend/qa_metrics/devops/frontend: выполнить Stage 2 `Strong marketplace recommender` с candidate normalization, ranking v1, business-rules layer, shadow/canary rollout и uplift validation - cross-team - 2026-03-28 14:10 MSK
[ ] 061 - architect/backend/devops/qa_metrics: выполнить Stage 3 `Near-Amazon architecture` только после подтверждённого Stage 2 uplift и readiness по streaming/features/experimentation - cross-team - 2026-03-28 14:10 MSK
[x] 062 - architect: зафиксировать Stage 1 truth-model recommendation platform как source-of-truth для labels, contracts и rollout - architect - 2026-03-28 14:18 MSK
[x] 063 - backend: заморозить Stage 1 recommendation contract envelope и event taxonomy (`recommendation_id`, `impression_id`, `engine_source`, `service_source`, `fallback_source`, `empty_reason`, `latency_ms`) - backend - 2026-03-28 14:18 MSK
[x] 064 - uiux: утвердить Stage 1 честные labels/disclosure/empty-state rules для recommendation sections - uiux - 2026-03-28 14:18 MSK
[x] 065 - qa_metrics/devops: закрепить Stage 1 dashboards, alerts и rollout gates по recommendation surfaces после contract freeze - qa_metrics/devops - 2026-03-28 14:18 MSK
[x] 066 - frontend: принять Stage 1 section contract и зафиксировать storefront integration rules/instrumentation plan - frontend - 2026-03-28 14:18 MSK
[x] 067 - architect: Stage 1 closeout review и решение о readiness к старту Stage 2 - architect - 2026-03-28 14:18 MSK
[x] 068 - architect: разложить Stage 2 `Strong marketplace recommender` в execution board с пакетами работ, зависимостями и rollout-порядком - architect - 2026-03-28 14:34 MSK
[ ] 069 - backend: Stage 2 candidate normalization и ranking v1 baseline для recommendation surfaces - backend - 2026-03-28 14:34 MSK
[ ] 070 - backend/uiux: Stage 2 business-rules layer v1 для substitutes/accessories/popular/personalized surfaces - backend/uiux - 2026-03-28 14:34 MSK
[ ] 071 - qa_metrics/devops: Stage 2 shadow/canary execution gates, parity checks и uplift measurement plan - qa_metrics/devops - 2026-03-28 14:34 MSK
[ ] 072 - frontend: Stage 2 storefront adoption plan для updated recommendation surfaces и instrumentation rollout - frontend - 2026-03-28 14:34 MSK
[ ] 073 - architect: Stage 2 closeout criteria и boundary между engineering-track и production-rollout - architect - 2026-03-28 14:34 MSK
[ ] 074 - backend: Stage 2 implementation package A — candidate normalization и ranking v1 baseline в recommendation engine - backend - 2026-03-28 14:39 MSK
[x] 075 - qa_metrics: Stage 2 implementation package A — shadow parity/uplift measurement spec и execution gates для ranking v1 - qa_metrics - 2026-03-28 14:39 MSK
