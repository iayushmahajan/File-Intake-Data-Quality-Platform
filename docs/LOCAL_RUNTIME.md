# Dedicated Reconcile Workbench local runtime

Project: **reconcile-workbench**. This is the normal new local runtime, separate from the
preserved, stopped `file-intake-processing-service` project. Do not use the old `run.sh` or
combine `compose.reconcile.yaml` with the original Compose file. Original transaction records
and files were not migrated; the new database starts empty, including its legacy UI route.

## Start and access

From the repository root:

```bash
bash scripts/reconcile.sh init
bash scripts/reconcile.sh up
bash scripts/reconcile.sh ps
```

In another terminal:

```bash
bash scripts/reconcile.sh frontend
```

- Application: **http://127.0.0.1:5174/**
- API health: http://127.0.0.1:8011/health
- OpenAPI: http://127.0.0.1:8011/docs

Both exact frontend origins, `http://127.0.0.1:5174` and `http://localhost:5174`, are allowed by the dedicated API CORS configuration. Vite binds
loopback, uses installed dependencies, and explicitly overrides the old frontend API URL.
The API publishes only loopback port 8011. PostgreSQL/Redis have no host ports.

The launcher fixes Docker context `default`, project name and standalone Compose file, and
clears inherited shell settings. `init` creates `.env.reconcile.local` with a random database
password and mode 0600. It is ignored by Git, outside the backend build context, and never
printed. Preserve this file with the new database volumes; deleting/regenerating it does not
rotate a password in an already initialized PostgreSQL volume. AI credentials remain empty.
`config` is quiet by default. Resolved JSON configuration contains the password: do not paste
it into reports or logs. No original `.env` is edited or inherited by Compose.

`up` builds the API image first, then recreates only the dedicated project containers from
that image, retaining all three named volumes. Explicit recreation avoids stale API/worker
image identities with this Compose/image-store combination. It may create/update **only the new project's** services and runs startup migrations
against its dedicated database. No dependency or application architecture changes were needed.

## Resource ownership

| Resource | Identity |
|---|---|
| Database / user | `reconcile_workbench` / `reconcile_workbench` |
| PostgreSQL volume | `reconcile-workbench_postgres_data` |
| Redis volume | `reconcile-workbench_redis_data` |
| Upload/export volume | `reconcile-workbench_app_data` mounted at `/app/data` |
| Broker / queue | `redis://redis:6379/0` / `reconcile-workbench` |
| Private data network | `reconcile-workbench_private` (internal) |
| API ingress network | `reconcile-workbench_ingress` (API only) |
| Backend image | `reconcile-workbench-backend:local` |

DB, Redis, worker and dispatcher attach only to the private network. The API also uses a
separate ingress bridge: on this Docker engine an internal-only network did not activate its
host-port mapping. Adding API-only ingress fixed real host/browser access. No service joins
an original network or mounts original volumes, `backend/data`, benchmark directories or the
Docker socket. This is resource/configuration isolation on the same daemon, not a separate
security boundary against the host administrator.

Startup calls Alembic automatically; the current new database reached **0006**. This does not
prove PostgreSQL concurrency/locking correctness or migrate the original database. The original
five containers and their volume metadata were compared before/after; original application-file
hashes and modification times were unchanged. Original volume contents were not mounted or
read for a block-level checksum.

## Read-only checks

```bash
bash scripts/reconcile.sh ps
bash scripts/reconcile.sh config --quiet
bash scripts/reconcile.sh logs api worker dispatcher

docker --context default exec reconcile-workbench-api-1 alembic current
docker --context default exec reconcile-workbench-redis-1 redis-cli ping
docker --context default exec reconcile-workbench-worker-1 \
  celery -A app.core.celery_app:celery_app inspect active_queues --timeout 5
curl --fail http://127.0.0.1:8011/health
```

The services' existing health checks cover PostgreSQL, Redis, API, worker ping and dispatcher
heartbeat. Docker's Compose labels identify the `reconcile-workbench` group; Docker Desktop GUI
visibility itself was not inspected. Local browser verification used real HTTP responses with
no API interception, no uploads, no review writes and no AI calls. History was genuinely empty.

## Prepared dirty benchmark and manual walkthrough

Verified local-only input:

```text
/home/ayush/.local/share/reconcile-workbench-benchmarks/observed/dirty.csv
154776 bytes
SHA-256: 1b5c1afa10aa0e7c20fd7e14d05c56772715b2771aa0f5fa67ed1709e1eecd46
```

It was obtained only from the observed file URL pinned in `flights-source-manifest.json`.
Storage directories are private and the file is mode 0600. No clean reference was downloaded,
mounted or uploaded. The benchmark path is not runtime storage. Keep it for local research
only; the third-party rights caveat in `FLIGHTS_BENCHMARK.md` still applies. The backend build
excludes runtime storage, environment files, SQLite files/journals and dirty/clean benchmark
filenames. Neither the dataset nor generated exports belongs in Git.

Open the application → Datasets → select this dirty CSV → Import observations → wait for
completed processing → inspect raw observations → Investigate evidence → review a selected
field → explicitly submit a human decision → History → acknowledge the conservative export
policy → Create frozen export → download reviewed CSV, exceptions CSV and provenance JSON.
Import acceptance is not completion; completion is not reconciliation; source consensus and AI
proposals are not ground truth. AI is deliberately unavailable in this initial setup, so manual
candidate/manual-clock review remains available. This setup did not upload the file or perform
the workflow for you. The first manual upload is yours to initiate.

## Stop and restart without deleting data

```bash
# Stops only reconcile-workbench, preserving its containers and volumes.
bash scripts/reconcile.sh stop

# Restarts those same containers and waits for health.
bash scripts/reconcile.sh start
```

These commands were exercised on the new runtime. For source/configuration updates use `up`
again, which rebuilds only its backend image. Stop the frontend with Ctrl+C in its own terminal;
restart it with `bash scripts/reconcile.sh frontend`. The frontend started during setup is an
owned Vite terminal session; if stopping it by PID from another terminal, first verify that the
PID's command is this repository's Vite on 5174. Do not kill arbitrary port owners.

No removal/prune/down-with-volumes command is provided. Do not delete original resources or
change their project identity. Preserve the new environment settings and volumes across future
manual sessions. Real-provider use, full PostgreSQL concurrency testing, authentic frozen
benchmark evaluation and any original-data migration remain separately gated.
