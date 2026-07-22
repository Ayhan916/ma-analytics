# Tech Stack — MA Analytics

> *"The best technology choice is the one your team can execute on, that solves the problem correctly, and that you won't regret in 3 years. Novelty is not a virtue. Boring is underrated."*

---

## 1. Decision Framework

Every technology in this stack was chosen against three criteria:

1. **Correctness** — Does it solve the technical problem well?
2. **Operability** — Can one developer run it, debug it, and maintain it?
3. **Longevity** — Will it still be the right choice in 3 years?

---

## 2. Backend

### Python 3.9
**Why:** Python is the undisputed language of machine learning. Every NLP library (transformers, sentence-transformers, scikit-learn) has first-class Python support. Using any other language would mean bridging to Python anyway.

**Why 3.9 specifically:** Balance of modern features (PEP 585 built-in generics) with macOS system Python compatibility and library support. Python 3.11+ brings performance improvements but `sentence-transformers` 2.7.0 has better-tested compatibility with 3.9.

**Trade-off accepted:** No `match` statements (Python 3.10+), no `str | None` type syntax (requires `Optional[str]`).

---

### FastAPI 0.115
**Why:** FastAPI is the correct choice for async Python APIs in 2024-2026. Key advantages:

- **Automatic OpenAPI generation** — every endpoint is self-documenting at `/docs`
- **Pydantic integration** — request/response validation is built-in, not bolted on
- **Async-native** — built on Starlette + asyncio, handles thousands of concurrent connections on a single process
- **Dependency injection** — `Depends(get_current_user)` pattern eliminates boilerplate auth code from every endpoint
- **Type annotations** — IDEs and linters catch errors at development time, not runtime

**Alternatives considered:**
- Django REST Framework: Too heavy, ORM doesn't support async well
- Flask: No async support, no automatic validation
- aiohttp: Lower-level, more code for same result

---

### SQLAlchemy 2.0 (async) + asyncpg
**Why SQLAlchemy 2.0:** The `mapped_column` / `Mapped[]` ORM style introduced in 2.0 is significantly cleaner than legacy declarative. Type hints work correctly. The async session API is stable.

**Why asyncpg:** Fastest PostgreSQL driver for Python. Pure async, no thread pool overhead. 3-5x faster than psycopg2 for I/O-bound database operations.

**Why not Tortoise ORM or SQLModel:** Less mature, smaller community, fewer escape hatches when you need raw SQL.

---

### Alembic 1.13
**Why:** The standard for SQLAlchemy migrations. `alembic revision --autogenerate` inspects the ORM models and generates migration files — no manual SQL writing for schema changes. Migration history is version-controlled alongside code.

---

### Celery 5.4 + Redis
**Why Celery:** The most battle-tested Python task queue. Supports retry logic, task routing, priority queues, monitoring (Flower), and horizontal scaling. The industry standard.

**Why Redis as broker:** Simpler operationally than RabbitMQ. Sufficient durability for our use case (task loss on Redis crash is acceptable — user can retry). Also used as Celery result backend.

**Why not:** FastAPI BackgroundTasks (not durable), RQ (less feature-rich), Dramatiq (smaller community).

---

### passlib[bcrypt] 1.7.4 + bcrypt 4.0.1
**Why bcrypt:** The correct algorithm for password hashing. Adaptive cost factor (currently 12 rounds), resistant to GPU acceleration attacks, industry standard since 2006.

**Version pinning (bcrypt 4.0.1):** passlib 1.7.4 has a compatibility issue with bcrypt ≥ 4.1 that raises a ValueError on passwords regardless of length. bcrypt 4.0.1 is the last version fully compatible with passlib 1.7.4. This is a known upstream issue; will be resolved when passlib releases 1.7.5.

---

### python-jose[cryptography] 3.3
**Why:** JWT token creation and validation. The `cryptography` backend provides better performance and security than the pure-Python backend.

**Algorithm used:** HS256 (HMAC-SHA256). Suitable for single-server deployments. RS256 (asymmetric) would be preferable for microservices where multiple services need to verify tokens.

---

### structlog 24.4
**Why:** Structured logging that outputs machine-readable JSON in production and human-readable colored output in development. Every log line is a dictionary — queryable in log aggregation systems (Datadog, Loki, CloudWatch). Traditional Python logging outputs strings that are hard to parse programmatically.

**Context variable binding:** `structlog.contextvars.bind_contextvars(request_id=...)` propagates the request ID to every log line within that request's execution context automatically.

---

### slowapi 0.1.9
**Why:** Rate limiting middleware for FastAPI. Built on limits library, uses the Starlette request object. Zero-configuration integration with FastAPI's decorator pattern.

---

## 3. Machine Learning

### sentence-transformers 2.7.0 (all-MiniLM-L6-v2)
**Why this model:** The best trade-off of quality vs. speed for semantic similarity tasks:

- **Dimensionality:** 384 dimensions (vs. 768 for larger models) — 2x smaller, 3x faster, 5% accuracy loss
- **Speed:** ~2,000 sentences/second on CPU, ~10,000/second on GPU/MPS
- **Quality:** Trained on 1B+ sentence pairs — excellent for semantic clustering
- **License:** Apache 2.0 — commercial use permitted

**Why sentence-transformers vs. direct Hugging Face transformers:** sentence-transformers provides the `encode()` method that handles batching, padding, and pooling automatically. 3 lines of code vs. 30.

---

### cardiffnlp/twitter-roberta-base-sentiment-latest
**Why:** State-of-the-art sentiment classification fine-tuned on 124M tweets. Understands informal language, abbreviations, and colloquialisms common in app reviews.

