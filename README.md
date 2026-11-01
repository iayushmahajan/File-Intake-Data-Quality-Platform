# File Intake & Data Quality Platform

I built this full-stack app to validate transaction CSV files and make the results easier to review. It separates accepted and rejected records, explains validation errors, and lets you correct rejected values from the dashboard.

You can map different column names, save import templates, download cleaned data and revisit previous uploads. Files are processed in the background with Celery and Redis, while PostgreSQL stores job history and results. The core workflow runs locally without an AI key.

## The UI

The dashboard shows the job status, accepted and rejected counts, quality score and validation results. For corrected datasets, it also shows what changed from the original job.

![File Intake & Data Quality Platform dashboard showing a completed import, quality metrics and a comparison with the original job](docs/images/data-quality-platform-dashboard.png)

These screenshots show the running app using the included fictional sample data. In this example, correcting one invalid email increases accepted records from 1 to 2 and the quality score from 70 to 100.

### Column mapping and validation preview

Choose which source column belongs to each field, reuse a saved template and preview validation before processing the file.

![Import form with a saved template, source-column mappings and validation results for two sample records](docs/images/import-mapping-light.png)

### Record explorer and corrections

Search and filter records, inspect the errors on a rejected row and edit its values. Reprocessing creates a linked job and keeps the original results.

![Dataset explorer with a rejected record open for editing and its invalid email highlighted](docs/images/record-correction-light.png)

## What it does

A CSV can look ready to use while containing invalid dates, mismatched currencies, duplicates or missing values. The app checks these rules and shows which records passed, which need correction and which are valid but unusual.

### From upload to results

```mermaid
flowchart TD
    A[Upload a transaction CSV] --> M[Map columns or reuse a template]
    M --> B[Validate and normalize records]
    B --> C[Accepted records]
    B --> D[Rejected records with explanations]
    C --> E[Download cleaned CSV]
    D --> F[Download error report]
    D --> R[Correct rejected records]
    R --> V[Reprocess as a linked job]
    V --> H
    C --> G[Review quality, patterns and anomalies]
    D --> G
    G --> H[Reopen saved results from job history]
```

For example, an invalid email produces a rejected record with an explanation. An otherwise valid order above 1,000 remains accepted but is flagged for review. The dashboard treats validation errors and anomaly signals separately.

| Feature | What it does |
|---|---|
| Column mapping and templates | Confirm source headers, preview field validation, and save mappings and rules; each job keeps the version it used |
| Record exploration and correction | Search every indexed record, filter and export results, edit rejected values, and compare a reprocessed job with its original |
| Validation and normalization | Checks across 12 required fields, cross-field rules and duplicate records; consistent formatting in accepted output |
| Quality analysis | A calculated quality score, field statistics, error patterns and rule-based anomaly flags |
| Background processing | A job ID immediately after acceptance, visible processing states and automatically displayed results |
| Historical dashboard | Saved analytics, searchable validation errors, file previews and job history with search, filters and pagination |
| CSV exports | Original input, normalized accepted records and rejected records with error details |
| Optional AI interpretation | A saved, downloadable summary based on aggregate measurements, excluding raw customer records |

## How it works

```mermaid
flowchart TD
    UI["React dashboard<br/>Upload, track and review"] -->|Upload file| API["FastAPI<br/>Save input and create job"]
    API -->|Job and work to dispatch| DB[("PostgreSQL<br/>Job history and analytics")]
    API --> FILES["Shared file storage<br/>Input and output CSVs"]
    DB --> DISPATCH["Dispatcher<br/>Queue saved work and recover expired attempts"]
    DISPATCH --> REDIS["Redis<br/>Task queue"]
    REDIS --> WORKER["Celery worker<br/>Validate, normalize and analyze"]
    WORKER -->|Write reports| FILES
    WORKER -->|Save results| DB
    UI -->|Check status and retrieve results| API
    API -->|Read saved results| DB
```

FastAPI saves the file and commits the job with its dispatch intent in one database transaction, then returns **HTTP 202**. A separate dispatcher sends the job to Redis, and Celery performs the CSV processing using worker-owned database sessions. PostgreSQL is the primary Compose database; SQLite supports local Python development.

The dashboard follows `pending → queued → processing → completed / failed`, polling while a job is active and loading its analytics when finished. The selected job stays in the URL so a page refresh reopens the same workspace.

### Background job handling

