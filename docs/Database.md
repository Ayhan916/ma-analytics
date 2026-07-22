# Database — MA Analytics

> *"The database is the most important architectural decision you make. It outlives every framework, every language, every team. Get the schema right the first time, or pay compound interest on the debt forever."*

---

## 1. Overview

**Database:** PostgreSQL 16
**ORM:** SQLAlchemy 2.0 (async, `mapped_column` style)
**Migration tool:** Alembic 1.13 (autogenerate)
**Schema name:** `public` (default)

**Design principles:**
- All primary keys are UUIDs (string). Avoids sequential ID leakage, safe for distributed systems, works with client-side ID generation.
- All timestamps include timezone (`DateTime(timezone=True)`). Stored as UTC, displayed in user's local timezone by the frontend.
- Foreign keys always constrained at the database level (not just application level).
- JSON columns for truly variable-length, schemaless data (labels, examples, subtasks). Everything with a defined structure is a proper column.

---

## 2. Entity Relationship Diagram

```
users
  │
  ├──< datasources (user_id)
  │       │
  │       ├──< reviews (datasource_id)
  │       ├──< clusters (datasource_id)
  │       └──< pipeline_jobs (datasource_id)
  │
  ├──< tickets (user_id)
  │
  └──< messages (user_id)
```

**Cascade rules:**
- Delete `user` → deletes all `datasources`, `tickets`, `messages`
- Delete `datasource` → deletes all `reviews`, `clusters`, `pipeline_jobs`

---

## 3. Table Definitions

### 3.1 `users`

Stores registered user accounts. The root entity — all other user data is linked here.

