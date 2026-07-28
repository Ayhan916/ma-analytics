# Database — MA Analytics

**Engine:** PostgreSQL 16 with pgvector 0.3 extension  
**ORM:** SQLAlchemy 2.0 async (asyncpg driver)  
**Migration tool:** Alembic 1.13  
**Connection:** `postgresql+asyncpg://ma_analytics:ma_analytics@localhost:5434/ma_analytics` (local)

---

## Schema Overview

```
users
  │
  ├──< datasources (user_id)
  │       │
  │       ├──< reviews (datasource_id)
  │       │       │
  │       │       ├── embedding: vector(384)        ← pgvector
  │       │       ├── search_vector: tsvector        ← full-text
  │       │       │
  │       │       ├──< review_sentences (review_id)
  │       │       ├──< review_aspects (review_id)
  │       │       └──< review_signals (review_id)
  │       │
  │       ├──< clusters (datasource_id)
  │       │       └──< cluster_reviews (cluster_id, review_id)
  │       │
  │       └──< feature_narratives (datasource_id)
  │
  ├──< innovation_briefs (user_id)
  ├──< messages (user_id)
  ├──< tickets (user_id)
  ├──< intelligence_documents (user_id)
  │       └──< intelligence_chunks (document_id)
  └──< pipeline_jobs (user_id)
```

---

## Table Definitions

### users
Stores authenticated user accounts.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| email | VARCHAR | Unique, indexed |
| hashed_password | VARCHAR | bcrypt hash |
| is_active | BOOLEAN | Default true |
| reset_token | VARCHAR | Nullable — password reset |
| reset_token_expires | TIMESTAMPTZ | Nullable |
| created_at | TIMESTAMPTZ | |

---

### datasources
One row per app or CSV upload.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| user_id | VARCHAR | FK → users.id |
| name | VARCHAR | Display name (e.g. "My BMW App") |
| app_id | VARCHAR | Google Play App ID (nullable for CSV) |
| industry | VARCHAR | E.g. "Automotive" |
| job_status | VARCHAR | `pending` / `running` / `done` / `failed` |
| job_id | VARCHAR | Celery task ID |
| scrape_params | JSONB | Scrape config (language, max_reviews, etc.) |
| created_at | TIMESTAMPTZ | |

---

### reviews
One row per customer review. This is the largest table — 33,649 rows in current data.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| datasource_id | VARCHAR | FK → datasources.id |
| external_id | VARCHAR | App store review ID (dedup) |
| content | TEXT | Review text |
| score | FLOAT | Star rating (1.0–5.0) |
| sentiment | VARCHAR | `positive` / `negative` / `neutral` |
| language | VARCHAR | `de` / `en` / other |
| version | VARCHAR | App version reviewed |
| version_source | VARCHAR | Source of version info |
| review_type | VARCHAR | `scrape` / `csv` |
| reviewed_at | TIMESTAMPTZ | Original review date |
| reply_content | TEXT | Developer reply (if any) |
| reply_at | TIMESTAMPTZ | |
| embedding | vector(384) | Sentence embedding — pgvector |
| search_vector | tsvector | Full-text search index |
| created_at | TIMESTAMPTZ | |

**Indexes:**
- `idx_reviews_datasource_id` — fast filter by app
- `idx_reviews_score` — filter by star rating
- `idx_reviews_language` — filter by language
- `idx_reviews_embedding` — ivfflat index for approximate nearest-neighbour search
- `idx_reviews_search_vector` — GIN index for full-text search

**Coverage:** 32,300 of 33,649 reviews have embeddings (96%). All 33,649 have tsvector.

---

### review_sentences
Individual sentences extracted from reviews during the pipeline.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| review_id | VARCHAR | FK → reviews.id |
| datasource_id | VARCHAR | Denormalised for query speed |
| position | INTEGER | Sentence index within review |
| text | TEXT | Sentence text |
| topic_id | INTEGER | LDA topic assignment (nullable) |
| created_at | TIMESTAMPTZ | |

---

### review_aspects
Aspect-Based Sentiment Analysis output — extracted aspect terms with polarity.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| review_id | VARCHAR | FK → reviews.id |
| sentence_id | VARCHAR | FK → review_sentences.id |
| aspect | VARCHAR | Extracted aspect term |
| polarity | VARCHAR | `positive` / `negative` / `neutral` |
| confidence | FLOAT | Model confidence score |

