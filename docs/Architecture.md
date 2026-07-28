# Architecture — MA Analytics

## 1. System Overview

MA Analytics is a multi-tier, event-driven SaaS application with three distinct intelligence layers: review signal extraction, innovation brief generation, and document RAG. Each layer is architecturally independent but shares the same persistence and embedding infrastructure.

```
┌────────────────────────────────────────────────────────────────┐
│                         PRESENTATION                            │
│              React 18 + TypeScript + Vite (port 3002)          │
│   Dashboard · DataSources · InnovationLab · Search · Inbox     │
└──────────────────────────┬─────────────────────────────────────┘
                           │ HTTP/REST (JSON)
┌──────────────────────────▼─────────────────────────────────────┐
│                        APPLICATION                               │
│                 FastAPI 0.115 (port 8000)                       │
│  auth · datasources · innovation · intelligence · search ·      │
│               dashboard · messages · tickets · jobs              │
└────────┬──────────────────────────────────┬────────────────────┘
         │ SQLAlchemy async (asyncpg)        │ Celery .delay()
┌────────▼──────────────┐       ┌───────────▼────────────────────┐
│      PERSISTENCE       │       │          COMPUTATION            │
│   PostgreSQL 16        │       │      Celery Worker             │
│   + pgvector 0.3       │       │  ├── Google Play Scraper       │
│                        │       │  ├── Text preprocessing        │
│  users                 │       │  ├── Sentiment (ABSA)          │
│  datasources           │       │  ├── Embeddings (MiniLM)       │
│  reviews + embeddings  │       │  ├── Signal extraction         │
│  review_signals        │       │  ├── KMeans clustering         │
│  review_sentences      │       │  └── Document chunking + embed │
│  clusters              │       └────────────────────────────────┘
│  innovation_briefs     │
│  feature_narratives    │       ┌────────────────────────────────┐
│  intelligence docs     │       │         AI PROVIDERS           │
│  messages · tickets    │       │  Primary: Claude Haiku         │
└────────────────────────┘       │  (claude-haiku-4-5-20251001)   │
                                 │  Fallback: Groq                │
         ┌───────────────────────│  llama-3.3-70b-versatile       │
         │ Redis (port 6380)     │  llama-3.1-70b-versatile       │
         │ Celery broker + cache │  gemma2-9b-it                  │
         └───────────────────────└────────────────────────────────┘
```

---

## 2. Data Flow — Review Pipeline

The primary data flow transforms raw app store text into structured, queryable signals.

```
Google Play ID or CSV
        │
        ▼
  [Celery Task: run_pipeline]
        │
        ├── 1. Scrape / parse reviews
        │         google-play-scraper → reviews table
        │
        ├── 2. Language detection
        │         langdetect → filter to DE + EN
        │
        ├── 3. Sentence segmentation
        │         → review_sentences table
        │
        ├── 4. Sentiment + aspect extraction
        │         ABSA (fast_lcf_atepc multilingual checkpoint)
        │         → review_aspects table
        │
        ├── 5. Embedding generation
        │         paraphrase-multilingual-MiniLM-L12-v2 (384 dims)
        │         → reviews.embedding (pgvector column)
        │         → reviews.search_vector (tsvector for full-text)
        │
        ├── 6. Signal classification
        │         Feature requests · Bugs · UX · Performance · General
        │         → review_signals table (feature, signal_type, severity 0–5)
        │
        └── 7. KMeans clustering
                  → clusters + cluster_reviews tables
```

Status tracking: `datasources.job_status` ∈ `{pending, running, done, failed}`.
A Celery task ID is stored in `datasources.job_id` for polling via `GET /jobs/{task_id}`.

---

## 3. Innovation Lab Architecture

The Innovation Lab is the primary intelligence output layer. It transforms raw signals into investor-ready product briefs through a multi-step pipeline.

