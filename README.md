# MA Analytics — Automotive Intelligence Platform

AI-powered product intelligence from app store reviews and regulatory documents.  
Analyse what users of automotive apps really want — and generate data-backed product concepts from it.

---

## What This System Does

MA Analytics scrapes and analyses Google Play reviews from automotive manufacturer apps (BMW, Mercedes-Benz, Audi, Volkswagen, etc.), extracts structured signals from those reviews via an NLP pipeline, and makes those signals exploitable through an Innovation Lab that generates investor-ready product briefs.

**Data pipeline:** Scrape → Preprocess → Embed → Signal extraction → Cluster  
**Intelligence layer:** Hypothesis-guided retrieval → Signal graph → Claude-generated brief → PDF export  
**Document layer:** Upload PDF → Chunk → Embed → RAG Q&A + metric extraction

---

## Feature Overview

| Module | What it does |
|--------|-------------|
| **Data Sources** | Add apps by Google Play ID or upload CSV reviews |
| **Pipeline** | Background NLP job: sentiment, embeddings, signal extraction, clustering |
| **Dashboard** | KPIs, top signals, cluster summary, AI narrative |
| **Innovation Lab** | Generate product briefs from signal data — with hypothesis validation, signal graph, signal selector |
| **Hybrid Search** | Semantic + full-text search over 30k+ reviews with RRF fusion |
| **Document Intelligence** | Upload PDFs (CSDDD, CSRD), extract metrics, Q&A via RAG |
| **Inbox** | Customer message management with AI reply generation |
| **Kanban** | Ticket management (Backlog → Todo → In Progress → Done) |
| **Settings** | Profile, password, notification preferences |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI 0.115 + Python 3.9 |
| AI (primary) | Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) |
| AI (fallback) | Groq — `llama-3.3-70b-versatile`, `llama-3.1-70b-versatile`, `gemma2-9b-it` |
| ML Pipeline | Celery + Redis, `paraphrase-multilingual-MiniLM-L12-v2`, scikit-learn |
| Database | PostgreSQL 16 + pgvector 0.3 |
| ORM | SQLAlchemy 2.0 async (asyncpg) |
| Migrations | Alembic 1.13 |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| PDF export | jsPDF (client-side) |
| Email | Resend |

---

## Local Development

### Prerequisites

- Python 3.9+
- Node.js 20+
- Docker + Docker Compose

### 1. Infrastructure

```bash
docker compose -f docker-compose.local.yml up -d db redis
```

Starts PostgreSQL on port **5434** and Redis on port **6380**.

### 2. Backend

```bash
cd backend
python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in API keys (see below)
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Celery Worker (new terminal)

```bash
cd backend && source .venv/bin/activate
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES \
  celery -A app.pipeline.celery_app worker --loglevel=info -P solo
```

> `-P solo` is required on macOS. On Linux (production), remove this flag.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:3002
```

---

## Ports

| Service | Port |
|---------|------|
| Frontend (dev) | 3002 |
| Backend API | 8000 |
| PostgreSQL | 5434 |
| Redis | 6380 |

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in values:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | `postgresql://ma_analytics:ma_analytics@localhost:5434/ma_analytics` |
| `ASYNC_DATABASE_URL` | ⬜ | Auto-derived from DATABASE_URL if not set |
| `REDIS_URL` | ✅ | `redis://localhost:6380/0` |
| `SECRET_KEY` | ✅ | JWT signing key — min 32 chars, use `openssl rand -hex 32` |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key — primary AI provider for all generation |
| `ANTHROPIC_MODEL` | ⬜ | Default: `claude-haiku-4-5-20251001` |
| `GROQ_API_KEY` | ⬜ | Groq key — fallback when Claude is unavailable |
| `GROQ_API_KEY_2` | ⬜ | Second Groq key — rotated on rate limits |
| `GROQ_MODEL` | ⬜ | Default: `llama-3.3-70b-versatile` |
| `RESEND_API_KEY` | ⬜ | Enables password reset emails |
| `FRONTEND_URL` | ⬜ | Used in email links — default `http://localhost:3002` |
| `DEBUG` | ⬜ | `true` enables `/docs` OpenAPI UI and verbose logging |

---

## Project Structure

```
MA-Analytics/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py           # Registration, login, password reset
│   │   │   ├── dashboard.py      # KPIs, clusters, AI narrative
│   │   │   ├── datasources.py    # App CRUD, CSV upload, scrape trigger
│   │   │   ├── innovation.py     # Innovation Lab — full feature module
│   │   │   ├── intelligence.py   # Document upload, RAG Q&A, metric extraction
│   │   │   ├── jobs.py           # Pipeline job status polling
│   │   │   ├── messages.py       # Inbox — message management + AI reply
│   │   │   ├── search.py         # Hybrid search (vector + full-text + RRF)
│   │   │   └── tickets.py        # Kanban ticket CRUD
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic settings — all env vars
│   │   │   ├── database.py       # Async SQLAlchemy engine + session
│   │   │   ├── deps.py           # FastAPI dependency injection
│   │   │   ├── logging.py        # Structlog JSON logging
│   │   │   └── security.py       # JWT creation/verification, password hashing
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── pipeline/
│   │   │   ├── celery_app.py     # Celery config + broker
│   │   │   ├── tasks.py          # Main pipeline task (scrape → ML → store)
│   │   │   ├── ml.py             # Embedding model, sentiment, clustering
│   │   │   └── intelligence.py   # Document chunking, embedding, metric extraction
│   │   └── main.py               # FastAPI app factory, router registration, CORS
│   ├── alembic/versions/         # Database migration history
│   ├── tests/                    # Unit + integration tests
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx
│       │   ├── DataSourcesPage.tsx
│       │   ├── AppDetailPage.tsx
│       │   ├── InnovationLabPage.tsx   # Innovation Lab — main UI
│       │   ├── SearchPage.tsx
│       │   ├── InboxPage.tsx
│       │   ├── KanbanPage.tsx
│       │   └── SettingsPage.tsx
│       ├── components/
│       │   ├── AppShell.tsx            # Navigation sidebar + layout
│       │   └── ProtectedRoute.tsx
│       ├── contexts/
│       │   └── AuthContext.tsx         # JWT token management
│       ├── services/
│       │   └── api.ts                  # All API client functions
│       └── utils/
│           └── exportBriefPdf.ts       # Client-side PDF generation
├── docs/                               # Full technical documentation
└── docker-compose.local.yml
```

---

## Database Migrations

```bash
cd backend && source .venv/bin/activate

# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe the change"

# Roll back one step
alembic downgrade -1
```

---

## API Documentation

When `DEBUG=true`, OpenAPI is available at `http://localhost:8000/docs`.

Key endpoint groups:
- `POST /auth/*` — Authentication
- `GET/POST /datasources/*` — Data source management
- `POST /innovation/signals` — Available signals for current filter
- `POST /innovation/generate` — Generate Innovation Brief
- `GET /innovation/briefs` — Brief history
- `POST /innovation/briefs/{id}/generate-concept` — Long-form concept
- `POST /search/` — Hybrid semantic + full-text search
- `POST /intelligence/*` — Document upload + Q&A

---

## Running Tests

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v
```

Integration tests require a running database (`docker compose up -d db`).