| Decision | Why it matters |
|---|---|
| Persist work before publishing to Redis | Accepted jobs remain recorded across API restarts and can be dispatched after a temporary broker outage |
| Claim each execution attempt atomically | Duplicate task deliveries cannot acquire a job already held by an active worker |
| Use attempt-specific files and guarded result commits | An expired worker cannot overwrite the outputs or published results of a newer attempt |
| Bound retries and persist failures | Invalid files and exhausted retries leave an inspectable outcome in job history |
| Validate AI output before saving it | Reports follow a defined schema and remain separate from deterministic quality calculations |

A task can be delivered more than once. The worker checks ownership of the job before saving results. Recovery depends on the database, dispatcher, broker, worker and shared storage being available. See the [background processing design](docs/ASYNC_PROCESSING.md) for execution leases, retry policies and failure handling.

## Tech stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, Papa Parse |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Background jobs | Celery, Redis |
| Database | PostgreSQL, SQLite, SQLModel, SQLAlchemy, Alembic |
| AI integration | OpenAI Python SDK with an OpenAI-compatible provider |
| Testing | pytest, Vitest, React Testing Library, Playwright |
| Infrastructure | Docker Compose, GitHub Actions |

## Run locally

With Docker running and Node.js/pnpm installed, start the entire local project from a Linux/WSL terminal:

```bash
./run.sh
```

Open **http://localhost:5175**. The script rebuilds and recreates containers to refresh shared storage, reuses the existing Docker project/data volumes, and starts the frontend. It installs frontend dependencies if absent. Stop any existing frontend on port 5175 first. `Ctrl+C` stops the frontend; backend services keep running.

In VS Code, open this project folder (in WSL if applicable) and press **Ctrl+Shift+B**, or choose **Terminal → Run Task → Run full project**. Use **Terminal → Run Task → Stop backend services** to stop Docker services without deleting saved data.

For individual setup and service commands:

Requires Docker with Compose, Node.js 22+ and pnpm 10.32.1. On Windows, enable Docker Desktop integration for your WSL distro.

```bash
# From the repository root
cp -n .env.example .env
docker compose -p file-intake-processing-service up --build -d --wait

cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

| Service | Address |
|---|---|
| Dashboard | http://localhost:5173 |
| API | http://127.0.0.1:8000 |
| API documentation | http://127.0.0.1:8000/docs |

Compose starts PostgreSQL, Redis, the API, a Celery worker and the dispatcher. Migrations run at API startup. Database and broker data use persistent volumes; input and output files are stored in `backend/data`.

The root `.env.example` uses `redis://redis:6379/0` for the Compose broker. If an existing root `.env` uses `localhost`, update that value before starting the stack. The backend environment example uses localhost for Python processes running outside Docker.

```bash
# Run from the repository root
docker compose -p file-intake-processing-service logs -f api worker dispatcher
docker compose -p file-intake-processing-service down
```

Use the same `-p file-intake-processing-service` project name for all commands above and the launcher so they address the same containers and persistent volumes. `docker compose down` without `--volumes` preserves the database and Redis volumes. The default setup binds the API and Redis to localhost and is intended for a single operator.

For SQLite development, migrations and all environment variables, see the [development reference](docs/DEVELOPMENT.md).

## Try a dataset

Sample files are in `backend/samples/`:

| File | Purpose |
|---|---|
| `normal_demo.csv` | Mostly valid transaction records |
| `heavier_error_demo.csv` | Validation errors and rejected records |
| `anomaly_demo.csv` | Accepted records with anomaly signals |
| [`mixed_100_records.csv`](backend/samples/mixed_100_records.csv) | 100 records: 70 valid and 30 invalid |
| [`mixed_500_records.csv`](backend/samples/mixed_500_records.csv) | 500 records: 350 valid and 150 invalid |
| [`mixed_1000_records.csv`](backend/samples/mixed_1000_records.csv) | 1,000 records: 700 valid and 300 invalid |
| [`mixed_10000_records.csv`](backend/samples/mixed_10000_records.csv) | 10,000 records: 7,000 valid and 3,000 invalid |
| [`mixed_1000_varied_issues.csv`](backend/samples/mixed_1000_varied_issues.csv) | 1,000 records with uneven, scattered issues across all quality dimensions: 663 accepted, 337 rejected |

The mixed datasets contain invalid emails, negative amounts, zero quantities, impossible dates, discounts above 100% and country/currency mismatches. Expected counts use the default validation rules. Record counts exclude the header. For the broader quality sample, see the [varied-issues breakdown](backend/samples/VARIED_ISSUES.md).

Choose a sample, confirm the column mapping, select **Preview validation**, then **Upload and Analyze CSV**. Explore Overview, Validation, Data profile, Anomalies and the dataset explorer, then download the clean or error CSV. Reopen the job from history to see its saved results. Samples use fictional identifiers and example.com email addresses.

