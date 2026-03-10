# Release Checklist (`dev` -> `main` -> `prod`)

## 1. Before PR to `main`

- [ ] PR source branch is `dev` (or approved hotfix branch)
- [ ] CI is green
- [ ] Required migrations are committed
- [ ] New env vars documented in examples
- [ ] Frontend checked on desktop + mobile + Telegram WebApp
- [ ] Metrics/logging impact reviewed

## 2. Merge to `main`

- [ ] PR approved
- [ ] Branch protection passed
- [ ] Merge method follows team policy

## 3. Automatic production deploy (GitHub Actions)

- [ ] Workflow `.github/workflows/deploy.yml` started on `main` push
- [ ] Deploy job finished successfully
- [ ] `https://potatofarm.ru/health/` is `200`
- [ ] Static and migrations applied

## 4. Post-deploy smoke checks

- [ ] Main page loads
- [ ] Login / auth flow works
- [ ] Catalog and product pages load
- [ ] Cart and checkout base flow works
- [ ] Bot endpoints healthy
- [ ] Key Grafana dashboards have data

## 5. Rollback (if needed)

- [ ] Identify last stable `main` commit SHA
- [ ] Re-run deploy with stable SHA
- [ ] Confirm health and critical paths again

