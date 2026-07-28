# Product Requirements — MA Analytics

> *"Requirements are not what customers ask for. Requirements are what customers need in order to accomplish what they're trying to do."*

---

## 1. Document Purpose

This document defines the complete functional and non-functional requirements for MA Analytics. It serves as the authoritative source of truth for what the system must do, why it must do it, and how well it must do it.

Every requirement is tagged with:
- **Priority:** P0 (must-have), P1 (important), P2 (nice-to-have)
- **Status:** ✅ Implemented | 🔄 In Progress | ⬜ Planned

---

## 2. User Roles

### Role: Product Manager (Primary)
**Goal:** Understand what customers want, generate data-backed product briefs, prioritize the roadmap.  
**Frequency:** Weekly Innovation Lab usage, daily Kanban management.  
**Success metric:** Time from "question" to "evidence-backed product brief" under 5 minutes.

### Role: Founder / Solo Operator (Secondary)
**Goal:** Stay close to customer sentiment, identify product opportunities, validate hypotheses.  
**Frequency:** 2-3x per week.  
**Success metric:** Weekly feedback + innovation review takes <30 minutes.

### Role: Customer Success Manager (Tertiary)
**Goal:** Respond to customer messages quickly and escalate systemic issues.  
**Frequency:** Daily Inbox usage.  
**Success metric:** Reply time reduced from 2 hours to 10 minutes.

---

## 3. Functional Requirements

### 3.1 Authentication & Account Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| AUTH-01 | User can register with email + password | P0 | ✅ |
| AUTH-02 | Password minimum 8 characters, enforced server-side | P0 | ✅ |
| AUTH-03 | User can log in and receive JWT as HTTP-only cookie | P0 | ✅ |
| AUTH-04 | Access token expires after 15 minutes | P0 | ✅ |
| AUTH-05 | Refresh token (7 days) enables token refresh without re-login | P0 | ✅ |
| AUTH-06 | `POST /auth/refresh` — frontend calls automatically on 401 | P0 | ✅ |
| AUTH-07 | Login/Register use separate axios instance (no redirect-loop interceptors) | P0 | ✅ |
| AUTH-08 | All protected routes require valid token | P0 | ✅ |
| AUTH-09 | User can view their profile (`GET /auth/me`) | P0 | ✅ |
| AUTH-10 | Password reset via email (Resend API) | P1 | ✅ |
| AUTH-11 | User can delete their account (GDPR Art. 17) | P1 | ⬜ |
| AUTH-12 | OAuth login (Google) | P2 | ⬜ |
| AUTH-13 | Multi-user team workspace with role-based access | P1 | ⬜ |

---

### 3.2 Data Sources

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DS-01 | User can connect a Google Play app by App ID or full URL | P0 | ✅ |
| DS-02 | System extracts App ID from Play Store URLs automatically | P0 | ✅ |
| DS-03 | User can configure review count (50–2000) | P0 | ✅ |
| DS-04 | User can configure language and country for scraping | P0 | ✅ |
| DS-05 | User can upload a CSV file with review data | P0 | ✅ |
| DS-06 | CSV upload supports configurable column mapping | P0 | ✅ |
| DS-07 | User can view all data sources with StatusBadge | P0 | ✅ |
| DS-08 | User can delete a data source (cascade deletes all associated data) | P0 | ✅ |
| DS-09 | Data source shows review count and created_at | P0 | ✅ |
| DS-10 | Apple App Store support | P1 | ⬜ |
| DS-11 | Trustpilot / G2 integration | P2 | ⬜ |
| DS-12 | Webhook integration for real-time review ingestion | P2 | ⬜ |

---

### 3.3 ML Pipeline

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PIPE-01 | Pipeline runs as background Celery task (non-blocking) | P0 | ✅ |
| PIPE-02 | Job status is trackable: pending → running → done / failed | P0 | ✅ |
| PIPE-03 | Frontend polls job status every 4 seconds while running | P0 | ✅ |
| PIPE-04 | Language detection (langdetect) — filter to DE + EN | P0 | ✅ |
| PIPE-05 | Sentence segmentation into `review_sentences` | P0 | ✅ |
| PIPE-06 | ABSA: Aspect-Based Sentiment Analysis (fast_lcf_atepc multilingual) | P0 | ✅ |
| PIPE-07 | Sentiment derived from star rating (1-2=neg, 4-5=pos) | P0 | ✅ |
| PIPE-08 | Sentence embeddings (paraphrase-multilingual-MiniLM-L12-v2, 384 dims) | P0 | ✅ |
| PIPE-09 | Embeddings stored as `vector(384)` in PostgreSQL via pgvector | P0 | ✅ |
| PIPE-10 | Full-text tsvector stored for hybrid search | P0 | ✅ |
| PIPE-11 | Signal extraction: feature label + signal_type + severity (0–5) | P0 | ✅ |
| PIPE-12 | 25 predefined feature categories (Updates, Bluetooth, Navigation, etc.) | P0 | ✅ |
| PIPE-13 | KMeans clustering on review embeddings → clusters table | P0 | ✅ |
| PIPE-14 | Feature narratives generated per datasource + feature | P0 | ✅ |
| PIPE-15 | Pipeline failure: error stored in job record, surfaced to user | P0 | ✅ |
| PIPE-16 | On macOS: Celery runs with `-P solo` (PyTorch fork restriction) | P0 | ✅ |
| PIPE-17 | Incremental scraping (only new reviews since last_synced) | P1 | ⬜ |