---

### review_signals
Structured signals extracted from reviews. This is the core analytical table.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| review_id | VARCHAR | FK → reviews.id |
| sentence_id | VARCHAR | FK → review_sentences.id |
| datasource_id | VARCHAR | Denormalised |
| feature | VARCHAR | Signal category (e.g. "Updates", "Bluetooth", "Navigation") |
| signal_type | VARCHAR | `feature_request` / `bug` / `ux` / `performance` / `general` / `resolution` |
| severity | INTEGER | 0–5 (5 = most severe) |
| is_resolved | BOOLEAN | Whether the issue appears to be resolved |
| version_hint | VARCHAR | App version where issue appears |
| aspect_id | VARCHAR | FK → review_aspects.id (nullable) |
| created_at | TIMESTAMPTZ | |

**Current data:**
- 41,620 total signal instances
- 25 unique feature labels
- Signal type distribution: bug (24,196) · general (11,904) · feature_request (2,095) · performance (1,637) · ux (1,173) · resolution (615)

**Key queries:**
```sql
-- Signal aggregation (Innovation Lab standard mode)
SELECT feature, COUNT(*) AS total_mentions,
       COUNT(*) FILTER (WHERE signal_type = 'feature_request') AS fr_mentions,
       COUNT(DISTINCT datasource_id) AS app_count,
       AVG(severity) AS avg_severity
FROM review_signals rs
JOIN datasources ds ON rs.datasource_id = ds.id
WHERE ds.user_id = :uid
GROUP BY feature HAVING COUNT(*) >= 2
ORDER BY COUNT(DISTINCT datasource_id) DESC, fr_mentions DESC;

-- Co-occurrence graph (Signal-Graph)
SELECT a.feature, b.feature, COUNT(DISTINCT a.review_id) AS co_count
FROM review_signals a
JOIN review_signals b ON a.review_id = b.review_id AND a.feature < b.feature
GROUP BY a.feature, b.feature HAVING COUNT(DISTINCT a.review_id) >= 10
ORDER BY co_count DESC;

-- Hypothesis-guided retrieval (semantic search → signal aggregation)
WITH hypothesis_reviews AS (
  SELECT r.id, r.datasource_id,
         r.embedding <=> CAST(:hyp_vec AS vector) AS distance
  FROM reviews r JOIN datasources ds ON r.datasource_id = ds.id
  WHERE ds.user_id = :uid AND r.embedding IS NOT NULL
  ORDER BY r.embedding <=> CAST(:hyp_vec AS vector) LIMIT 500
)
SELECT rs.feature, COUNT(DISTINCT hr.id) AS total_mentions, ...
FROM hypothesis_reviews hr
JOIN review_signals rs ON rs.review_id = hr.id ...
GROUP BY rs.feature;
```

---

### feature_narratives
AI-generated narrative summaries per feature per datasource. Pre-computed and stored.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| datasource_id | VARCHAR | FK → datasources.id |
| feature | VARCHAR | Signal feature label |
| feature_request_narrative | TEXT | Summary of user wishes for this feature |
| bug_narrative | TEXT | Summary of bugs reported |
| created_at | TIMESTAMPTZ | |

---

### clusters
KMeans cluster metadata.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| datasource_id | VARCHAR | FK → datasources.id |
| label | VARCHAR | AI-generated cluster label |
| size | INTEGER | Number of reviews in cluster |
| sentiment_score | FLOAT | Average sentiment |
| example_reviews | JSONB | Array of example review texts |
| created_at | TIMESTAMPTZ | |

### cluster_reviews
Many-to-many join between clusters and reviews.

| Column | Type | Notes |
|--------|------|-------|
| cluster_id | VARCHAR | FK → clusters.id |
| review_id | VARCHAR | FK → reviews.id |

---