```sql
CREATE TABLE users (
    id         VARCHAR PRIMARY KEY,
    email      VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR NOT NULL,
    full_name  VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_users_email ON users(email);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | Client-generated UUID |
| `email` | VARCHAR | NOT NULL | Unique, used for authentication |
| `hashed_password` | VARCHAR | NOT NULL | bcrypt hash (60 chars) |
| `full_name` | VARCHAR | NULL | Display name, optional |
| `created_at` | TIMESTAMPTZ | NOT NULL | Account creation timestamp |

**Indexes:**
- `PRIMARY KEY (id)` — B-tree
- `UNIQUE INDEX ix_users_email (email)` — Used by login query: `WHERE email = $1`

**Security note:** `email` is indexed for login performance. `hashed_password` is never returned by any API endpoint.

---

### 3.2 `datasources`

Represents a connected data source (Google Play app or CSV upload).

```sql
CREATE TABLE datasources (
    id         VARCHAR PRIMARY KEY,
    user_id    VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       VARCHAR NOT NULL,
    app_id     VARCHAR,
    type       datasourcetype NOT NULL,
    last_synced TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TYPE datasourcetype AS ENUM ('google_play', 'csv');
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | Client-generated UUID |
| `user_id` | VARCHAR | NOT NULL | FK → `users.id` |
| `name` | VARCHAR | NOT NULL | User-defined display name (e.g., "BMW Connected") |
| `app_id` | VARCHAR | NULL | Google Play App ID. NULL for CSV sources |
| `type` | ENUM | NOT NULL | `google_play` or `csv` |
| `last_synced` | TIMESTAMPTZ | NULL | Timestamp of last successful pipeline completion |
| `created_at` | TIMESTAMPTZ | NOT NULL | When the data source was created |

**Relationships:**
- `user_id` → `users.id` (CASCADE DELETE)
- One `DataSource` → many `Review`s
- One `DataSource` → many `Cluster`s
- One `DataSource` → many `PipelineJob`s

---

### 3.3 `reviews`

Individual customer reviews scraped from Google Play or imported via CSV.

```sql
CREATE TABLE reviews (
    id             VARCHAR PRIMARY KEY,
    datasource_id  VARCHAR NOT NULL REFERENCES datasources(id) ON DELETE CASCADE,
    content        TEXT NOT NULL,
    score          FLOAT,
    sentiment      VARCHAR,
    version        VARCHAR,
    reviewed_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | |
| `datasource_id` | VARCHAR | NOT NULL | FK → `datasources.id` |
| `content` | TEXT | NOT NULL | Full review text |
| `score` | FLOAT | NULL | Star rating (1.0–5.0). NULL if not available |
| `sentiment` | VARCHAR | NULL | `positive`, `negative`, `neutral`. Populated by pipeline |
| `version` | VARCHAR | NULL | App version at time of review (from Play Store metadata) |
| `reviewed_at` | TIMESTAMPTZ | NULL | When the user wrote the review |
| `created_at` | TIMESTAMPTZ | NOT NULL | When we imported it |

**Volume expectations:**
- Typical data source: 50–500 reviews
- Large data source: up to 10,000 reviews
- At 500 customers × 500 reviews avg = 250,000 total rows — trivial for PostgreSQL

**Pipeline behavior:** After scraping, `sentiment` is NULL. The ML pipeline populates `sentiment` for all reviews before clustering.

---

### 3.4 `clusters`

ML-generated topic clusters derived from review analysis. Each cluster represents a pattern across multiple reviews.

```sql
CREATE TABLE clusters (
    id             VARCHAR PRIMARY KEY,
    datasource_id  VARCHAR NOT NULL REFERENCES datasources(id) ON DELETE CASCADE,
    type           clustertype NOT NULL,
    label          VARCHAR NOT NULL,
    summary        TEXT,
    solution       TEXT,
    mentions       INTEGER DEFAULT 0,
    examples       JSON DEFAULT '[]',
    mentions_over_time JSON DEFAULT '{}',
    sentiment_counts   JSON DEFAULT '{}',
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TYPE clustertype AS ENUM ('issue', 'strength');
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | |
| `datasource_id` | VARCHAR | NOT NULL | FK → `datasources.id` |
| `type` | ENUM | NOT NULL | `issue` (from negative reviews) or `strength` (from positive) |
| `label` | VARCHAR | NOT NULL | Human-readable label. Generated by TF-IDF or Groq LLM |
| `summary` | TEXT | NULL | 1-2 sentence description of what the cluster represents |
| `solution` | TEXT | NULL | AI-generated suggested fix (Phase 2 feature) |
| `mentions` | INTEGER | NOT NULL | Count of reviews assigned to this cluster |
| `examples` | JSON | NOT NULL | Array of up to 5 representative review text strings |
| `mentions_over_time` | JSON | NOT NULL | `{"2024-01": 3, "2024-02": 5, ...}` — for trend charts (Phase 2) |
| `sentiment_counts` | JSON | NOT NULL | `{"positive": 2, "negative": 8, "neutral": 1}` — within-cluster breakdown |
| `created_at` | TIMESTAMPTZ | NOT NULL | When the cluster was generated |

**JSON column schema — `examples`:**
```json
[
  "Anmeldung nicht möglich.. Peinliche app",
  "Kein Login mehr möglich.",
  "Keine login möglichkeit"
]
```

**Regeneration:** Clusters are deleted and regenerated each time the pipeline runs on a data source (`DELETE WHERE datasource_id = $1` before inserting new clusters).

---

### 3.5 `pipeline_jobs`

Tracks the status of every ML pipeline execution. One job per scrape or re-run operation.

```sql
CREATE TABLE pipeline_jobs (
    id             VARCHAR PRIMARY KEY,
    datasource_id  VARCHAR NOT NULL REFERENCES datasources(id) ON DELETE CASCADE,
    status         jobstatus DEFAULT 'pending',
    progress       VARCHAR,
    error          TEXT,
    review_count   INTEGER DEFAULT 0,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    finished_at    TIMESTAMPTZ
);

CREATE TYPE jobstatus AS ENUM ('pending', 'running', 'done', 'failed');
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | Also used as Celery task ID reference |
| `datasource_id` | VARCHAR | NOT NULL | FK → `datasources.id` |
| `status` | ENUM | NOT NULL | Current pipeline state |
| `progress` | VARCHAR | NULL | Human-readable stage description |
| `error` | TEXT | NULL | Error message if `status = failed` |
| `review_count` | INTEGER | NOT NULL | Number of reviews processed |
| `created_at` | TIMESTAMPTZ | NOT NULL | When the job was created |
| `finished_at` | TIMESTAMPTZ | NULL | When the job completed (success or failure) |

**Status lifecycle:**
```
pending → running/scraping → running/saving_reviews → 
running/analyzing_sentiment → running/creating_embeddings → 
running/clustering → done
                 └→ failed (at any stage)
```

---

### 3.6 `tickets`

Kanban board tickets. Can be created manually, via AI generation from messages, or in the future via cluster-to-ticket export.

```sql
CREATE TABLE tickets (
    id            VARCHAR PRIMARY KEY,
    user_id       VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         VARCHAR NOT NULL,
    description   TEXT,
    priority      ticketpriority DEFAULT 'Medium',
    status        ticketstatus DEFAULT 'Backlog',
    customer_name VARCHAR,
    labels        JSON DEFAULT '[]',
    subtasks      JSON DEFAULT '[]',
    comments      JSON DEFAULT '[]',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TYPE ticketpriority AS ENUM ('Low', 'Medium', 'High');
CREATE TYPE ticketstatus AS ENUM ('Backlog', 'Todo', 'In Progress', 'Done');
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | |
| `user_id` | VARCHAR | NOT NULL | FK → `users.id` |
| `title` | VARCHAR | NOT NULL | Short ticket title (max 200 chars) |
| `description` | TEXT | NULL | Full description, may be AI-generated |
| `priority` | ENUM | NOT NULL | `Low`, `Medium`, `High` |
| `status` | ENUM | NOT NULL | Kanban column: `Backlog`, `Todo`, `In Progress`, `Done` |
| `customer_name` | VARCHAR | NULL | Populated when ticket is generated from a customer message |
| `labels` | JSON | NOT NULL | Array of string tags, e.g. `["bug", "auth", "P0"]` |
| `subtasks` | JSON | NOT NULL | Array of `{text: string, done: boolean}` objects |
| `comments` | JSON | NOT NULL | Array of string comments (Phase 2: structured with author + timestamp) |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Updated via application logic on PATCH |

**JSON column schema — `subtasks`:**
```json
[
  {"text": "Reproduce the authentication error", "done": false},
  {"text": "Check JWT validation logic", "done": true}
]
```

---

### 3.7 `messages`

Customer messages in the Inbox. Can be manually created (via form) or in the future ingested from email/support tools.

```sql
CREATE TABLE messages (
    id         VARCHAR PRIMARY KEY,
    user_id    VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       VARCHAR,
    email      VARCHAR,
    text       TEXT NOT NULL,
    sentiment  VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | VARCHAR (UUID) | NOT NULL | |
| `user_id` | VARCHAR | NOT NULL | FK → `users.id` |
| `name` | VARCHAR | NULL | Customer's name |
| `email` | VARCHAR | NULL | Customer's email (for sending replies) |
| `text` | TEXT | NOT NULL | Full message content |
| `sentiment` | VARCHAR | NULL | `positive`, `negative`, `neutral` — auto-detected on creation |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

---

## 4. Migration Strategy

**Tool:** Alembic with autogenerate

**Workflow for schema changes:**
```bash
# 1. Modify SQLAlchemy model
# 2. Generate migration
alembic revision --autogenerate -m "add_column_description_to_clusters"
# 3. Review generated SQL
# 4. Apply
alembic upgrade head
# 5. Rollback if needed
alembic downgrade -1
```

**Current migrations:**
- `230a0afefba4_initial_schema.py` — All 7 tables, all ENUMs, initial schema

**Migration naming convention:** `{revision_hash}_{description_in_snake_case}.py`

**Production deployment:** `alembic upgrade head` runs automatically in `start.sh` before uvicorn starts. Zero-downtime migrations require backward-compatible changes (additive only, never rename/delete without a deprecation period).

---

## 5. Performance Considerations

### Indexes (Current)

| Table | Index | Purpose |
|-------|-------|---------|
| `users` | `email` (UNIQUE) | Login query |
| `datasources` | `user_id` (FK) | List datasources by user |
| `reviews` | `datasource_id` (FK) | Load reviews for pipeline |
| `clusters` | `datasource_id` (FK) | Load clusters for dashboard |
| `pipeline_jobs` | `datasource_id` (FK) | Find latest job for datasource |
| `tickets` | `user_id` (FK) | List tickets by user |
| `messages` | `user_id` (FK) | List messages by user |

### Indexes to Add (Phase 2)

```sql
-- For filtering tickets by status + priority
CREATE INDEX ix_tickets_user_status ON tickets(user_id, status);
CREATE INDEX ix_tickets_user_priority ON tickets(user_id, priority);

-- For trend queries on reviews
CREATE INDEX ix_reviews_datasource_reviewed_at ON reviews(datasource_id, reviewed_at);

-- For listing jobs by creation time
CREATE INDEX ix_pipeline_jobs_datasource_created ON pipeline_jobs(datasource_id, created_at DESC);
```

### Query Optimization Patterns

**N+1 prevention:** The `GET /datasources` endpoint performs one query for datasources, then N queries for latest job per datasource. At current scale (typical: <20 datasources per user) this is acceptable. When optimizing, use:

```sql
SELECT DISTINCT ON (datasource_id) *
FROM pipeline_jobs
WHERE datasource_id = ANY($1)
ORDER BY datasource_id, created_at DESC;
```

**Review count:** Currently uses `SELECT COUNT(*)` per datasource. Replace with denormalized `review_count` column on `datasources` table when needed.

---

## 6. Backup Strategy

**Development:** Manual snapshots before destructive migrations.

**Production (Phase 1):**
```bash
# Daily backup via cron
pg_dump -h localhost -U ma_analytics ma_analytics \
  | gzip > /backups/ma_analytics_$(date +%Y%m%d).sql.gz
```

**Production (Phase 2):** Managed PostgreSQL with automated daily backups and point-in-time recovery (PITR). Providers: Neon, Supabase, Render, AWS RDS.

**Retention:** 7 days rolling, monthly archives for 1 year.

---

## 7. Data Volume Projections

| Metric | Year 1 | Year 2 | Year 3 |
|--------|--------|--------|--------|
| Users | 500 | 2,000 | 5,000 |
| Data Sources | 1,500 | 8,000 | 25,000 |
| Reviews | 500K | 5M | 20M |
| Clusters | 15K | 80K | 250K |
| Tickets | 25K | 200K | 800K |
| Total DB size | ~2GB | ~20GB | ~80GB |

PostgreSQL handles 80GB trivially on a single server. Partitioning (`reviews` by `datasource_id` or `created_at`) becomes relevant above 100M rows.

---

*Document Owner: Engineering / Database Architecture*
*Last Updated: 2026-07*
*Status: v1.0 Schema — Production*