---

### 3.4 Dashboard

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DASH-01 | KPI: total review count | P0 | ✅ |
| DASH-02 | KPI: average star rating | P0 | ✅ |
| DASH-03 | KPI: % positive reviews | P0 | ✅ |
| DASH-04 | KPI: % negative reviews | P0 | ✅ |
| DASH-05 | Sentiment distribution bar (visual breakdown, proportional widths) | P0 | ✅ |
| DASH-06 | Top issues list (sorted by mention count, expandable cluster cards) | P0 | ✅ |
| DASH-07 | Top strengths list (expandable) | P0 | ✅ |
| DASH-08 | Each cluster card: label, mention count, 3 example quotes | P0 | ✅ |
| DASH-09 | AI narrative paragraph | P0 | ✅ |
| DASH-10 | DataSource selector dropdown | P0 | ✅ |
| DASH-11 | Empty state with CTA to connect data source | P0 | ✅ |
| DASH-12 | Sentiment trend over time (line chart) | P1 | ⬜ |
| DASH-13 | Version comparison (compare review periods) | P1 | ⬜ |
| DASH-14 | Competitor benchmarking (cross-datasource) | P2 | ⬜ |

---

### 3.5 Innovation Lab

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| INN-01 | User can select generation mode: "Wettbewerb" or "Innovation" | P0 | ✅ |
| INN-02 | User can select scope: "Alle" / "Industrie" / "Datasource" | P0 | ✅ |
| INN-03 | System aggregates review_signals across selected scope | P0 | ✅ |
| INN-04 | System generates structured brief as JSON via Claude Haiku | P0 | ✅ |
| INN-05 | Brief fields: product_name, tagline, core_problem, market_gap, features, target_audience, differentiation, risk, risk_level | P0 | ✅ |
| INN-06 | Brief is automatically saved to innovation_briefs table | P0 | ✅ |
| INN-07 | Brief history panel shows all saved briefs for the user | P0 | ✅ |
| INN-08 | User can delete a saved brief | P0 | ✅ |
| INN-09 | Groq cascade fallback when Claude is unavailable | P0 | ✅ |
| INN-10 | AI temperature 0.6 for brief JSON generation | P0 | ✅ |
| INN-11 | Previous product names injected into prompt to prevent repetition | P0 | ✅ |
| INN-12 | User can enter a hypothesis text (optional) | P0 | ✅ |
| INN-13 | Hypothesis is embedded (MiniLM) and used for pgvector cosine search | P0 | ✅ |
| INN-14 | Hypothesis-guided mode: top 500 semantically similar reviews form the signal pool | P0 | ✅ |
| INN-15 | Brief includes hypothesis_check and hypothesis_alignment fields when hypothesis is used | P0 | ✅ |
| INN-16 | Signal co-occurrence graph computed on-demand (self-join on review_signals) | P0 | ✅ |
| INN-17 | Hub signals (>20% total co-occurrence weight) marked with ⚠ in prompt | P0 | ✅ |
| INN-18 | Signal graph injected into prompt as strategic instruction | P0 | ✅ |
| INN-19 | Automatic signal exclusion: top-3 signals from last 10 briefs excluded by default | P0 | ✅ |
| INN-20 | Manual signal exclusion via Signal-Steuerung panel takes precedence over auto | P0 | ✅ |
| INN-21 | `excluded_signals=null` → auto-exclude; `excluded_signals=[]` → no exclusion; `excluded_signals=[...]` → manual list | P0 | ✅ |
| INN-22 | Exclusion fallback: if <5 signals remain after exclusion, re-run without exclusion | P0 | ✅ |
| INN-23 | `POST /innovation/signals` endpoint returns all available signal clusters for given scope | P0 | ✅ |
| INN-24 | Signal-Steuerung panel: collapsible, shows signal chips with mention counts | P0 | ✅ |
| INN-25 | Signal chips colored by type: violet (FR-dominant), red (bug-dominant), indigo (general) | P0 | ✅ |
| INN-26 | Exclusion badge: "auto" (gray) / "X aus" (amber) / "alle aktiv" (green) | P0 | ✅ |
| INN-27 | `userControlledSignals` boolean: reset to false on scope/filter change | P0 | ✅ |
| INN-28 | User can generate long-form concept description for any saved brief | P0 | ✅ |
| INN-29 | Concept description: ~1200+ words, 9 structured sections | P0 | ✅ |
| INN-30 | "Konzept neu generieren" allows regeneration of existing concept | P0 | ✅ |
| INN-31 | User can export brief as PDF (client-side, jsPDF) | P0 | ✅ |
| INN-32 | PDF includes: header, hypothesis validation, signal analysis, feature table, risk block, concept excerpt, data sources table, page footers | P0 | ✅ |
| INN-33 | Brief Copilot: conversational Q&A about a saved brief (POST /innovation/briefs/{id}/chat) | P0 | ✅ |
| INN-34 | Copilot maintains full conversation history in frontend state | P0 | ✅ |
| INN-35 | Review enrichment per signal: scaled by rank (1–3: 20 reviews, 4–8: 12, 9–15: 8, 16+: 4) | P0 | ✅ |
| INN-36 | Review deduplication: first 60 chars compared, pool 5× target size | P0 | ✅ |

