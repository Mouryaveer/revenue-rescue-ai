# Baseline — 2026-10-12

Recorded before any feature work, on `main` at `c6280fe`. The working tree already
had uncommitted user changes in `.gitignore`, `README.md`, `demo.py`, `events.py`,
`config.py`, `recovery.py` and `frontend/package*.json`. Those changes were kept.

## Environment

| Item | Value | Status |
| --- | --- | --- |
| Kiro CLI | `kiro-cli-chat 2.27.1` | available |
| Python (system) | 3.14.2, 3.11.9 (`py -0p`) | 3.11 used for `.venv` (better torch/lightgbm/pyspark wheel support) |
| `.venv` | Was a dangling symlink to `..\RevenueRescue AI\revenue-rescue-ai-fixed\.venv` | Replaced with a fresh 3.11 venv |
| Node / npm / pnpm | 24.19.0 / 11.17.0 / 10.4.1 | available |
| Docker | CLI 29.2.1 | **daemon not running**: Postgres, Redis, Kafka, HDFS and Spark containers are unavailable until Docker Desktop is started |
| Java | 24.0.2 | present; PySpark 3.5 officially supports Java 8/11/17, so local Spark needs JDK 17 |

## Python tests

```
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
165 passed, 1 warning in 6.04s
```

## Lint / security (pre-existing, not yet fixed)

`ruff check backend agents policies simulator` reported:

- 12 × F821 undefined-name: forward references to SQLAlchemy relationship types in
  `models/*.py` (no `TYPE_CHECKING` imports)
- 3 × B904 (`auth.py:63`, `razorpay_test_provider.py:137`, `tasks.py:32`)
- 1 × S324 md5 in `recovery_service.py:82`
- ~120 auto-fixable style issues (F401, I001, UP007, UP017, …)
- `pyproject.toml` uses the deprecated top-level `[tool.ruff]` select/ignore keys

`bandit -ll`: 1 high-severity finding (the md5 usage above).

## Frontend

- Old `frontend/` (legacy Next.js `app/` plus Vite `src/`): `tsc` passed, **`vite build` failed**
  (`postcss.config.js` was CommonJS inside an ESM package).
- `replaced-frontend/` (latest): `tsc` passed and `vite build` succeeded.

**Decision:** at the user's request the old frontend was removed and `replaced-frontend/`
now lives at `frontend/`. Manus-specific Vite plugins, unused template pages, and
template components were removed, and an `/api` dev proxy was added. After the move:
`tsc --noEmit` passes and `vite build` passes.

The latest frontend is a static marketing/demo site. It makes **no backend calls yet**:
there are no `fetch`/`axios` calls and no `/api` usage.

`tests/e2e/test_dashboard.spec.ts` targets old routes (`/overview`, `/cases`, `/audit`,
`/policies`) that do not exist in the new frontend. It must be rewritten in Phase 12.