**Limitation acknowledged:** Trained primarily on English. German text accuracy is reduced. This is why we use star ratings as primary sentiment signal (ADR-003) and only fall back to this model when ratings are unavailable.

---

### scikit-learn 1.4.2 (KMeans, TF-IDF)
**Why KMeans:** Fast, deterministic (with fixed seed), well-understood. For 50-500 reviews, KMeans is the correct choice. HDBSCAN or UMAP-based clustering would be superior for 10,000+ reviews with irregular cluster shapes — planned for Phase 2.

**Why TF-IDF for labels:** Extracts the most statistically distinctive terms from a cluster corpus. Produces keywords like "login / nicht / möglich" which immediately communicate the cluster topic. Zero API cost.

---

## 4. Frontend

### React 18 + TypeScript + Vite
**Why React 18:** The dominant frontend framework. Concurrent rendering, Suspense, and the hooks model are mature and well-documented. The component model maps cleanly to the UI requirements.

**Why TypeScript:** Catches a class of runtime errors at compile time. Essential for a codebase that will be maintained and extended. API response types can be validated against interface definitions.

**Why Vite:** 10-100x faster than webpack for development HMR. Build times under 2 seconds. The correct choice for any new React project in 2024+.

---

### Tailwind CSS 3
**Why:** Utility-first CSS eliminates the cognitive overhead of naming CSS classes. The design system (spacing scale, color palette, typography) is consistent by default. Dark mode (`dark:` prefix) works out of the box.

**Alternative considered:** CSS Modules — more verbose, slower to iterate.

---

### Axios
**Why:** Interceptors for automatic Authorization header injection and 401 redirect. Cleaner API than `fetch` for the patterns we use (base URL, request/response transformation). The `authApi` / `apiClient` split (auth endpoints without interceptors, all other endpoints with interceptors) is a well-established pattern.

---

### lucide-react
**Why:** 1,000+ clean, consistent SVG icons as React components. Tree-shakeable (only icons used are in the bundle). The spiritual successor to Feather Icons.

---

## 5. Infrastructure

### PostgreSQL 16
**Why:** The correct database for this application. ACID-compliant, JSON column support (for labels, subtasks, comments, examples), excellent async driver (asyncpg), proven at any scale from single-user to billion-row tables.

**JSON columns used:** `Cluster.examples`, `Cluster.mentions_over_time`, `Cluster.sentiment_counts`, `Ticket.labels`, `Ticket.subtasks`, `Ticket.comments`. These fields benefit from JSON's flexibility (variable structure) without warranting a separate NoSQL database.

---

### Redis 7
**Why:** Celery's preferred broker. Sub-millisecond latency. Atomic operations (LPUSH/BRPOP for the queue, SET/GET for results). In-memory with optional persistence.

**Persistence configuration:** `appendonly yes` in production to survive restarts with minimal task loss.

---

### Docker + Docker Compose
**Why Docker:** Eliminates "works on my machine" problems. The same image runs on macOS (development) and Linux (production).

**Why Compose:** Sufficient for single-server deployments. Service health checks (`pg_isready`) ensure the backend waits for PostgreSQL before starting. Kubernetes migration path clear when needed.

---

### Nginx (production)
**Why:** Serves the React SPA (static files) and proxies `/api/*` to the FastAPI backend. Handles TLS termination (with Caddy or Let's Encrypt). Gzip compression for static assets. Connection rate limiting at the edge.

---

## 6. AI / External Services

### Groq (llama3-8b-8192)
**Why Groq:** The fastest LLM inference API available. llama3-8b runs at 800+ tokens/second — fast enough that cluster summary generation is imperceptible to users. Free tier is generous for development.

**Why llama3-8b:** Good enough for summarization and simple generation tasks. Smaller models (mistral-7b) are slightly worse; larger models (llama3-70b) are 10x slower with marginal quality improvement for our use case.

**Architecture note:** All Groq calls have graceful fallbacks. If the API key is not set or the call fails, rule-based fallbacks activate. This means the system works fully offline — Groq is enhancement, not dependency.

---

### Resend (email)
**Why:** Modern email API with excellent developer experience. Deliverability-focused. Simple REST API. Free tier (100 emails/day) sufficient for early customers.

**Status:** Integrated in configuration; email delivery endpoint (POST /messages/{id}/send-reply) is P1 — planned for next iteration.

---

## 7. Development Tools

| Tool | Purpose | Why |
|------|---------|-----|
| `uvicorn --reload` | Hot-reload in development | Fastest Python ASGI server |
| `alembic autogenerate` | Schema migrations | Never write SQL for schema changes |
| `python-dotenv` | .env file loading | Standard, simple |
| `pydantic-settings` | Type-safe config | Env vars validated as typed fields |
| ESLint + TypeScript | Frontend linting | Catch errors before runtime |
| `npm run build` | Production frontend build | Vite tree-shaking, minification |

---

## 8. What We Deliberately Did NOT Use

| Technology | Why Not |
|------------|---------|
| Django | Too heavy, poor async story |
| MongoDB | JSON columns in PostgreSQL are sufficient; no need for schemaless |
| GraphQL | REST is simpler for this access pattern; no N+1 problem at this scale |
| Redux / Zustand | React state + context sufficient for current complexity |
| WebSockets | Polling every 4s is sufficient for job status; WebSockets add complexity |
| Kubernetes | Premature at current scale; Compose is operationally simpler |
| OpenAI GPT-4 | 100x more expensive than Groq for equivalent quality at our use case |
| Pinecone / Weaviate | Local KMeans is sufficient; vector DB adds operational overhead |

---

*Document Owner: Engineering / CTO*
*Last Updated: 2026-07*
*Status: v1.0 Stable*