---

### 3.6 Hybrid Search

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SEARCH-01 | User can search reviews by text query | P0 | ✅ |
| SEARCH-02 | Hybrid mode: RRF fusion of vector + fulltext results | P0 | ✅ |
| SEARCH-03 | Vector mode: cosine similarity via pgvector | P0 | ✅ |
| SEARCH-04 | Fulltext mode: BM25 via `ts_rank_cd` + `websearch_to_tsquery` | P0 | ✅ |
| SEARCH-05 | Filter by datasource_ids (specific apps) | P0 | ✅ |
| SEARCH-06 | Filter by star rating range (1.0–5.0) | P0 | ✅ |
| SEARCH-07 | Filter by language | P0 | ✅ |
| SEARCH-08 | Results include: review text, similarity score, app source, sentiment, date | P0 | ✅ |
| SEARCH-09 | Maximum 100 results per query | P0 | ✅ |
| SEARCH-10 | Semantic search over document chunks (document intelligence) | P0 | ✅ |

---

### 3.7 Document Intelligence

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DOC-01 | User can upload PDF documents | P0 | ✅ |
| DOC-02 | PDF text extraction per page | P0 | ✅ |
| DOC-03 | Chunking with page overlap | P0 | ✅ |
| DOC-04 | Chunk embedding (same MiniLM model as reviews — ensures cross-source similarity) | P0 | ✅ |
| DOC-05 | Document list view with metadata (title, type, year, page count) | P0 | ✅ |
| DOC-06 | User can ask questions over indexed documents | P0 | ✅ |
| DOC-07 | Answer includes source citations (document title + page number) | P0 | ✅ |
| DOC-08 | Batch metric extraction (Scope 1/2/3, reduction targets, obligations) | P0 | ✅ |
| DOC-09 | User can delete indexed documents | P0 | ✅ |

---

### 3.8 Customer Inbox

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| INBOX-01 | User can view all customer messages in a list | P0 | ✅ |
| INBOX-02 | Message list: name, sentiment badge, text preview, date | P0 | ✅ |
| INBOX-03 | User can create a new message | P0 | ✅ |
| INBOX-04 | User can generate an AI reply (Claude/Groq) | P0 | ✅ |
| INBOX-05 | User can generate Kanban tickets from a message | P0 | ✅ |
| INBOX-06 | Generated tickets appear immediately in Kanban Board | P0 | ✅ |
| INBOX-07 | Send reply via Resend API | P1 | ⬜ |
| INBOX-08 | Filter messages by sentiment | P1 | ⬜ |

---

### 3.9 Kanban Board

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| KAN-01 | Four columns: Backlog, Todo, In Progress, Done | P0 | ✅ |
| KAN-02 | Each column shows ticket count | P0 | ✅ |
| KAN-03 | Ticket card shows: title, priority badge | P0 | ✅ |
| KAN-04 | User can create a new ticket from Backlog column | P0 | ✅ |
| KAN-05 | User can click ticket to open detail panel | P0 | ✅ |
| KAN-06 | Detail panel: edit title, description, status, priority | P0 | ✅ |
| KAN-07 | Status change moves ticket to appropriate column immediately | P0 | ✅ |
| KAN-08 | User can delete a ticket with confirmation dialog | P0 | ✅ |
| KAN-09 | Drag-and-drop between columns | P1 | ⬜ |
| KAN-10 | Jira / Linear export | P2 | ⬜ |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| PERF-01 | API response time (p95) for read endpoints | < 200ms |
| PERF-02 | API response time (p95) for write endpoints | < 500ms |
| PERF-03 | Innovation Brief generation (Claude Haiku) | < 15 seconds |
| PERF-04 | Hybrid search results | < 500ms |
| PERF-05 | ML pipeline completion (200 reviews) | < 3 minutes |
| PERF-06 | ML pipeline completion (2000 reviews) | < 15 minutes |
| PERF-07 | pgvector cosine search (hypothesis retrieval, 32K vectors) | < 300ms |