### innovation_briefs
Saved Innovation Lab product briefs. One row per generation.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| user_id | VARCHAR | FK → users.id |
| mode | VARCHAR | `competitor` / `innovation` |
| scope | VARCHAR | `all` / `industry` / `datasource` |
| industry | VARCHAR | Nullable — filter used |
| market | VARCHAR | Nullable — market filter (e.g. "de") |
| user_hypothesis | TEXT | Nullable — hypothesis used for guided retrieval |
| product_name | VARCHAR | Generated product name |
| tagline | TEXT | One-line product promise |
| core_problem | TEXT | Problem description with data |
| market_gap | TEXT | Why existing apps don't solve it |
| features | JSONB | Array of `{name, mentions, priority}` |
| target_audience | TEXT | |
| differentiation | TEXT | USP vs. analysed apps |
| risk | TEXT | Primary risk |
| risk_level | VARCHAR | `hoch` / `mittel` / `niedrig` |
| hypothesis_check | TEXT | Nullable — AI evaluation of hypothesis |
| hypothesis_alignment | VARCHAR | Nullable — `stark` / `mittel` / `schwach` |
| total_demand | INTEGER | Sum of FR mentions across top signals |
| apps_analyzed | INTEGER | |
| sources | JSONB | Full signal list used for generation |
| concept_description | TEXT | Nullable — long-form strategic document |
| created_at | TIMESTAMPTZ | |

---

### messages
Customer inbox messages.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| user_id | VARCHAR | FK → users.id |
| customer_name | VARCHAR | |
| customer_email | VARCHAR | |
| subject | VARCHAR | |
| content | TEXT | |
| status | VARCHAR | `new` / `in_progress` / `resolved` |
| priority | VARCHAR | `low` / `medium` / `high` |
| created_at | TIMESTAMPTZ | |

---

### tickets
Kanban board tickets.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| user_id | VARCHAR | FK → users.id |
| title | VARCHAR | |
| description | TEXT | |
| status | VARCHAR | `backlog` / `todo` / `in_progress` / `done` |
| priority | VARCHAR | `low` / `medium` / `high` |
| assignee | VARCHAR | Nullable |
| created_at | TIMESTAMPTZ | |

---

### pipeline_jobs
Tracks background pipeline execution.

| Column | Type | Notes |
|--------|------|-------|
| id | VARCHAR (UUID) | Primary key |
| user_id | VARCHAR | FK → users.id |
| datasource_id | VARCHAR | FK → datasources.id |
| celery_task_id | VARCHAR | |
| status | VARCHAR | `pending` / `running` / `done` / `failed` |
| progress | INTEGER | 0–100 |
| error_message | TEXT | Nullable |
| created_at | TIMESTAMPTZ | |

---

## Migration History

| Migration | Description |
|-----------|-------------|
| `230a0afefba4` | Initial schema — users, datasources, reviews, clusters |
| `df8eba836231` | RAG foundation — pgvector extension, embeddings column |
| `a3f1c8d9e201` | Hybrid search — tsvector column + GIN index |
| `b1c2d3e4f5a6` | ABSA pipeline — review_sentences, review_aspects tables |
| `61cbb76c0196` | Add external_id to reviews (dedup) |
| `h4i5j6k7l8m9` | Add industry to datasources |
| `i5j6k7l8m9n0` | Add feature_request_narrative to feature_narratives |
| `j6k7l8m9n0o1` | Add innovation_briefs table |
| `a1b2c3d4e5f6` | Intelligence tables — documents, chunks, metrics |
| `k7l8m9n0o1p2` | Add concept_description to innovation_briefs |
| `2329cfa66168` | Performance indexes |

---

## Design Decisions

**UUID primary keys:** All tables use string UUIDs. Avoids sequential ID leakage, safe for client-side ID pre-generation, works in distributed setups.

**Denormalised datasource_id in child tables:** `review_signals`, `review_sentences` carry `datasource_id` even though it can be derived via `review_id → reviews → datasource_id`. This enables single-join queries in the hot path (signal aggregation) instead of two-level joins.

**JSONB for variable structures:** `features`, `sources`, `example_reviews` are JSONB columns. They contain arrays of objects whose schema evolved over time. Using proper columns would have required many migrations; JSONB allows schema evolution at the application layer.

**pgvector for all semantic similarity:** Rather than a separate vector database (Pinecone, Weaviate, Qdrant), pgvector keeps vectors inside PostgreSQL. This simplifies operations (one database), enables SQL joins between vectors and structured data (e.g., filter by datasource_id then rank by distance), and is sufficient for the current data volume.
