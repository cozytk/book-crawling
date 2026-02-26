# Deployment Flow

## Goal
Keep deployment scope isolated so one merge does not unintentionally deploy multiple systems.

## Current Integrations (verified via `gh`)
- `main` push triggers Vercel status (`context: Vercel`)
- `main` push triggers Railway status (`context: adequate-enjoyment - book-crawling`)
- No GitHub Actions existed before this setup
- `main` branch protection was not enabled before this setup

## Rules
1. One PR should target one deploy scope:
   - `api`: `api/`, `crawlers/`, `models/`, `crawler_logging/`, `main.py`, `pyproject.toml`, `uv.lock`, `railway.toml`
   - `web`: `web/`
   - `db`: `supabase/`
2. If a mixed deploy is intentional, add the label `mixed-deploy-ok`.
3. Merge through PR only.

## GitHub Workflows
- `CI`:
  - `backend-tests`: `uv sync --frozen` + `uv run pytest -q`
  - `web-build`: `npm ci` + `npm run build` in `web/`
- `Deploy Scope Guard`:
  - Fails PR when multiple deploy scopes are changed without `mixed-deploy-ok`

## Suggested Labels
- `deploy:api`
- `deploy:web`
- `deploy:db`
- `mixed-deploy-ok`

## Example
- API fix only:
  - open PR with `deploy:api`
- Web UI change only:
  - open PR with `deploy:web`
- API + Web emergency hotfix:
  - open one PR and add `mixed-deploy-ok`
