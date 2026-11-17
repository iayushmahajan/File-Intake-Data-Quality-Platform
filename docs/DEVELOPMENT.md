# Development and operations

The normal local runtime is **`reconcile-workbench`**, defined by `compose.reconcile.yaml` and
`scripts/reconcile.sh`. The original `file-intake-processing-service` project, volumes and
`backend/data` are separate retained resources. Do not combine the two Compose files, use the
old `run.sh` for this runtime, or rename resource identities as a cosmetic cleanup.

## Setup and access

Prerequisites: Docker with Compose v2 and context `default`, Node.js 22, pnpm **10.32.1**, and
Python 3.10+ for scripts/tests. From the repository root, for a **new dedicated environment**:

```bash
pnpm --dir frontend install --frozen-lockfile
bash scripts/reconcile.sh init
bash scripts/reconcile.sh config
bash scripts/reconcile.sh up
bash scripts/reconcile.sh ps
```

In another terminal:

```bash
bash scripts/reconcile.sh frontend
```

Application: **http://localhost:5174/** or http://127.0.0.1:5174/.
API: http://127.0.0.1:8011/health and http://127.0.0.1:8011/docs.
PostgreSQL and Redis have no published host ports. Services are `db`, `redis`, `api`, `worker`
and `dispatcher`; the frontend runs on the host using existing Vite, not a second application.

`init` preserves an existing regular mode-0600 settings file or creates ignored
`.env.reconcile.local` with a random database password. Preserve it with the database volumes:
regenerating it does not change a password inside an initialized PostgreSQL database.
`config` is quiet by default; explicit resolved output contains secrets and must not be published.
The launcher clears inherited shell configuration and fixes project/file/context explicitly.
Root/backend/frontend environment examples describe other local configurations; they do not
silently replace the dedicated launcher settings.

`up` builds the backend image then recreates only dedicated containers, retaining storage.
API startup automatically runs Alembic upgrades. For an already provisioned stopped environment,
`bash scripts/reconcile.sh start` starts its existing containers. Stop without removing volumes:

```bash
bash scripts/reconcile.sh stop
```

Stop host Vite with Ctrl+C; restart with `bash scripts/reconcile.sh frontend`. For deliberate
backend source updates use `up` only after the migration/storage gate below. These are operator
instructions, not permission to recreate an existing environment during a documentation task.

## Configuration and storage

| Setting/resource | Dedicated value |
|---|---|
| PostgreSQL database / user | `reconcile_workbench` / `reconcile_workbench` |
| PostgreSQL volume | `reconcile-workbench_postgres_data` |
| Redis volume | `reconcile-workbench_redis_data` |
| Upload/export volume | `reconcile-workbench_app_data` → `/app/data` |
| Broker / queue | `redis://redis:6379/0` / `reconcile-workbench` |
| Private network | `reconcile-workbench_private` (internal) |
| API-only ingress | `reconcile-workbench_ingress` |
| Backend image | `reconcile-workbench-backend:local` |
| Frontend API URL | `VITE_API_BASE_URL=http://127.0.0.1:8011`, set by launcher |
| Dedicated CORS origins | `http://127.0.0.1:5174,http://localhost:5174` |

API/worker/dispatcher share the new app volume, database, broker and queue. No original volume,
`backend/data` bind mount, benchmark directory or Docker socket is mounted. DB/Redis/worker/
dispatcher use only the private network; API also has ingress for loopback publication.
All processes must use compatible backend/schema versions before accepting Flights work.

`app/core/config.py` supports `DATABASE_URL`, `DATA_DIR`, `MAX_UPLOAD_BYTES` (10 MiB default),
`CELERY_BROKER_URL`, `CELERY_QUEUE`, job retry/lease settings and comma-separated `CORS_ORIGINS`.
The general CORS default permits localhost/127.0.0.1 on 5173; the dedicated Compose override is
5174. Overrides replace defaults, trim whitespace and ignore empty entries.
Never print provider keys/database URLs containing passwords.

The dedicated Compose explicitly leaves `OPENAI_API_KEY` empty. A host key alone does not enable
AI because the launcher clears inherited settings. Provider/model configuration needs a separately
reviewed isolated setup; see [AI boundaries](AI_AND_EVALUATION.md). No public access-control/RBAC
system is implemented: keep write/export/cost-incurring endpoints local.

## Safe verification

