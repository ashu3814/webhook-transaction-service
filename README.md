# Webhook Transaction Service

## Project overview

Webhook Transaction Service accepts transaction notifications from payment
processors, stores each transaction in PostgreSQL, and hands new transactions
to a Celery worker through RabbitMQ. Each unique `transaction_id` is processed
once. Duplicate webhook deliveries are acknowledged without inserting another
row or queueing another task.

The worker intentionally waits 30 seconds before marking a transaction
`PROCESSED`. Transaction timestamps are timezone-aware and are returned by the
API in Indian Standard Time (IST, UTC+05:30).

## Contents

- [Architecture and workflows](#architecture-and-workflows)
- [Technology choices](#technology-choices)
- [Configuration](#configuration)
- [API documentation](#api-documentation)
- [IST timestamps](#ist-timestamps)
- [Local setup](#local-setup)
- [Database schema and migration](#database-schema-and-migration)
- [Testing guide](#testing-guide)
- [Performance notes](#performance-notes)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Further documentation](#further-documentation)

## Architecture and workflows

### Request and processing flow

```text
Payment processor
        |
        | POST /v1/webhooks/transactions
        v
FastAPI webhook endpoint
        |
        +-- transaction_id exists? -- yes --> log duplicate; return HTTP 202
        |                                  (do not insert or enqueue)
        |
        +-- no --> insert PROCESSING row and commit
                    |
                    v
              publish Celery task to RabbitMQ
                    |
                    v
              Celery worker receives task
                    |
                    +-- wait 30 seconds
                    |
                    +-- one SQL UPDATE sets PROCESSED and processed_at
                    |
                    v
              PostgreSQL
```

The database primary key on `transaction_id` is the final uniqueness
guarantee. If simultaneous requests both pass the initial existence check, the
request that loses the insert race is recognized as a duplicate and does not
enqueue work.

### Idempotency flow

1. The endpoint checks whether `transaction_id` already exists.
2. If present, it logs `Duplicate webhook skipped` and returns the regular
   `202 Accepted` response without enqueuing a task.
3. If absent, it commits a new `PROCESSING` row.
4. If a concurrent request inserted the same key first, the unique-key
   violation is checked after rollback; an existing key is treated as a
   duplicate.
5. Only the request that creates the row publishes a task.

### Timestamp flow

1. The model's `created_at` default calls `now_ist()`.
2. When the worker marks the row processed, `processed_at` is set using
   `now_ist()`.
3. PostgreSQL `TIMESTAMPTZ` stores the timestamp as an instant; API responses
   serialize it in IST with a `+05:30` offset.
4. The health endpoint also uses `now_ist()`.

### Celery worker flow

The worker receives `process_transaction`, waits once for 30 seconds, opens a
database session, updates the transaction, commits, then closes the session.
Celery uses concurrency 4 and `worker_prefetch_multiplier=1` so work is not
reserved too far ahead of available worker slots.

## Technology choices

| Technology | Role | Why it is used |
| --- | --- | --- |
| FastAPI | HTTP API | Provides request validation, dependency injection, and generated OpenAPI documentation. |
| PostgreSQL | Persistent database | Stores transactions durably and enforces unique transaction IDs with a primary key. |
| SQLAlchemy | Database access | Maps transaction records to Python models and executes parameterized database operations. |
| CloudAMQP | Message broker | Separates request handling from background processing and buffers queued work. |
| Celery | Task queue and worker | Runs processing outside the HTTP request, supports worker concurrency, and integrates with RabbitMQ. |
| Pydantic | Request/response schemas | Validates incoming transaction fields and shapes API responses. |

## Configuration

Create a local `.env` file from `.env.example`. `app/config.py` reads these
settings from the environment or `.env`:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection URL for the application PostgreSQL database. |
| `RABBITMQ_URL` | (Deprecated) Use `CELERY_BROKER_URL` instead. |
| `CELERY_BROKER_URL` | RabbitMQ broker URL used by Celery to publish and receive tasks. |
| `CELERY_RESULT_BACKEND` | Celery result-backend URL. Task results are currently ignored (`task_ignore_result=True`), so result records are not needed by the API. |
| `API_HOST` | Host address used when starting the app with `python app/main.py`; defaults to `0.0.0.0`. |
| `API_PORT` | Port used by `python app/main.py`; defaults to `8000`. |
| `API_ENV` | Environment label used in startup logging; defaults to `development`. |

Example values for the local Docker Compose services:

```dotenv
DATABASE_URL=postgresql://postgres:password@localhost:5432/webhook_db
RABBITMQ_URL=amqp://guest:guest@localhost:5672//
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=db+postgresql://postgres:password@localhost:5432/webhook_db
API_HOST=0.0.0.0
API_PORT=8000
API_ENV=development
```

Use the correct hostname for the environment. For example, a process running
inside a container normally connects to another Compose service by its service
name (such as `postgres` or `rabbitmq`), not by `localhost`. Never commit
production credentials to the repository.

## API documentation

Interactive OpenAPI documentation is available at `/docs` when the API is
running.

### `POST /v1/webhooks/transactions`

Request:

```json
{
  "transaction_id": "txn_abc123def456",
  "source_account": "acc_user_789",
  "destination_account": "acc_merchant_456",
  "amount": 1500,
  "currency": "INR"
}
```

Both new and duplicate requests return HTTP `202 Accepted`:

```json
{
  "status": "received"
}
```

For a new ID, the service stores a `PROCESSING` row and queues one task. For an
existing ID, it logs and skips the duplicate without creating a row or task.

### `GET /v1/transactions/{transaction_id}`

Returns a one-element JSON array for a found transaction. Example after
processing:

```json
[
  {
    "transaction_id": "txn_abc123def456",
    "source_account": "acc_user_789",
    "destination_account": "acc_merchant_456",
    "amount": 1500,
    "currency": "INR",
    "status": "PROCESSED",
    "created_at": "2026-10-17T09:30:00+05:30",
    "processed_at": "2026-10-17T09:30:30+05:30"
  }
]
```

Before processing, the status is `PROCESSING` and `processed_at` is `null`.
An unknown ID returns HTTP `404 Not Found`.

### `GET /`

Returns the health status and current IST timestamp:

```json
{
  "status": "HEALTHY",
  "current_time": "2026-10-17T09:30:00+05:30"
}
```

## IST timestamps

The shared functions live in `app/utils/time.py`:

- `now_ist()` returns the current timezone-aware datetime at UTC+05:30.
- `to_ist(value)` converts an aware datetime to IST. For compatibility, a
  naive datetime is interpreted as UTC before conversion.

The transaction model uses `DateTime(timezone=True)`. The transaction response
schema converts `created_at` and `processed_at` to IST during serialization.
The health endpoint also returns an ISO 8601 timestamp with `+05:30`. Celery
uses the `Asia/Kolkata` timezone.

PostgreSQL `TIMESTAMPTZ` represents instants and may display them in the
database session's timezone; API output is explicitly normalized to IST.

## Local setup

### Prerequisites

- Git
- Python 3.11 or newer
- Docker with the Docker Compose plugin

### 1. Clone the repository

Replace the placeholder with the repository's clone URL:

```powershell
git clone <repository-url>
Set-Location webhook-service
```

### 2. Create and edit `.env`

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least `DATABASE_URL` and `CELERY_BROKER_URL` to match
the local services. Example local values are in
[Configuration](#configuration).

### 3. Install Python dependencies

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 4. Start PostgreSQL and RabbitMQ

```powershell
docker compose up -d
docker compose ps
```

The Compose file starts PostgreSQL on port `5432` and RabbitMQ on port `5672`.
Its RabbitMQ management interface is exposed on port `15672`.

### 5. Prepare the database schema

There is no Alembic migration runner in this project. On API startup,
`Base.metadata.create_all()` creates missing tables in a new database; it does
not alter existing tables. For a new local database, no separate migration
command is needed. For an existing database with timezone-naive timestamp
columns, apply the SQL in [Database schema and migration](#database-schema-and-migration)
before starting the updated application.

### 6. Start the Celery worker

In a new PowerShell terminal from the project directory:

```powershell
.\venv\Scripts\Activate.ps1
python celery_worker.py
```

Leave this terminal running. The worker imports the task and connects to the
RabbitMQ URL in `CELERY_BROKER_URL`.

### 7. Start the FastAPI server

In another terminal from the project directory:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The service is available at `http://localhost:8000` and the API docs at
`http://localhost:8000/docs`.

## Database schema and migration

For new databases, the model declares `created_at` and `processed_at` as
timezone-aware SQLAlchemy `DateTime` columns. The application creates missing
tables at startup.

`Base.metadata.create_all()` does not alter columns in an existing table. If
the existing PostgreSQL columns are `TIMESTAMP WITHOUT TIME ZONE` and their
values represent UTC, back up the database and run this SQL once before
deploying:

```sql
ALTER TABLE transactions
  ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING created_at AT TIME ZONE 'UTC',
  ALTER COLUMN processed_at TYPE TIMESTAMPTZ
    USING processed_at AT TIME ZONE 'UTC';
```

If the naive values represent a timezone other than UTC, replace `'UTC'` with
their actual source timezone. Do not run this conversion repeatedly: after
conversion, the columns are `TIMESTAMPTZ`.

## Testing guide

The repository does not currently include automated test cases. The following
manual scenarios exercise the implemented behavior. Run them with PostgreSQL,
RabbitMQ, the worker, and API running.

### Scenario 1: Submit and process one transaction

In PowerShell:

```powershell
$body = @{
  transaction_id = "txn_test_001"
  source_account = "acc_user_123"
  destination_account = "acc_merchant_456"
  amount = 1000
  currency = "INR"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/webhooks/transactions `
  -ContentType "application/json" -Body $body
```

Expect HTTP `202` and `status` equal to `received`. Query the transaction:

```powershell
Invoke-RestMethod -Method Get `
  -Uri http://localhost:8000/v1/transactions/txn_test_001
```

The status should first be `PROCESSING` and become `PROCESSED` after the
background task finishes.

### Scenario 2: Send a duplicate webhook

In the same PowerShell session, send the same payload again:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/webhooks/transactions `
  -ContentType "application/json" -Body $body
```

It should return HTTP `202` and `status` equal to `received`. The API log should
include `Duplicate webhook skipped`. The database should still contain one row
for `txn_test_001`, and the duplicate request should not enqueue another task.

### Scenario 3: Verify IST timestamps

Request the health endpoint and the transaction:

```powershell
Invoke-RestMethod -Method Get -Uri http://localhost:8000/
Invoke-RestMethod -Method Get `
  -Uri http://localhost:8000/v1/transactions/txn_test_001
```

Check that `current_time`, `created_at`, and non-null `processed_at` values end
in `+05:30`. `processed_at` is `null` before the worker completes.

## Performance notes

The task has one intentional 30-second sleep, followed by one database `UPDATE`
that sets the status and `processed_at`. Task execution is therefore expected
to take approximately 30 seconds plus the database operation.

This is not a hard end-to-end 30-second SLA. Total time also includes broker
queue wait, worker availability, and database/network latency. Celery is
configured with concurrency 4 and `worker_prefetch_multiplier=1` to reduce
delays when tasks are queued. Its `task_time_limit` of 30 minutes is a maximum
runtime limit, not an extra wait. Keep a worker running and check its logs if a
transaction takes longer than expected.

## Deployment

Deploy the API and Celery worker as separate services/processes that use the
same PostgreSQL database and RabbitMQ broker.

For example, on a hosting provider that supports web and background workers:

1. Provision PostgreSQL and RabbitMQ. Obtain their connection URLs.
2. Create a web service from the repository. Install dependencies with
   `pip install -r requirements.txt` and use this start command:

   ```text
   python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

3. Create a background worker from the same repository and use:

   ```text
   python celery_worker.py
   ```

4. Set `DATABASE_URL` and `CELERY_BROKER_URL` in both services. Set
   `API_ENV=production` on the web service. Set any other required values from
   [Configuration](#configuration) for your hosting environment.
5. Run the database conversion above first if deploying against an existing
   database with naive UTC timestamp columns.
6. Deploy both services, then check `GET /`, submit a test webhook, and verify
   the worker logs and transaction status.

### Railway deployment

1. Sign up at [Railway](https://railway.app).
2. Connect your GitHub account.
3. Create a new project from this repository.
4. Add two services:
   - **Web Service** (FastAPI): Start command:
     `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Background Worker** (Celery): Start command: `python celery_worker.py`
5. Set these environment variables in the Railway dashboard:
   `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `API_ENV`,
   `API_HOST`, and `API_PORT`.
6. Deploy and test the health endpoint:
   `curl https://your-railway-url.up.railway.app/`

The repository's Docker Compose file is for local PostgreSQL and RabbitMQ; it
does not start the API or the Celery worker. The Dockerfile starts the API
container only.

## Troubleshooting

### Transaction remains `PROCESSING`

- Check that `python celery_worker.py` is running.
- Confirm the worker and API use the same `CELERY_BROKER_URL`.
- Check worker logs for task exceptions.
- Confirm `DATABASE_URL` points to the same database used by the API.
- Account for the 30-second task delay, any queued work, and service latency.

### API or worker cannot connect to PostgreSQL

- Check the `DATABASE_URL` hostname, port, database, username, and password.
- Confirm PostgreSQL is ready with `docker compose ps`.
- From a container, use the Compose service hostname rather than `localhost`.

### Webhook is acknowledged but transaction is not found

- Confirm the API is connected to the expected database.
- Query using the exact `transaction_id` submitted.
- Review API logs for database errors.

### RabbitMQ connection or queue problem

- Check `CELERY_BROKER_URL` in both the API and worker environment.
- Confirm RabbitMQ is ready with `docker compose ps`.
- Ensure broker credentials and network access are valid.

### Duplicate webhook returns `202`

This is expected. Duplicate IDs receive the same acknowledgement as new
webhooks; check the API log for `Duplicate webhook skipped`. No second row or
task is created.

## Project structure

```text
webhook-service/
├── app/
│   ├── enums/
│   ├── models/
│   ├── repositories/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── tasks/
│   ├── utils/
│   │   └── time.py
│   ├── config.py
│   ├── database.py
│   └── main.py
├── tests/
├── celery_worker.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Further documentation

- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Celery documentation](https://docs.celeryq.dev/en/stable/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [RabbitMQ documentation](https://www.rabbitmq.com/docs)
- [Pydantic documentation](https://docs.pydantic.dev/)
