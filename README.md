# WealthPilot — Backend

FastAPI backend for the WealthPilot financial advisor platform. Ingests Excel files and audio recordings to create and manage household financial data, powered by GPT-4o and Whisper.

## Tech Stack

- **Python 3.12+** with **FastAPI**
- **uv** — package manager and virtualenv
- **SQLAlchemy (AsyncIO)** + **asyncpg** — async ORM
- **Supabase** (PostgreSQL) — managed database
- **Alembic** — database migrations
- **Pydantic AI** — structured LLM extraction agents
- **OpenAI** — GPT-4o for column mapping + audio extraction, Whisper for transcription

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- A [Supabase](https://supabase.com) project (free tier works)
- An [OpenAI](https://platform.openai.com) API key

## Project Structure

```
backend/
├── app/
│   ├── agents/          # Pydantic AI agents (column mapping, audio extraction)
│   ├── api/routes/      # FastAPI route handlers
│   ├── core/            # Config, database setup, job store
│   ├── models/          # SQLAlchemy ORM models
│   ├── repositories/    # All database queries
│   ├── schemas/         # Pydantic request/response schemas
│   └── services/        # Business logic
├── alembic/             # Database migrations
├── alembic.ini
├── pyproject.toml
├── run.py               # Local dev entrypoint
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
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Getting your Supabase `DATABASE_URL`:**
1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) → your project
2. **Project Settings** → **Database**
3. Copy the **Connection string** (URI format)
4. Replace `postgresql://` with `postgresql+asyncpg://`

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

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/households` | List all households |
| `POST` | `/api/households/upload-excel` | Upload and process Excel file |
| `POST` | `/api/households/{id}/upload-audio` | Upload and process audio recording |
| `GET` | `/api/households/{id}` | Get household detail |
| `GET` | `/api/households/insights` | Aggregated financial insights |
| `GET` | `/api/households/{id}/conflicts` | List pending data conflicts |
| `POST` | `/api/conflicts/{id}/resolve` | Accept or reject a conflict |
| `GET` | `/api/jobs/{job_id}` | Poll background job status |

Full interactive documentation available at `/docs` when running locally.

## Key Features

### Excel Ingestion
- Upload `.xlsx` / `.xls` files with any column layout
- AI agent (GPT-4o) maps columns to canonical fields automatically
- Second AI reviewer agent audits and corrects the initial mapping
- Processes all sheets in a workbook, not just the first
- Matches existing households by name and enriches instead of duplicating

### Audio Ingestion
- Transcribes audio via OpenAI Whisper
- GPT-4o extracts structured financial data from the transcript
- Passes existing household values as context (handles relative updates like "bump income 10%")
- Per-field `quotes` — stores the verbatim transcript phrase behind each extracted value
- Detected changes that differ from existing data are flagged as conflicts for advisor review

### Conflict Resolution
- Contradictions between incoming and existing data are stored as `DataConflict` records
- Advisor reviews each conflict and accepts or rejects the incoming value
- Each audio conflict shows the source quote from the transcript

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (must use `postgresql+asyncpg://` driver prefix) |
| `OPENAI_API_KEY` | OpenAI API key — used for GPT-4o and Whisper |

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