Python dependency setup, if needed:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

From the repository root:

```bash
timeout 180s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests -q
python3 -B -m unittest discover -s scripts -p 'test_flights_*.py' -q
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/path/to/existing/chromium pnpm --dir frontend test:foundation
bash -n scripts/reconcile.sh
git diff --check
```

Backend `conftest.py` sets a new temporary SQLite database/storage, memory transport and empty AI
key **before imports**; its schema creation/drop/migration affects only that state. It deliberately
overrides a supplied `DATABASE_URL`, so this suite is not a PostgreSQL concurrency test. TestClient
can stall in a restricted sandbox; use a bounded approved rerun with the same isolated fixtures,
optionally `-o faulthandler_timeout=45`, and report timeouts as failures of that run.
The standalone script tests use synthetic external temporary files without app startup.
The foundation harness starts its own temporary Vite/Chromium, intercepts synthetic APIs and
closes only its own processes. Its outputs stay under `/tmp`, not in the product gallery.

`pnpm --dir frontend test:e2e` and `scripts/verify_async_stack.py` are **state-changing integration
checks**, not routine read-only checks: they create services/resources, can occupy API port 8011,
and exercise worker death/broker loss before removing their owned resources. Inspect them and
prove isolation before separately authorizing execution. No normal API startup is needed for
ordinary isolated unit/API tests. Current results are in [validation](VALIDATION.md).

## Migration, backup and recovery gate

Head is `0006`, chain `0001 → 0002 → 0003 → 0004 → 0005 → 0006`. Startup
`app/main.py::lifespan` calls `migrate_database`; starting the API is a migration operation.
0002 introduced durable execution, 0003 transaction records/templates, 0004 Flights observations
and legacy-preserving kind/hash/issues fields, 0005 AI history/claim constraints, and 0006 review
and frozen-export metadata. Destructive downgrades are disabled; rollback requires an approved
restore with retention of newer history/files, not a casual Alembic downgrade.

Before upgrading retained data:

1. Verify actual project/container labels, database/user/revision, mounts and storage ownership.
2. Coordinate intake/review/export writes and workers; back up PostgreSQL **and** original/output
   file storage plus required private configuration. A database-only backup cannot restore artifacts.
3. Restore into separately authorized disposable resources with unique identity, ports, volumes,
   queue and `DATA_DIR`; verify row/file hashes and legacy accessibility there.
4. Exercise sequential migrations and preservation constraints, PostgreSQL concurrent AI claims,
   review revisions, idempotent retries/export races and Redis/Celery interruption/recovery.
5. Approve the target rollout only after restore tests and a clear maintenance/rollback plan.

SQLite is retained for tests/single-worker development, not multi-process scaling. Do not move
existing SQLite or old Compose data to PostgreSQL by merely changing a URL/project name.
No automatic retention/orphan cleanup or terminal-job retry UI is provided.

## Troubleshooting

Read-only checks for the dedicated project:

```bash
bash scripts/reconcile.sh ps
bash scripts/reconcile.sh logs api worker dispatcher
bash scripts/reconcile.sh config
curl --fail http://127.0.0.1:8011/health
docker --context default exec reconcile-workbench-api-1 alembic current
docker --context default exec reconcile-workbench-redis-1 redis-cli ping
```

- API docs load but browser requests fail: inspect the actual tab origin, request URL and Console/
  Network error. localhost and 127.0.0.1 are distinct origins; compare exact CORS settings and
  `VITE_API_BASE_URL`. A stopped browser wait does not cancel accepted server work.
- Pending/queued jobs: inspect dispatcher/worker health and matching queue/broker/database.
  Waiting expires after its configured limit; lease recovery requires the dispatcher to run.
- Processing after worker death: await lease expiry/recovery; do not edit job rows or delete inputs.
- Missing input/output: verify the shared app volume. Missing input fails processing; missing
  published artifacts return safe errors rather than erasing history. Restore ownership, not fake files.
- Repeated timeouts: inspect file complexity/memory; change hard limit and lease together only
  deliberately. Keep clocks aligned for UTC lease checks.
- Docker unavailable in WSL: verify Docker Desktop integration/context. Diagnose client credential
  helpers without overwriting the user's Docker settings or touching unrelated projects.
- Read/write conflicts: refresh after 409. For an unknown write outcome retain the exact request
  ID/payload; do not submit a different decision merely to clear the message.