```
POST /innovation/generate
           │
           ├── 1. Build WHERE clause (scope: all / industry / datasource)
           │
           ├── 2. Signal exclusion
           │         IF body.excluded_signals is set → use those (manual UI)
           │         ELSE → auto-exclude top-3 signals from last 10 briefs
           │                (prevents concept repetition across generations)
           │         IF exclusion leaves < 5 signals → fallback: no exclusion
           │
           ├── 3. Signal retrieval — two modes
           │
           │    WITH hypothesis:
           │    ├── Embed hypothesis text (paraphrase-multilingual-MiniLM-L12-v2)
           │    ├── pgvector cosine search → top 500 semantically similar reviews
           │    ├── Aggregate review_signals FROM those 500 reviews only
           │    ├── Order by: avg cosine distance ASC, fr_mentions DESC
           │    └── Enrich each signal with hypothesis-relevant review texts
           │         (sorted by cosine distance to hypothesis, not severity)
           │
           │    WITHOUT hypothesis:
           │    ├── Aggregate all review_signals across full corpus
           │    └── Order by: app_count DESC, fr_mentions DESC, total DESC
           │
           ├── 4. Review enrichment per signal
           │         Rank 1–3:   up to 20 reviews
           │         Rank 4–8:   up to 12 reviews
           │         Rank 9–15:  up to 8 reviews
           │         Rank 16+:   up to 4 reviews
           │         Pool 5× target, deduplicate on first 60 chars
           │
           ├── 5. Signal graph computation
           │         Co-occurrence: signals appearing in the same review
           │         Hub detection: signals with >20% of total co-occurrence weight
           │         Hub = systemic OEM infrastructure problem
           │         Edge = standalone third-party product opportunity
           │
           ├── 6. Prompt construction (_build_prompt)
           │         Part A: compact overview of ALL signal clusters
           │         Part B: deep-dive — top 15 signals with real review texts
           │         Signal graph block: hub vs edge classification
           │         Previous concepts block: "avoid these product names/concepts"
           │         Retrieval mode header: "hypothesis-guided" label if applicable
           │         AUSFÜLLANWEISUNG: field instructions with HIER_ placeholders
           │
           ├── 7. Claude JSON generation (temperature 0.6)
           │         Primary: Claude Haiku via anthropic SDK
           │         On error: Groq cascade (llama-3.3-70b → llama-3.1-70b → gemma2)
           │         Multi-key rotation on 429 rate limit errors
           │         Returns: InnovationBrief JSON (product_name, features, etc.)
           │
           ├── 8. Concept description generation (Claude text, temperature 0.4)
           │         Long-form strategic document ~1200+ words
           │         9 sections: Executive Summary · Market Analysis · Product Vision
           │         · Feature Details · Target Audience · Differentiation
           │         · Risk Assessment · Go-to-Market · Roadmap
           │
           └── 9. Persist to innovation_briefs table
                     RETURNING id → SavedBriefFull returned to client
```

**On-demand concept generation:**
`POST /innovation/briefs/{id}/generate-concept` regenerates the long-form concept for any saved brief.

**Brief Copilot:**
`POST /innovation/briefs/{id}/chat` — conversational Q&A using the brief as context.

**Signal selector endpoint:**
`POST /innovation/signals` — returns all available signal clusters with counts and severity for the given filter scope. Used by the frontend Signal-Steuerung panel.

---

## 4. Signal Graph

The signal graph is computed on-demand from the review_signals table using a self-join co-occurrence query. It does not require a separate graph database.

```sql
-- Co-occurrence: signals appearing in the same review
SELECT a.feature AS sig_a, b.feature AS sig_b,
       COUNT(DISTINCT a.review_id) AS co_count
FROM review_signals a
JOIN review_signals b ON a.review_id = b.review_id AND a.feature < b.feature
WHERE {scope filter}
GROUP BY a.feature, b.feature
HAVING COUNT(DISTINCT a.review_id) >= 10
ORDER BY co_count DESC

-- Hub detection
hub_score[signal] = sum of co_count for all its edges
hub_threshold = total_weight * 0.20
is_hub = hub_score >= hub_threshold
```

