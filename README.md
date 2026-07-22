# MA Analytics — Voice of Customer AI Platform

AI-powered product intelligence from Google Play reviews and customer feedback.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.9 |
| ML Pipeline | Celery + Redis, sentence-transformers, scikit-learn |
| Database | PostgreSQL 16 |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| AI | Groq (llama3-8b-8192) — optional |

## Features

- **Google Play Scraper** — scrape app reviews by App ID
- **CSV Upload** — import review exports from any source
- **ML Pipeline** — sentiment analysis, embeddings, KMeans clustering (background job via Celery)
- **Dashboard** — KPIs, top issues, top strengths, AI insight
- **Inbox** — customer message management with AI reply generation
- **Kanban Board** — ticket management (Backlog → Todo → In Progress → Done)

## Local Development

### Prerequisites

- Python 3.9+
- Node.js 20+
- Docker + Docker Compose

### 1. Start infrastructure

```bash
docker compose -f docker-compose.local.yml up -d db redis
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit values as needed
alembic upgrade head
uvicorn app.main:app --port 8001 --reload
```

### 3. Celery Worker (new terminal)

```bash
cd backend && source .venv/bin/activate
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES \
  celery -A app.pipeline.celery_app worker --loglevel=info -P solo
```

> `-P solo` required on macOS. On Linux (production), remove this flag.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev   # runs on http://localhost:3002
```

### Ports

| Service | Port |
|---------|------|
| Frontend (dev) | 3002 |
| Backend API | 8001 |
| PostgreSQL | 5434 |
| Redis | 6380 |

## Production (Docker)

```bash
# Generate a secure secret key
openssl rand -hex 32

# Edit backend/.env with production values
cp backend/.env.example backend/.env

# Build and start all services
docker compose -f docker-compose.local.yml up --build -d
```

API docs available at `http://localhost:8001/docs` when `DEBUG=true`.

## Environment Variables

See `backend/.env.example` for all available options.

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `SECRET_KEY` | ✅ | JWT signing key (min 32 chars) |
| `GROQ_API_KEY` | ⬜ | Enables AI summaries and replies |
| `RESEND_API_KEY` | ⬜ | Enables email delivery |
| `DEBUG` | ⬜ | Enables API docs + verbose logging |

## Project Structure

```
MA-Analytics/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── core/         # Config, DB, security, logging
│   │   ├── models/       # SQLAlchemy models
│   │   └── pipeline/     # Celery tasks + ML functions
│   ├── alembic/          # Database migrations
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard, DataSources, Inbox, Kanban
│       ├── components/   # AppShell, ProtectedRoute
│       ├── contexts/     # AuthContext
│       └── services/     # API client
└── docker-compose.local.yml
```
