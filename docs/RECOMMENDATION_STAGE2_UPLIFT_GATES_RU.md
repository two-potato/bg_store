# Recommendation Stage 2 Uplift Gates

Дата: 2026-03-28  
Роль: `qa_metrics`  
Пакет: backlog `075`

## 1. Цель

Зафиксировать QA / metrics execution packet для Stage 2 `ranking v1` engineering track.

Stage 2 здесь не означает production rollout.  
Stage 2 означает, что мы должны честно проверить:

- ranking v1 не ломает Stage 1 baseline
- shadow parity предсказуемый
- uplift по бизнес-метрикам измерим
- canary можно запускать только после зелёной инженерной оценки

Опора:

- [RECOMMENDATION_STAGE1_CLOSEOUT_RU.md](./RECOMMENDATION_STAGE1_CLOSEOUT_RU.md)
- [RECOMMENDATION_STAGE2_EXECUTION_BOARD_RU.md](./RECOMMENDATION_STAGE2_EXECUTION_BOARD_RU.md)
- [RECOMMENDATION_PLATFORM_METRICS_QA_RU.md](./RECOMMENDATION_PLATFORM_METRICS_QA_RU.md)

## 2. Shadow parity checks для ranking v1

Ranking v1 сравнивается не с абстрактной “идеальной системой”, а со Stage 1 baseline.

### 2.1. Обязательные parity checks

- contract schema parity: `100%`
- required fields parity: `100%`
- truth label parity: `100%`
- empty/non-empty parity: разница не более `2pp`
- top-3 item overlap: не ниже `70%` для `home`, `pdp`, `cart`
- top-3 item overlap: не ниже `60%` для `search_recovery`
- source / strategy parity на уровне envelope: `100%`
- fallback disclosure parity: `100%`
- analytics linkage parity: `100%`
- latency delta: допустим, но должен быть измерим и объясним

### 2.2. Что считается shadow mismatch

- ranking v1 меняет обязательные поля envelope
- ranking v1 меняет truth labels
- ranking v1 превращает empty state в silent replacement
- ranking v1 теряет attribution linkage
- ranking v1 резко меняет top-k без понятного business rule

### 2.3. Что допускается в shadow

- minor ordering differences внутри длинных списков
- tie-break variations
- score hints
- небольшая latency variance

## 3. Uplift measurement plan

Оценка делается по surface/section/variant/source.

### 3.1. Primary metrics

- `CTR`
- `ATC rate`
- `CVR`
- `attributed GMV`
- `repeat purchase uplift`

### 3.2. Secondary metrics

- `coverage`
- `empty-rate`
- `fallback-rate`
- `diversity`
- `novelty`
- `candidate-count`
- `selected-count`
- `latency`

### 3.3. Как сравниваем

- сравнение `ranking v1` против Stage 1 baseline
- сравнение по каждой primary surface отдельно
- сравнение отдельно по `personalized`, `popular`, `substitutes`, `accessories`, `reorder`, `recovery`
- анализируем не только CTR, но и downstream `ATC / CVR / GMV`

### 3.4. Что искать в uplift

- рост CTR без просадки ATC/CVR
- рост ATC без деградации GMV
- стабильный или лучший repeat purchase uplift
- отсутствие роста fallback/empty
- отсутствие inventory contamination

## 4. Blocking vs informative metrics

### 4.1. Blocking metrics

Любая из этих метрик блокирует переход к canary:

- contract schema mismatch
- missing required fields
- forbidden label detected
- empty-rate выше `5%` на обязательных sections
- fallback-rate выше `1% / 15m`
- p95 latency выше `700ms` на `home`, `cart`, `checkout`
- p95 latency выше `800ms` на `pdp`, `reorder`, `search_recovery`
- error-rate выше `1%`
- timeout-rate выше `0.5%`
- analytics linkage mismatch
- shadow top-k overlap ниже порога из раздела 2

### 4.2. Informative metrics

Эти метрики нужны для решения, но сами по себе не блокируют canary:

- score distribution
- candidate-count by source
- selected-count
- diversity
- novelty
- reason code distribution
- source distribution
- latency delta, если она не приводит к SLO breach
- small variant-level CTR fluctuation без downstream evidence

### 4.3. Принцип

CTR без ATC/CVR не считается доказательством успеха.  
CTR может вырасти из-за label bait или placement bias, поэтому всегда смотрим связку `CTR -> ATC -> CVR -> GMV`.

## 5. Minimum sample / period

Для честной оценки ranking v1 нужен не один хороший день, а устойчивое окно.

### 5.1. Minimum period

- минимум `14` календарных дней для primary surfaces
- минимум `21` календарный день для sparse surfaces
- если выборка маленькая, окно расширяем до `28` дней

### 5.2. Minimum sample

Для каждого primary surface и каждого variant:

- не меньше `10,000` impressions
- не меньше `300` clicks, если surface достаточно трафиковый
- не меньше `100` attributed conversion events, если surface конверсионный

Если эти числа не набраны за 14 дней, окно продлевается.

### 5.3. Правило честности

Раньше времени не принимаем решение по ranking v1, если:

- сэмпл слишком мал
- нет weekday/weekend покрытия
- есть sample ratio mismatch
- есть явный traffic skew по surface или device

## 6. Что разрешает start of canary

Canary можно запускать только после:

- Stage 1 closeout green
- truth-model и label matrix утверждены
- contract baseline зелёный
- shadow parity checks из раздела 2 зелёные
- blocking metrics из раздела 4.1 не нарушены
- QA/DevOps gates готовы
- rollback owner назначен
- baseline sample для Stage 2 набран хотя бы по primary surfaces

### Canary start means

- ограниченный traffic slice
- только согласованные surfaces
- отдельный variant assignment
- отдельная observability
- немедленный rollback при breach

## 7. Что блокирует canary

- contract mismatch
- shadow mismatch
- fallback spike
- empty required section
- latency breach
- unclear attribution
- mixing UI changes with ranking changes in one test
- lack of sample
- lack of rollback ownership

## 8. Почему это ещё не Stage 2 completion

Stage 2 completion нельзя объявлять, пока не выполнены все три условия:

1. есть измеримый uplift или не хуже baseline по `CTR / ATC / CVR / GMV`
2. shadow/canary поведение подтверждено и стабильно
3. rollout gates и rollback ownership закрыты без открытых blockers

Пока у нас только engineering track и controlled evaluation.  
Это правильно и достаточно для следующего шага, но это ещё не completion.

## 9. Итог

Stage 2 `ranking v1` можно считать готовым к canary только если:

- parity зелёный
- sample достаточный
- uplift измерим
- fallback и empty-state поведение контролируемо
- business metrics не деградируют

Это и есть честная QA-граница между инженерной сборкой и production rollout.