## Correct records and reuse imports

The dataset explorer searches and filters the complete indexed result, with pagination, selectable columns and filtered CSV exports. Rejected fields include error explanations and can be edited in a record detail panel. Validate the corrections, then reprocess the dataset as a new linked job. The comparison shows changes in accepted/rejected counts and quality score, while the original files and results remain intact.

Import templates save column mappings and optional allowed values, numeric bounds and date formats. Each job keeps the configuration used for that run, so later template updates do not change historical results.

Try [`09_partner_headers.csv`](backend/samples/manual/09_partner_headers.csv) for the mapping and correction workflow. See the [import workspace guide](docs/IMPORT_WORKSPACE.md) for API details and the [manual test guide](backend/samples/manual/README.md) for expected outcomes.

## Validation and scoring

The input schema requires 12 columns covering customer ID, email, country, signup date, order amount, currency, payment method, order status, product category, quantity, discount and last login date. Validation checks field formats, supported values, date consistency, country/currency rules and duplicate records.

Accepted records are normalized; rejected records retain their supplied values and include error explanations. A completed job can contain rejected records. Invalid file structure produces a failed job.

The backend calculates and stores the quality score:

| Dimension | What it measures | Weight |
|---|---|---:|
| Validity | Records that pass validation | 60% |
| Completeness | Required cells containing a value | 20% |
| Uniqueness | Records remaining after duplicate detection | 10% |
| Anomaly health | Accepted records without anomaly signals | 10% |

The same data produces the same score; AI does not calculate or change it. Anomaly signals use explicit thresholds for order amount, quantity and discount. Amounts remain in their original currencies; aggregate statistics do not perform currency conversion.

See [CSV rules and score calculations](docs/DEVELOPMENT.md) for exact headers, thresholds and handling of empty datasets.

## Optional AI interpretation

For a completed job, you can optionally request an AI summary. The provider receives counts, error-category totals, quality dimensions and numeric profiles. Raw rows, email addresses, customer IDs and filenames are excluded.

Responses must pass a strict Pydantic schema before being saved. Reports can be reopened and exported as Markdown. Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` to use a provider; validation and analytics work without them.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Process health |
| POST | `/api/v1/uploads` | Accept a CSV and return its job ID |
| GET | `/api/v1/jobs` | Paginated history with search and status filters |
| GET | `/api/v1/jobs/{id}` | Job status, analytics, correction lineage and saved AI report |
| GET | `/api/v1/jobs/{id}/records` | Search, filter, sort and page through indexed records |
| GET | `/api/v1/jobs/{id}/records/export` | Download all records matching the current filters |
| POST | `/api/v1/jobs/{id}/corrections` | Reprocess validated corrections as a linked job |
| POST | `/api/v1/imports/preview` | Inspect headers and preview mapped field validation |
| GET / POST | `/api/v1/imports/templates` | List or save reusable import templates |
| GET | `/api/v1/jobs/{id}/download/{kind}` | Download `input`, `clean` or `errors` CSV |
| POST | `/api/v1/jobs/{id}/ai-analysis` | Generate or retrieve an AI report |

Interactive request and response schemas are available at `/docs`. Uploads are limited to 10 MiB by default through `MAX_UPLOAD_BYTES`.

## Tests

Backend tests require a Python virtual environment with `backend/requirements.txt` installed. Browser tests also require Docker, Playwright Chromium and free ports 8011 and 5174.

```bash
# From the repository root
backend/.venv/bin/python -m pytest backend/tests -q
pnpm --dir frontend test
pnpm --dir frontend build

cd frontend
pnpm exec playwright install chromium
pnpm test:e2e
cd ..

# Disposable PostgreSQL, Redis and Celery integration checks
backend/.venv/bin/python scripts/verify_async_stack.py
```

Tests cover validation, persistence, migrations, retries, duplicate delivery, polling and browser workflows. Edge cases include malformed CSVs, upload-size boundaries, correction limits, stale or mismatched templates, empty exports and errors beyond the preview sample. Frontend checks cover failed uploads, unavailable templates, duplicate mappings, read-only records and correction retries that preserve edits.

Test databases and files are isolated from development data. AI calls are mocked or disabled.

GitHub Actions is configured for backend and frontend tests, the production build and the disposable async integration checks. Detailed execution records are kept in the [verification log](docs/UPGRADE_CHECKPOINT.md).

---

Built by Ayush Satish Mahajan.
