# Frontend Audit (2026-03-07)

## Scope
- Templates: `backend/templates/shopfront/**`
- Styles: `backend/static/shopfront/theme.css`, `backend/static/shopfront/unified-theme.css`
- Shared frontend scripts used by templates

## Key Findings

1. Cascade conflicts between legacy and new theme layers
- `theme.css` still contains warm palette and old visual tokens.
- `unified-theme.css` overrides many of these with `!important`.
- Result: unstable behavior in navbar/mobile/cart badge depending on rule order.

2. Extremely high style override pressure
- `unified-theme.css` contains >1200 `!important`.
- This makes refactoring risky and causes regressions from small changes.

3. Duplication of critical UI rules
- Repeated rules for:
  - `.mobile-nav-mint-link*`
  - `.mobile-cart-badge`
  - `.cart-control--icon`
- Same selectors appear in multiple sections with different values.

4. Template duplication in mobile dropdown menu
- `components/navbar.html` had many repeated anchor blocks with duplicated icon+label markup.
- This increases maintenance cost and drift risk.

5. Runtime/static sync fragility in dev
- Template/CSS updates were not always reflected due to stale static layer and cache.
- Needs strict “last layer” stylesheet for safe hotfixes.

## Refactoring Performed (Phase 1)

1. Template component extraction
- Added reusable item component:
  - `backend/templates/shopfront/components/mobile_menu_item.html`
- Replaced repeated mobile dropdown menu links in:
  - `backend/templates/shopfront/components/navbar.html`

2. Introduced stable final CSS layer
- Added temporary final layer:
  - `backend/static/shopfront/refactor.frontend.css`
- Connected last in:
  - `backend/templates/shopfront/base.html`

3. Base template normalization
- `base.html` now loads frontend layers in deterministic order:
  - `theme.css` -> `unified-theme.css` -> `refactor.frontend.css`

## Refactoring Performed (Phase 2)

1. Removed legacy cascade conflict
- Stopped loading `theme.css` in runtime base template.
- Frontend now uses a single project stylesheet:
  - `backend/static/shopfront/unified-theme.css`

2. Consolidated final overrides into single stylesheet
- Merged critical stabilization rules directly into `unified-theme.css`:
  - `--u26-border` canonical value
  - mobile nav/cart badge visual contract
  - cart control state contract (`add` icon vs `stepper`)
- Removed temporary layer file:
  - `backend/static/shopfront/refactor.frontend.css`

3. Runtime sync and smoke check
- Synced updated template/CSS into running dev containers.
- Restarted `backend` and `nginx`.
- Verified `/catalog/` now references only `unified-theme.css?v=20260307-phase2`.
- Ran `python manage.py check` successfully.

## Remaining Technical Debt

1. `theme.css` and `unified-theme.css` should be split into:
- `tokens.css`
- `layout.css`
- `components.css`
- `utilities.css`

2. Replace `!important` strategy with predictable specificity:
- BEM-like namespace
- component-level wrappers

3. Add visual regression checks:
- snapshot tests for:
  - header
  - mobile nav
  - catalog cards
  - cart controls

4. Remove dead style blocks and repeated rule clusters inside `unified-theme.css`.
5. Move pytest-based UI/HTML tests into container image or CI test stage (container currently lacks `pytest`).

## Quick Metrics
- Template files in `shopfront`: 66
- Static files in `shopfront`: 27
- `!important` count:
  - `theme.css`: 166
  - `unified-theme.css`: 1253