### 4.2 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| REL-01 | API uptime | ≥ 99.5% |
| REL-02 | Pipeline job failure rate | < 2% |
| REL-03 | Failed pipeline jobs surface error message to user | 100% |
| REL-04 | AI generation: Groq fallback cascade if Claude unavailable | 100% |
| REL-05 | Signal exclusion fallback when <5 signals remain | 100% |
| REL-06 | Database backup | Daily, 7-day retention |

### 4.3 Security

| ID | Requirement | Target |
|----|-------------|--------|
| SEC-01 | All endpoints require authentication (except /health, /auth/*) | 100% |
| SEC-02 | Users can only access their own data (user_id filter on every query) | 100% |
| SEC-03 | Passwords hashed with bcrypt (cost factor 12) | 100% |
| SEC-04 | JWT tokens signed with HS256, 15-minute access token | 100% |
| SEC-05 | Tokens stored as HTTP-only cookies (not localStorage) | 100% |
| SEC-06 | Rate limiting on auth endpoints: 10/min register, 20/min login | 100% |
| SEC-07 | API docs hidden in production (DEBUG=false) | 100% |
| SEC-08 | CORS restricted to configured origins (never "*" in production) | 100% |
| SEC-09 | All SQL via SQLAlchemy parameterized queries (no string interpolation) | 100% |
| SEC-10 | Secrets loaded from environment variables, never hardcoded | 100% |

### 4.4 Usability

| ID | Requirement | Target |
|----|-------------|--------|
| UX-01 | New user can connect first data source in < 3 minutes | 95% of users |
| UX-02 | First Innovation Brief generated within 5 minutes of data load | 90% of users |
| UX-03 | All async actions have loading states (no silent waiting) | 100% |
| UX-04 | All destructive actions require confirmation with named resource | 100% |
| UX-05 | Empty states provide actionable next step | 100% |
| UX-06 | Signal exclusion badge always shows current exclusion mode | 100% |

### 4.5 Scalability

| ID | Requirement | Target |
|----|-------------|--------|
| SCALE-01 | System handles 100 concurrent users | Phase 1 |
| SCALE-02 | Database supports 10M reviews total | Phase 2 |
| SCALE-03 | pgvector index handles 1M embeddings with <500ms search | Phase 2 |
| SCALE-04 | Celery worker pool scales horizontally | Phase 2 |

---

## 5. Constraints

**Technical:**
- Backend must run on Python 3.9 (PyTorch + sentence-transformers compatibility)
- ML models must run locally (no external API calls for inference)
- pgvector 0.3+ required for `<=>` cosine operator
- Google Play scraping subject to Google's rate limiting

**Business:**
- MVP deployable by a single developer
- Infrastructure cost under €200/month at 100 customers
- AI generation costs must be bounded (brief generation is the only variable LLM cost)

**Legal:**
- Google Play reviews are public data — scraping is legally permissible
- No PII stored beyond what the user explicitly provides
- GDPR compliance: account deletion endpoint required (P1)

---

## 6. Acceptance Criteria (v1.0 Current State)

All P0 requirements above are implemented. The system is production-capable with:

- ✅ New user can register, connect a Google Play app, and see clustered insights in under 10 minutes
- ✅ Innovation Lab generates diverse, evidence-backed briefs in under 15 seconds
- ✅ Hypothesis-guided RAG retrieval produces hypothesis-specific signal aggregation
- ✅ Signal graph identifies hub vs. edge signals and injects strategic guidance into prompts
- ✅ Signal exclusion (auto + manual) prevents concept repetition across generations
- ✅ Brief Copilot enables conversational exploration of generated briefs
- ✅ PDF export generates formatted A4 documents client-side
- ✅ Document Intelligence indexes PDFs and answers semantic questions with source citations
- ✅ Hybrid search (RRF fusion) over 33,649 reviews with <500ms response time

---

*Document Owner: Product Management*  
*Last Updated: 2026-07*  
*Status: v1.0 — All P0 requirements implemented*