**Purpose:** Tells the LLM which signals are infrastructure-level OEM problems (hubs) versus standalone product opportunities (edge nodes). The prompt includes a strategic instruction: "Build the concept on edge signals, not hub signals."

---

## 5. Hybrid Search Architecture

```
POST /search/
      │
      ├── Embed query → 384-dim vector
      │
      ├── Vector branch
      │     cosine similarity via pgvector <=> operator
      │     ROW_NUMBER() OVER (ORDER BY distance ASC)
      │
      ├── Full-text branch
      │     ts_rank_cd(search_vector, websearch_to_tsquery())
      │     ROW_NUMBER() OVER (ORDER BY rank DESC)
      │
      └── RRF fusion
            rrf_score = 1/(60 + rank_vector) + 1/(60 + rank_fulltext)
            ORDER BY rrf_score DESC
```

Search modes: `hybrid` (default), `vector`, `fulltext`.

---

## 6. Document Intelligence Architecture

```
POST /intelligence/upload (PDF)
      ├── Extract text per page
      ├── Chunk with page overlap
      ├── Embed each chunk (MiniLM, same model as reviews)
      └── Store: intelligence_documents + intelligence_chunks tables

POST /intelligence/query
      ├── Embed question
      ├── pgvector cosine search → top K chunks
      ├── Claude: answer from retrieved context
      └── Return answer + source page references

POST /intelligence/extract-all
      └── Batch metric extraction (Scope 1/2/3, reduction targets,
          regulatory obligations) → intelligence_metrics table
```

---

## 7. AI Provider Strategy

**Primary:** Anthropic Claude Haiku (`claude-haiku-4-5-20251001`)
- JSON brief generation: temperature 0.6
- Concept description text: temperature 0.4
- Brief chat: temperature 0.4, max_tokens 1200
- Document Q&A: temperature 0.3

**Fallback cascade** (triggered on any Claude error including rate limits):
```
JSON generation fallback (_groq_json_fallback):
  llama-3.3-70b-versatile (key 1) → llama-3.1-70b-versatile (key 1)
  → gemma2-9b-it (key 1) → llama-3.3-70b-versatile (key 2)
  → llama-3.1-70b-versatile (key 2) → gemma2-9b-it (key 2)
  → HTTP 429 if all exhausted

Text/chat fallback (_groq_text_fallback):
  llama-3.1-8b-instant → llama-3.3-70b-versatile → llama-3.1-70b-versatile
  (per key)
```

Rate limit detection: `_is_rate_limit(exc)` checks for `"429"`, `"rate_limit"`, `"overloaded"` in exception string.

Note: `llama-3.1-8b-instant` is excluded from JSON generation because it copies schema placeholder text literally instead of replacing it with real content.

---

## 8. Authentication

Stateless JWT with HTTP-only cookies.

- `access_token`: 15-minute lifetime, signed with `SECRET_KEY` (HS256)
- `refresh_token`: 7-day lifetime, stored as HTTP-only cookie
- Password hashing: bcrypt via passlib
- Password reset: time-limited token stored in `users.reset_token` + email via Resend

---

## 9. Clean Architecture Principles Applied

| Principle | How |
|-----------|-----|
| No logic in routers | All signal aggregation, prompt building, and AI calls are in helper functions, not route handlers |
| Async-first | All DB operations use `await db.execute()`. No sync DB in request path |
| Dependency injection | `get_db`, `get_current_user` via FastAPI `Depends()` |
| Migration-driven schema | Alembic handles all schema changes — no `create_all()` in production |
| Single embedding model | All vectors (reviews, documents, hypotheses) use the same 384-dim model — ensures meaningful cosine similarity across search types |
| AI provider isolation | `_call_claude_json`, `_call_claude_text` are pure functions — swapping providers means only changing these functions |
