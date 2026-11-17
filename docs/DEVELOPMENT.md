# Legacy transaction development reference

For column mapping, saved templates, record exploration and correction workflows, see the [import workspace guide](IMPORT_WORKSPACE.md).

This preserves transaction-specific configuration, CSV rules and local Python setup. The current Flights product and contracts are in the [README](../README.md). API startup applies migrations: follow the [backup and rollout gates](HANDOFF.md) before executing startup commands against any existing storage.

## CSV schema and validation

All headers below are required and case-sensitive. Duplicate headers are rejected. Extra named columns are accepted but not preserved in outputs. Rows with a different field count are rejected. A header-only or empty file is a failed job.

| Field | Rule |
|---|---|
| `customer_id` | Nonempty; repeated customer IDs are allowed across transactions |
| `email` | Nonempty, maximum 254 characters; basic structural check excluding whitespace and repeated `@` |
| `country` | DE, FR, IN, US or GB |
| `signup_date` | Calendar date parsed with `%Y-%m-%d` |
| `order_amount` | Finite, non-negative decimal representable in numeric profiles |
| `currency` | EUR, USD or INR |
| `payment_method` | card, paypal or bank_transfer |
| `order_status` | completed, pending or cancelled |
| `product_category` | Nonempty; free text |
| `quantity` | Positive integer |
| `discount_percent` | Finite decimal from 0 through 100 |
| `last_login_date` | Calendar date, on or after signup |

Cross-field rules:

- German and French records require EUR. Other allowed countries can use any supported currency; this is not a universal currency-conversion policy.
- Completed orders require a nonzero amount.
- Later records with identical required values after trimming/case folding are rejected as duplicate records. Customer ID alone is not a transaction identity.

Normalization uppercases IDs/countries/currencies, lowercases email/payment/status, trims categories, formats dates, and writes amount/discount to two decimal places. Rejected rows retain their supplied field values and list every detected error. `row_number` counts logical CSV records including the header, so the first data record is 2; multiline quoted fields are one record.

Email validation is a structural check, not a deliverability check. No external lookup is performed.

## Deterministic quality score

The platform score is calculated by backend code and persisted. AI scores do not replace it.

| Dimension | Measurement | Weight |
|---|---|---:|
| Validity | Accepted records / all records × 100 | 60% |
| Completeness | Nonempty required cells / all required cells × 100 | 20% |
| Uniqueness | (All records − later duplicate records) / all records × 100 | 10% |
| Anomaly health | Accepted records without heuristic anomalies / accepted records × 100 | 10% |

Dimension values are rounded to two decimals; the weighted overall score is rounded to one decimal. If there are no accepted records, anomaly health is unavailable and remaining weights are normalized to sum to one. Empty datasets have no score. Failed jobs do not display a quality score. Completeness and uniqueness are measured over all parsed data records; profiles and anomaly health describe accepted records only.

These dimensions overlap deliberately: validity is the dominant gate, while the remaining dimensions explain additional aspects of quality. The weights are a documented product choice, not a statistical quality guarantee.

## Analytics and visualizations

- Acceptance donut with the same counts and percentages available as text.
- Error-category bars; one rejected row can produce several issues.
- Numeric count/min/max/average for amount, quantity and discount.
- Top three values for country, currency, payment method, status and category.
- Repeated error combinations and searchable preview of the first 100 rejected records.
- Anomalies: amount above 1,000 in its original currency, quantity above 20, discount above 50%. These review signals do not reject records.
- First 100 anomaly signals retained for display; total anomaly count remains available.

Order amounts are **not converted between currencies**. Aggregate amount statistics and thresholds are descriptive source-unit measurements, not comparable financial totals. Anomaly record numbers refer to the original logical CSV records.

## Alternative local Python development — SQLite

Use one worker process for SQLite; PostgreSQL is the preferred multi-process configuration. SQLite still serializes writers and is not intended for scaling worker concurrency.

```bash
# Repository root: start only the local Redis broker
# Use a separate Compose project if another application stack is already running.
docker compose up -d redis
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

In two additional terminals, each in `backend/` with `.venv` activated:

```bash
celery -A app.core.celery_app:celery_app worker --loglevel=INFO --concurrency=1
```

```bash
python -m app.dispatcher
```

Then start the frontend with `pnpm dev` in `frontend/`. API, worker and dispatcher must use the same `DATABASE_URL`, `DATA_DIR`, broker and queue configuration. `backend/.env.example` uses localhost Redis; the repository-root `.env.example` uses `redis://redis:6379/0` for Compose. Compose reads `CELERY_BROKER_URL` from the environment with that service hostname as its default. If an older root `.env` contains a localhost broker URL, change that value to the Redis service hostname before starting Compose.

Default SQLite remains `backend/file_processing.db`; files remain in `backend/data/`. Switching to PostgreSQL does not transfer SQLite history automatically or delete it. Back up database metadata and files together.

## Migrations

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
alembic current
```

Migration `0001` adopts existing job history and creates the analytics table/indexes. Migration `0002` adds durable dispatch/lease metadata. Older interrupted synchronous `pending`/`processing` jobs become failed with a clear explanation; completed history and AI reports are preserved. Older jobs without analytics remain downloadable and display an explicit historical-data notice. Destructive downgrade is disabled; restore a reviewed backup instead. The default single API process performs startup migrations; larger deployments should run migrations once before starting replicas.

## Configuration

| Variable | Default / purpose |
|---|---|
| `DATABASE_URL` | SQLite at `backend/file_processing.db`; supports `postgresql+psycopg://...` |
| `DATA_DIR` | `backend/data`, with input/output subdirectories |
| `MAX_UPLOAD_BYTES` | 10485760 (10 MiB), configurable file-content limit |
| `CORS_ORIGINS` | Comma-separated explicit browser origins |
| `VITE_API_BASE_URL` | Frontend API address, default `http://localhost:8000` |
| `OPENAI_API_KEY` | Empty; optional existing provider credential |
| `OPENAI_BASE_URL` | Existing repository default `https://models.inference.ai.azure.com` |
| `OPENAI_MODEL` | Existing repository default `gpt-5-mini` |
| `POSTGRES_PASSWORD` | Compose local database credential |
| `CELERY_BROKER_URL` | Local Python: `redis://localhost:6379/0`; Compose/root example: `redis://redis:6379/0`; environment override supported |
| `CELERY_QUEUE` | `csv-processing`; must match dispatcher and workers |
| `JOB_TIME_LIMIT_SECONDS` | 120 hard limit; soft limit is two seconds earlier |
| `JOB_LEASE_SECONDS` | 150; must exceed the hard limit by at least five seconds |
| `JOB_MAX_ATTEMPTS` | 3 execution attempts |
| `DISPATCH_INTERVAL_SECONDS` | 2 seconds between dispatch/recovery cycles |
| `JOB_REDISPATCH_SECONDS` | 30 seconds before republishing unclaimed work |
| `JOB_QUEUE_TIMEOUT_SECONDS` | 600 seconds without a worker claim before failure |
| `PUBLISH_MAX_FAILURES` | 8 consecutive failed publication attempts |

The API exposes output basenames, not internal attempt paths or Celery task IDs; downloads resolve files by application job ID. `.env` files are ignored; `.env.example` files contain no secrets. The Docker build excludes local credentials, databases, virtual environments and runtime data.
