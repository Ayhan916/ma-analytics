# Architecture — MA Analytics

> *"Good architecture makes the system easy to understand, easy to change, easy to test, and easy to deploy. Bad architecture makes all of these hard. The measure of architecture is not elegance — it is fitness for purpose over time."*

---

## 1. Architectural Overview

MA Analytics is a **multi-tier, event-driven SaaS application** built on a clean separation of concerns across four logical layers:

```
┌─────────────────────────────────────────────────────────────┐
│                        PRESENTATION                          │
│              React 18 + TypeScript + Vite                    │
│         (Dashboard, DataSources, Inbox, Kanban)              │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS / REST (JSON)
┌────────────────────────▼────────────────────────────────────┐
│                      APPLICATION                             │
│                  FastAPI (Python 3.9)                        │
│          (Auth, DataSources, Dashboard, Tickets,             │
│                   Messages, Jobs)                            │
└──────────┬─────────────────────────────┬───────────────────┘
           │ SQLAlchemy async             │ Celery .delay()
           │ (asyncpg)                    │
┌──────────▼───────────┐    ┌────────────▼───────────────────┐
│      PERSISTENCE      │    │         COMPUTATION             │
│   PostgreSQL 16       │    │    Celery Worker (Python)       │
│   (users, reviews,   │    │    ├── Google Play Scraper      │
│    tickets, clusters, │    │    ├── Text Preprocessing       │
│    messages, jobs)    │    │    ├── Sentiment Analysis       │
│                       │    │    ├── Sentence Embeddings      │
│   Redis (Celery       │    │    ├── KMeans Clustering        │
│   broker + backend)   │    │    └── LLM Summarization        │
└───────────────────────┘    └────────────────────────────────┘
```

---

## 2. Architectural Principles

### 2.1 Async-First API, Sync Worker

The FastAPI application is **fully asynchronous** (asyncpg + SQLAlchemy async). This ensures the API server handles hundreds of concurrent requests without blocking — critical for a multi-tenant SaaS where users are polling job status every 4 seconds.

The Celery worker is **synchronous** by design. ML inference (transformer models, KMeans) is CPU-bound, not I/O-bound. Using async in the worker would add complexity without benefit. The worker uses a standard psycopg2 SQLAlchemy session.

**Key insight:** The wrong choice here is to use async everywhere. Mixing async and sync ML libraries (PyTorch, sentence-transformers) leads to event loop deadlocks. The architectural separation of concerns (async API ↔ sync worker) prevents this entire class of bugs.

### 2.2 Single-Responsibility Routing

Each router owns exactly one domain:

```
/auth        → authentication (tokens, identity)
/datasources → data source lifecycle (create, list, delete)
/jobs        → pipeline job status (read-only)
/dashboard   → aggregated intelligence (read-only)
/tickets     → ticket CRUD
/messages    → message CRUD + AI generation
```

No cross-domain logic in routers. Business logic lives in services (Phase 2 refactor) or is inlined when simple enough to not warrant extraction.

### 2.3 Event-Driven Pipeline

The ML pipeline is **completely decoupled** from the HTTP request cycle. When a user connects a data source:

1. FastAPI creates `DataSource` + `PipelineJob` records → **responds in <100ms**
2. Celery task dispatched to Redis queue
3. Worker picks up task, runs pipeline (30s–5min depending on review count)
4. Frontend polls `GET /jobs/{id}` every 4 seconds
5. When job is `done`, frontend navigates user to Dashboard

This means: the API is never blocked by ML computation. Users get immediate feedback. The system degrades gracefully under load.

### 2.4 Defense in Depth (Data Isolation)

Every database query that touches user data includes `WHERE user_id = current_user.id`. This is enforced at the **query level**, not just at the application level.

The dependency `get_current_user` extracts the authenticated user from the JWT on every protected request. No endpoint in the protected domain operates without this dependency.

---

## 3. Component Diagram

