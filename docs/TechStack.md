# Tech Stack — MA Analytics

## 1. Backend

### Python 3.9
The entire backend runs on Python 3.9. This version was chosen for compatibility with `sentence-transformers 2.7.0`, `torch 2.4.1`, and `transformers 4.44.2`. Python 3.10+ has `match` syntax and `str | None` type unions, but library compatibility at the time of initial build favoured 3.9. All type annotations use `Optional[X]` from `typing` accordingly.

### FastAPI 0.115
Async-first Python API framework. Key reasons for selection:
- Native `async/await` request handling — no thread pool needed for async DB operations
- Automatic OpenAPI schema generation from Pydantic models (available at `/docs` when `DEBUG=true`)
- `Depends()` dependency injection for clean auth and DB session management
- Pydantic v2 validation on all request/response bodies

### SQLAlchemy 2.0 (async)
ORM with full async support via `asyncpg`. The `AsyncSession` pattern is used throughout — no synchronous DB calls in any request path. All queries use `text()` with named parameters to prevent SQL injection.

### Alembic 1.13
Database migration tool. All schema changes go through Alembic migrations — never `Base.metadata.create_all()`. Migration history is the authoritative record of schema evolution.

### PostgreSQL 16 + pgvector 0.3
Primary database. pgvector adds a `vector` column type and the `<=>` cosine distance operator directly in SQL. This enables:
- Semantic search with `ORDER BY embedding <=> CAST(:query AS vector)`
- Hypothesis-guided review retrieval in the Innovation Lab
- Document chunk retrieval for RAG Q&A

All 33,649 reviews have 384-dimensional embeddings stored as `vector(384)` columns. 96% coverage (32,300 of 33,649).

### Redis (via celery[redis] + redis 5.1.1)
Used exclusively as the Celery message broker. No application-level caching. Jobs are enqueued with `.delay()` and consumed by the Celery worker process.

---

## 2. ML / AI Stack

### paraphrase-multilingual-MiniLM-L12-v2 (sentence-transformers)
The single embedding model used across the entire system:
- Review embeddings (stored in PostgreSQL as `vector(384)`)
- Document chunk embeddings (for RAG)
- Hypothesis embeddings (for semantic retrieval in Innovation Lab)
- Query embeddings (for hybrid search)

Using one model for all vectors ensures that cosine similarity is semantically meaningful across all search types. The model is multilingual and handles both German and English review text.

**Dimensions:** 384  
**Max input length:** 128 tokens  
**Language support:** 50+ languages including German and English

### fast_lcf_atepc (ABSA — Aspect-Based Sentiment Analysis)
Custom multilingual checkpoint for Aspect Term Extraction and Polarity Classification. Extracts aspect terms (e.g., "Bluetooth", "Login", "Update") and classifies their sentiment polarity from review sentences. Output feeds into the `review_aspects` table and informs signal classification.

Checkpoint stored at: `backend/checkpoints/ATEPC_MULTILINGUAL_CHECKPOINT/`

### scikit-learn (KMeans clustering)
After embeddings are generated, KMeans clusters reviews by semantic similarity. Cluster count is determined dynamically based on review volume. Results stored in `clusters` and `cluster_reviews` tables and visualised on the Dashboard.

### anthropic >= 0.120.0 (Claude Haiku)
Primary AI provider for all generation tasks. Used for:
- Innovation Brief JSON generation (structured output, temperature 0.6)
- Long-form concept description text (temperature 0.4)
- Brief Copilot chat (temperature 0.4)
- Document Q&A (temperature 0.3)

Model: `claude-haiku-4-5-20251001` (configurable via `ANTHROPIC_MODEL` env var).

The Anthropic SDK is called synchronously in FastAPI routes (not async). This is intentional — the Claude API call is the primary latency source and is already running in an async endpoint context.

### groq 1.0.0 (Fallback)
Three-model cascade as fallback when Claude is unavailable or rate-limited:
1. `llama-3.3-70b-versatile` — best quality
2. `llama-3.1-70b-versatile` — slightly older, similar quality
3. `gemma2-9b-it` — fastest, lowest quality

Two API keys are rotated to maximise throughput before hitting daily limits. The `llama-3.1-8b-instant` model is intentionally excluded from JSON generation because it reproduces schema placeholder text literally.

---

## 3. Frontend

### React 18 + TypeScript
All UI components are functional components with hooks. TypeScript strict mode is enabled.

### Vite 6
Build tool and dev server. Dev server runs on port 3002. Production build outputs to `frontend/dist/`.

### Tailwind CSS
Utility-first CSS. Dark theme throughout — slate-950 background, slate-800/40 cards. No custom CSS files.

### Lucide React
Icon library. Consistent icon usage across all pages.

### Axios (via apiClient)
HTTP client for all API calls. Configured with:
- `baseURL: http://localhost:8000`
- `withCredentials: true` (for cookie-based auth)
- Response interceptor: 401 → redirect to login

Two axios instances:
- `apiClient` — with interceptors, used for all authenticated calls
- `authAxios` — without interceptors, used only for `login()` and `register()` to avoid redirect loops on 401

### jsPDF (client-side PDF export)
Used in the Innovation Lab to generate PDF exports of briefs. No server-side PDF generation. The `exportBriefPdf.ts` utility generates a multi-page A4 document with: header, hypothesis validation block, analysis section, feature table, risk block, concept description, data sources table, and page footers.

---

## 4. Infrastructure

### Docker Compose (local)
`docker-compose.local.yml` starts two services for local development:
- `db`: PostgreSQL 16 with pgvector extension, port 5434, persistent volume
- `redis`: Redis 7, port 6380, in-memory only

The backend and frontend are not containerised in local dev — they run as native processes for hot-reload performance.

### Celery Worker
Background task processor. Required for the data pipeline. Separate process from the FastAPI server. On macOS, must run with `-P solo` due to macOS fork restrictions with PyTorch. On Linux, use the default prefork pool.

---

## 5. Development Tooling

| Tool | Purpose |
|------|---------|
| ESLint | Frontend linting — configured with TypeScript + React rules |
| pytest 8.3 | Backend testing framework |
| pytest-asyncio | Async test support |
| structlog 24.4 | Structured JSON logging in backend — every request logs `method`, `path`, `status`, `duration_ms`, `request_id` |
| slowapi 0.1.9 | Rate limiting on auth endpoints |
| python-dotenv | `.env` file loading for local dev |

---

## 6. Key Dependency Versions

```
# Backend
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
sqlalchemy==2.0.35
alembic==1.13.3
asyncpg==0.29.0
anthropic>=0.120.0
groq==1.0.0
celery==5.4.0
redis==5.1.1
sentence-transformers==2.7.0
transformers==4.44.2
torch==2.4.1
scikit-learn==1.4.2
numpy==1.26.4
pgvector==0.3.2
google-play-scraper==1.2.4
langdetect==1.0.9
resend==2.27.0
slowapi==0.1.9
structlog==24.4.0

# Frontend (key packages)
react@18
typescript@5
vite@6
tailwindcss@3
axios
lucide-react
jspdf
html2canvas
```
