# WealthPilot — Backend

FastAPI backend for the WealthPilot financial advisor platform. Ingests Excel files and audio recordings to create and manage household financial data, powered by GPT-4o and Whisper, with full CRUD management of households, members, financial accounts, and bank details.

## Tech Stack

- **Python 3.12+** with **FastAPI**
- **uv** — package manager and virtualenv
- **SQLAlchemy 2.0 (AsyncIO)** + **asyncpg** — async ORM
- **Supabase** (PostgreSQL) — managed database, accessed via the transaction-mode pooler
- **Alembic** — database migrations
- **Pydantic AI** — structured LLM extraction agents
- **OpenAI** — GPT-4o for column mapping + audio extraction, Whisper for transcription
- **Logfire** — observability / tracing (optional)

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- A [Supabase](https://supabase.com) project (free tier works)
- An [OpenAI](https://platform.openai.com) API key
- A [Logfire](https://logfire.pydantic.dev) token (optional — only if you want traces)

## Project Structure

```
backend/
├── app/
│   ├── agents/              # Pydantic AI agents (column mapping, audio extraction)
│   ├── api/
│   │   ├── deps.py          # Shared FastAPI dependencies
│   │   └── routes/          # FastAPI route handlers
│   │       ├── households.py
│   │       ├── members.py
│   │       ├── accounts.py
│   │       ├── bank_details.py
│   │       ├── conflicts.py
│   │       ├── jobs.py
│   │       └── admin.py
│   ├── core/                # Config, database setup, in-memory job store
│   ├── models/              # SQLAlchemy ORM models
│   ├── repositories/        # All database queries
│   ├── schemas/             # Pydantic request/response schemas
│   └── services/            # Business logic
│       ├── household_service.py
│       ├── member_service.py
│       ├── excel_service.py
│       ├── audio_service.py
│       ├── conflict_service.py
│       ├── insight_service.py
│       └── admin_service.py
├── alembic/                 # Database migrations
├── alembic.ini
├── Dockerfile
├── pyproject.toml
├── run.py                   # Local dev entrypoint
└── .env.example
```

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/jay-arora31/wealthpilot-backend.git
cd wealthpilot-backend
```

### 2. Install dependencies

```bash
uv sync
```

This creates a `.venv` and installs all dependencies from `uv.lock`.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
# Supabase transaction-mode pooler (runtime)
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional — leave blank to skip Logfire traces
LOGFIRE_API_KEY=
LOGFIRE_INSTRUMENT_SQL=false

# CORS — comma-separated. Add your frontend origin(s) here.
ALLOWED_ORIGINS=http://localhost:5173
```

**Getting your Supabase `DATABASE_URL`:**
1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) → your project
2. **Project Settings** → **Database** → **Connection pooling** → **Transaction** mode
3. Copy the URI and replace the `postgresql://` prefix with `postgresql+asyncpg://`
4. Note: the username is `postgres.<PROJECT_REF>`, not plain `postgres`

> The transaction pooler is required at runtime (FastAPI uses many short connections). For Alembic migrations, prefer the **direct** connection string on port 5432 so advisory locks and prepared statements work correctly.

### 4. Run database migrations

```bash
uv run alembic upgrade head
```

This creates all tables in your Supabase database.

### 5. Start the development server

```bash
uv run run.py
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Overview

### Households
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/households` | List all households |
| `POST` | `/api/households` | Create a household |
| `GET` | `/api/households/{id}` | Get household detail |
| `PUT` | `/api/households/{id}` | Update household fields |
| `DELETE` | `/api/households/{id}` | Delete household (cascades) |
| `GET` | `/api/households/insights` | Aggregated financial insights |
| `POST` | `/api/households/upload-excel` | Upload and process an Excel file |
| `POST` | `/api/households/{id}/upload-audio` | Upload and process an audio recording (optional `?force=true`) |

### Members
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/households/{id}/members` | List members in a household |
| `POST` | `/api/households/{id}/members` | Add a member |
| `PUT` | `/api/members/{id}` | Update a member |
| `DELETE` | `/api/members/{id}` | Remove a member |

### Financial Accounts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/households/{id}/accounts` | List accounts for a household |
| `POST` | `/api/households/{id}/accounts` | Create an account (with ownerships) |
| `PUT` | `/api/accounts/{id}` | Update an account |
| `DELETE` | `/api/accounts/{id}` | Delete an account |

### Bank Details
| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/api/bank-details/{id}` | Update a bank detail record |
| `DELETE` | `/api/bank-details/{id}` | Delete a bank detail record |

### Conflicts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/households/{id}/conflicts` | List pending data conflicts |
| `POST` | `/api/conflicts/{id}/resolve` | Accept or reject a conflict |

### Jobs & Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/jobs/{job_id}` | Poll background job status (Excel / audio) |
| `DELETE` | `/api/admin/reset` | **Danger:** wipe every household and all related data |

Full interactive documentation is available at `/docs` when running locally.

## Key Features

### Excel Ingestion
- Upload `.xlsx` / `.xls` files with any column layout
- AI agent (GPT-4o) maps columns to canonical fields automatically
- Second AI reviewer agent audits and corrects the initial mapping
- Processes all sheets in a workbook, not just the first
- Matches existing households by name and enriches instead of duplicating

### Audio Ingestion
- Transcribes audio via OpenAI Whisper (`.mp3`, `.wav`, `.m4a`, `.webm`, `.mp4`, `.ogg`)
- GPT-4o extracts structured financial data from the transcript
- Passes existing household values as context (handles relative updates like "bump income 10%")
- Per-field `quotes` — stores the verbatim transcript phrase behind each extracted value
- Detected changes that differ from existing data are flagged as conflicts for advisor review
- `force=true` query param bypasses conflict gating and applies incoming values directly

### Conflict Resolution
- Contradictions between incoming and existing data are stored as `DataConflict` records
- Advisor reviews each conflict and accepts or rejects the incoming value
- Each audio conflict shows the source quote from the transcript

### Background Jobs
- Excel and audio ingestion run in FastAPI background tasks so uploads return immediately
- Job progress is tracked in an in-memory `job_store`; the frontend polls `/api/jobs/{id}` until the job completes
- Every job owns its own DB session so background work never shares state with the request that queued it

### Admin
- `DELETE /api/admin/reset` nukes every household (cascades through members, accounts, bank details, and conflicts). Wired up to the frontend's Settings → Danger Zone.

## Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `DATABASE_URL` | ✅ | Supabase PostgreSQL connection string — must use the `postgresql+asyncpg://` driver prefix and the transaction pooler host. |
| `OPENAI_API_KEY` | ✅ | OpenAI API key — used for GPT-4o (column mapping + audio extraction) and Whisper (transcription). |
| `LOGFIRE_API_KEY` | ❌ | Logfire write token. Leave blank to disable Logfire export. |
| `LOGFIRE_INSTRUMENT_SQL` | ❌ | `true` to trace every SQL statement (very noisy during ingests). Defaults to `false`. |
| `ALLOWED_ORIGINS` | ❌ | Comma-separated CORS origins. Defaults to `http://localhost:5173`. |

## Running Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Check current migration state
uv run alembic current

# Rollback one migration
uv run alembic downgrade -1

# Auto-generate a new migration after model changes
uv run alembic revision --autogenerate -m "description"
```

## Docker (Local Testing)

```bash
# Build the image
docker build -t wealthpilot-backend:local .

# Run with your .env file
docker run -p 8080:8080 --env-file .env wealthpilot-backend:local
```

API will be available at http://localhost:8080/docs

## Observability

When `LOGFIRE_API_KEY` is set, the backend:
- Instruments FastAPI (every request becomes a span, with headers captured)
- Wraps the OpenAI client, `httpx`, and `pydantic-ai` — so every LLM call shows up in the trace
- Emits structured events from routes and services (`route.upload_excel_accepted`, `account.created`, etc.)

Set `LOGFIRE_INSTRUMENT_SQL=true` only while debugging — it emits a span per SQL statement and will flood the console during Excel/audio ingests.