```
Browser
  │
  │ HTTPS (dev: HTTP to Vite dev server)
  ▼
Nginx (production) / Vite Dev Server (development)
  │
  │ /api/* → proxy → Backend:8001
  │ /*     → serve index.html (SPA routing)
  ▼
FastAPI App (uvicorn, port 8001)
  ├── CORS Middleware
  ├── Request Logging Middleware (structlog + X-Request-ID)
  ├── Rate Limit Middleware (slowapi)
  ├── Global Exception Handler
  │
  ├── Routers
  │   ├── /health          → health check
  │   ├── /auth/*          → register, login, me
  │   ├── /datasources/*   → CRUD + trigger pipeline
  │   ├── /jobs/*          → status polling
  │   ├── /dashboard/*     → summary, issues, strengths, insight
  │   ├── /tickets/*       → CRUD
  │   └── /messages/*      → CRUD + generate-reply, generate-tickets
  │
  ├── Core
  │   ├── config.py        → pydantic-settings, .env loading
  │   ├── database.py      → async SQLAlchemy engine, session factory
  │   ├── security.py      → JWT encode/decode, bcrypt
  │   ├── deps.py          → get_current_user dependency
  │   └── logging.py       → structlog configuration
  │
  └── Models (SQLAlchemy ORM)
      ├── User
      ├── DataSource
      ├── Review
      ├── Cluster
      ├── Ticket
      ├── Message
      └── PipelineJob

Redis (port 6380)
  ├── Celery task queue (broker)
  └── Celery result backend

Celery Worker (same codebase, different entrypoint)
  ├── app.pipeline.tasks.scrape_and_run
  │   ├── google_play_scraper.reviews()
  │   ├── Store Reviews in PostgreSQL (sync)
  │   └── → _run_ml_pipeline()
  │
  ├── app.pipeline.tasks.run_pipeline
  │   └── → _run_ml_pipeline()
  │
  └── _run_ml_pipeline()
      ├── Load Reviews from DB
      ├── clean_text() → preprocessing
      ├── _score_to_sentiment() → star-rating-based sentiment
      │   └── predict_sentiments() → RoBERTa fallback
      ├── create_embeddings() → all-MiniLM-L6-v2
      ├── cluster_texts() → KMeans (neg reviews → issues)
      ├── cluster_texts() → KMeans (pos reviews → strengths)
      ├── get_cluster_label() → TF-IDF keywords
      ├── generate_cluster_summary_groq() → optional LLM
      └── Store Clusters in PostgreSQL

PostgreSQL (port 5434)
  └── Database: ma_analytics
      ├── users
      ├── datasources
      ├── reviews
      ├── clusters
      ├── tickets
      ├── messages
      └── pipeline_jobs
```

---

## 4. Data Flow: Full Pipeline Execution

```
User clicks "Connect & Analyze"
           │
           ▼
POST /datasources/google-play
           │
           ├── Create DataSource record (status: active)
           ├── Create PipelineJob record (status: pending)
           ├── Respond 201 → {datasource_id, job_id}
           │
           └── scrape_and_run.delay(job_id, ds_id, app_id, ...)
                          │
                          ▼ (async, in Celery worker)
               Job status: pending → running / "scraping"
                          │
               google_play_scraper.reviews(app_id, count=200)
                          │ (network call, 5-30 seconds)
                          ▼
               Store N Review records in PostgreSQL
                          │
               Job status: running / "analyzing_sentiment"
                          │
               clean_text() on all review contents
                          │
               Star ratings → sentiment labels
               (or RoBERTa model if no ratings)
                          │
               Update Review.sentiment for all records
                          │
               Job status: running / "creating_embeddings"
                          │
               SentenceTransformer.encode(texts)
               → ndarray shape (N, 384)
                          │
               Job status: running / "clustering"
                          │
               KMeans on negative embeddings → Issue clusters
               KMeans on positive embeddings → Strength clusters
                          │
               TF-IDF labels per cluster
               Groq summaries (if API key present)
                          │
               Store Cluster records in PostgreSQL
               Update DataSource.last_synced
               Update PipelineJob.status = done
                          │
                          ▼
           Frontend polls GET /jobs/{job_id} every 4s
           Status: done → navigate to Dashboard
                          │
                          ▼
           GET /dashboard/summary?datasource_id={id}
           → KPIs, top issues, top strengths, AI insight
```

---

## 5. Deployment Architecture

### Development (Local)

```
┌─────────────────────────────────────────────┐
│              Developer Machine               │
│                                              │
│  Docker Compose:                             │
│  ├── PostgreSQL (port 5434)                  │
│  └── Redis (port 6380)                       │
│                                              │
│  Local processes:                            │
│  ├── uvicorn (port 8001, --reload)           │
│  ├── Celery worker (-P solo, macOS fix)      │
│  └── Vite dev server (port 3002, HMR)        │
└─────────────────────────────────────────────┘
```

### Production (Docker Compose, Single Server)

