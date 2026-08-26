# Contributing

## Branching

- Main development branch: `dev`
- Production branch: `main`
- Merge to `main` only through PRs

## Required Before Merge

- Tests pass
- Ruff passes
- New behavior is covered by tests where practical
- README/docs are updated when behavior or operations change
- Release/deploy flows must install dependencies via lockfiles (`uv.lock`, frontend lockfile)

## Code Guidelines

- Keep views thin
- Prefer service/query helpers for business logic
- Add explicit type hints for new public service functions (including return types)
- Validate uploads and external inputs on the server
- Do not introduce raw SQL unless there is a measured reason
- Keep compatibility imports during package moves until tests are migrated

## Review Focus

- Regressions in catalog, checkout, seller cabinet
- Query growth / N+1 risks
- Security of browser POST endpoints and uploads
- Deploy/runtime impact
