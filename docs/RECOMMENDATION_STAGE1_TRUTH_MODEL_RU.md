# Recommendation Stage 1 Truth Model

Дата: 2026-03-28  
Статус: Stage 1 `MVP cleanup`

## 1. Truth map

| Группа | Что это на самом деле | Допустимые labels |
| --- | --- | --- |
| `personalized` | Выдача, где user-specific сигналы реально влияют на ranking | `Рекомендуем для вас`, `Под вас`, `На основе ваших действий` |
| `heuristic` | Выдача на правилах, affinity, same-seller, price band, replenishment, search recovery | `Подборка`, `Похожие`, `С этим товаром берут`, `Альтернативы`, `Замены` |
| `materialized` | Предсчитанная подборка из `RecommendationSet` или snapshot | `Популярное`, `Повторить заказ`, `Пора пополнить`, `Сохранённое` |
| `popular` | Pure popularity / trending / broad demand | `Популярное`, `Хиты`, `Часто покупают` |
| `recovery` | Возврат пользователя из search zero-result / narrow-result / cart gap | `Похожие по запросу`, `Продолжить поиск`, `Замены` |
| `bootstrap` | Временный или parity-unstable слой, который ещё не должен продаваться как зрелая персонализация | `Черновой режим`, `Технический fallback`, `Пилотная выдача` |

## 2. Что можно называть

- `personalized` можно называть только то, где `user_id` или его устойчивые сигналы реально участвуют в ranking.
- `heuristic` можно называть только как правило- или контекстно-управляемую выдачу.
- `materialized` можно называть только если выборка пришла из предсчитанного набора или снапшота.
- `popular` можно называть только если блок основан на popularity signal, без притворства персонализации.
- `recovery` можно называть только для search/cart gap scenarios.
- `bootstrap` нельзя продавать как зрелый recommender.

## 3. Запрещённые labels

- `Вы смотрели`, если нет реальной истории просмотров.
- `Из ваших подписок`, если нет реальных подписок.
- `Персонально подобрано`, если ranking не использует user-specific signal.
- `Покупают вместе`, если нет co-purchase / co-cart signal.
- `С этим товаром берут`, если это просто popularity fallback.
- `Альтернативы`, если нет substitute logic и stock-aware проверки.

## 4. Запрещённые claims

- Нельзя писать, что система «полностью персонализирована», если `user_id` не влияет на выдачу.
- Нельзя писать, что recommendation service «Amazon-like», если нет online feature store, streaming backbone и mature experimentation.
- Нельзя писать, что `bootstrap`-выдача является полноценным production recommender.
- Нельзя скрывать fallback под тем же названием секции.
- Нельзя использовать product language, который обещает больше, чем реально есть в ranking.

## 5. Truth mapping по ролям

| Роль | Что обязана использовать |
| --- | --- |
| `backend` | Истинные contract fields, `engine_source`, `service_source`, `fallback_source`, `empty_reason`, `latency_ms` |
| `frontend` | Только честные section labels и typed contracts, без подмены семантики |
| `uiux` | Только labels, которые совпадают с фактическим source и intent |
| `qa_metrics` | Truth map как baseline для dashboards, parity и go/no-go |
| `devops` | Truth map как основа rollout modes, shadow/canary и alerting |

## 6. Что считается нарушением

- Секция называется как персональная, но фактически является popularity fallback.
- Fallback остаётся под тем же label, что и исходная секция.
- Docs и UI обещают больше, чем реально делает ranking.
- `bootstrap` используется как маркетинговый термин, а не как временный режим.
- Truth map и contract envelope расходятся.

## 7. Rule of thumb

- Если signal не доказан, label не повышаем.
- Если source сменился, label тоже меняется.
- Если персонализация не измеряется, она не считается персонализацией.