```
┌─────────────────────────────────────────────────────────┐
│                   VPS (Hetzner CPX31)                    │
│                   8 vCPU, 16GB RAM                       │
│                                                          │
│  Docker Compose:                                         │
│  ├── postgres:16 (internal network only)                 │
│  ├── redis:7-alpine (internal network only)              │
│  ├── backend (FastAPI, port 8000 internal)               │
│  ├── worker (Celery, prefork pool, 4 workers)            │
│  └── frontend (Nginx, port 80 → reverse proxy)          │
│                                                          │
│  External:                                               │
│  └── Caddy / Nginx (TLS termination, port 443)          │
└─────────────────────────────────────────────────────────┘
```

### Production (Phase 2 — Kubernetes)

When customer count exceeds 500:
- FastAPI → deployment (3 replicas, HPA)
- Celery workers → deployment (2–10 replicas, KEDA autoscaling based on Redis queue depth)
- PostgreSQL → managed service (Neon, Supabase, or RDS)
- Redis → managed service (Upstash or ElastiCache)
- Frontend → CDN (Cloudflare Pages or Vercel)

---

## 6. Key Architectural Decisions

### ADR-001: Celery over FastAPI Background Tasks

**Context:** The ML pipeline takes 30s–5min. FastAPI has built-in `BackgroundTasks`.

**Decision:** Use Celery + Redis.

**Rationale:**
- FastAPI BackgroundTasks run in the same process — if the server restarts, the task is lost
- Celery tasks survive server restarts (they're in Redis)
- Celery provides retry logic, task routing, and monitoring (Flower)
- At scale, worker processes can be scaled independently from API processes

**Trade-off:** Adds operational complexity (Redis dependency). Accepted.

---

### ADR-002: Synchronous SQLAlchemy in Celery Worker

**Context:** We use async SQLAlchemy (asyncpg) in FastAPI. Should we use the same in Celery?

**Decision:** Use synchronous SQLAlchemy (psycopg2) in Celery workers.

**Rationale:**
- Celery tasks are synchronous by default. Running asyncio inside sync tasks requires `asyncio.run()` wrapper which creates a new event loop per task — fragile and slow
- ML libraries (PyTorch, sentence-transformers) are not async-aware
- psycopg2 is battle-tested and appropriate for the CPU-bound worker context

**Trade-off:** Two separate database configurations (async + sync). Managed via `app/pipeline/db.py` (sync) vs `app/core/database.py` (async). Clear separation.

---

### ADR-003: Star Rating as Primary Sentiment Signal

**Context:** We have both star ratings (1-5) and a transformer model for sentiment.

**Decision:** Use star rating as primary sentiment signal when available (>50% of reviews have ratings). Use transformer model as fallback.

**Rationale:**
- Star ratings are ground truth from the user — more reliable than NLP inference for German text
- The RoBERTa model (`cardiffnlp/twitter-roberta-base-sentiment-latest`) was trained primarily on English Twitter data — accuracy on German app reviews is poor
- Clustering by star-rating-derived sentiment produces much cleaner clusters

**Trade-off:** Loses nuance (a 3-star review might be very negative or mildly positive). Accepted — aggregate accuracy matters more than edge cases.

---

### ADR-004: TF-IDF for Cluster Labels (not pure LLM)

**Context:** Each cluster needs a human-readable label.

**Decision:** Use TF-IDF keyword extraction (top 3 keywords joined by " / ") as primary labeling. Use Groq LLM for summaries when API key is available.

**Rationale:**
- TF-IDF is deterministic, free, fast, and works offline
- LLM labels are better quality but cost money per cluster and require network access
- The hybrid approach gives usable labels always, great labels when LLM is configured

---

## 7. Scalability Constraints & Mitigations

| Constraint | Current Limit | Mitigation |
|------------|--------------|------------|
| Celery pool=-P solo (macOS) | 1 concurrent task | Linux production uses prefork (4+ workers) |
| Google Play rate limiting | ~1,000 req/hour | Exponential backoff + retry in scraper |
| ML model load time (first request) | ~10-20 seconds | Models loaded once, cached as module-level singletons |
| KMeans determinism | Non-deterministic | `random_state=42` fixed seed |
| PostgreSQL connection pool | 10 connections (asyncpg default) | Increase via `pool_size` in production |

---

*Document Owner: Engineering / Architecture*
*Last Updated: 2026-07*
*Status: v1.0 — Production-ready single-server deployment*
