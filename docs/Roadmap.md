# Product Roadmap — MA Analytics

> *"A roadmap is a statement of intent, not a promise. Its value is not in the dates — it is in the thinking: what matters most, in what order, and why. A roadmap that everyone ignores is decoration. A roadmap that drives weekly decisions is strategy."*

---

## 1. Strategic Context

### Where We Are (July 2026)

MA Analytics has completed a full-stack build with significantly more capability than a typical MVP. The system is production-capable today with the following modules fully implemented:

**Core Data Pipeline:** Google Play scraping + CSV import → ABSA sentiment extraction → multilingual embeddings → signal classification → KMeans clustering. Processing 33,649 reviews from 5 automotive apps (BMW, Mercedes-Benz, Audi, Volkswagen, Porsche) with 41,620 extracted signals across 25 feature categories.

**Intelligence Layer (Innovation Lab):** The primary output module.
- Hypothesis-Guided RAG: embed hypothesis → pgvector search over 32,300 reviews → aggregate signals from semantic matches
- Signal Graph: co-occurrence analysis identifies OEM infrastructure problems (hubs) vs. product opportunities (edge signals)
- Signal Exclusion: automatic (last 10 briefs) + manual (Signal-Steuerung panel) to prevent concept repetition
- Multi-provider AI: Claude Haiku primary (temperature 0.6), Groq cascade fallback (llama-3.3-70b → llama-3.1-70b → gemma2)
- Brief persistence, Copilot chat, long-form concept documents, PDF export

**Supporting Modules:** Hybrid search (RRF fusion), Document Intelligence (PDF RAG, metric extraction), Customer Inbox (AI reply), Kanban Board, Dashboard with KPIs.

### What's Genuinely Not Built Yet

The current gaps are in three categories:
1. **Platform hardening** — features needed before real customer onboarding (password reset, account deletion, email send)
2. **Data breadth** — expanding beyond Google Play (Apple App Store, other sources)
3. **Intelligence depth** — making the Innovation Lab's output more accurate and diverse (finer signal taxonomy, cross-source linking)

---

## 2. Current State: v1.0 (Completed July 2026)

### What's Built

| Area | Status | Notes |
|------|--------|-------|
| Auth (register, login, JWT HTTP-only cookies, refresh) | ✅ Done | bcrypt, 15min access + 7d refresh, rate limiting |
| Google Play data source | ✅ Done | Scraping + full ML pipeline |
| CSV upload | ✅ Done | Configurable column mapping |
| Async pipeline (Celery) | ✅ Done | 7-stage with progress tracking |
| ABSA sentiment analysis | ✅ Done | fast_lcf_atepc multilingual checkpoint |
| Multilingual embeddings | ✅ Done | paraphrase-multilingual-MiniLM-L12-v2 (384 dims) |
| pgvector semantic search | ✅ Done | IVFFlat index, cosine distance operator |
| Full-text hybrid search | ✅ Done | tsvector GIN index, RRF fusion |
| Signal extraction | ✅ Done | 25 feature labels, 6 signal types, severity 0–5 |
| KMeans clustering | ✅ Done | Auto k, cluster labels and narratives |
| Dashboard + KPIs | ✅ Done | 4 KPIs, sentiment bar, cluster cards, AI narrative |
| Innovation Lab — core | ✅ Done | Mode, scope, signal aggregation, Claude brief |
| Hypothesis-Guided RAG | ✅ Done | Embed → vector search → signal aggregation from subset |
| Signal Graph | ✅ Done | Co-occurrence SQL, hub detection, prompt injection |
| Signal Exclusion (auto) | ✅ Done | Top-3 signals from last 10 briefs |
| Signal-Steuerung Panel (manual) | ✅ Done | Signal chips, Alle/Keine, exclusion badge |
| Brief persistence + history | ✅ Done | innovation_briefs table, list + delete |
| Concept document generation | ✅ Done | ~1200+ words, 9 sections, Claude temperature 0.4 |
| Brief Copilot chat | ✅ Done | POST /innovation/briefs/{id}/chat |
| PDF Export | ✅ Done | Client-side jsPDF, A4, multi-page |
| Document Intelligence | ✅ Done | PDF upload, chunking, embedding, RAG Q&A |
| Metric extraction | ✅ Done | Scope 1/2/3, reduction targets, regulatory obligations |
| Customer Inbox | ✅ Done | Messages, AI reply, ticket generation |
| Kanban Board | ✅ Done | 4 columns, ticket CRUD, priority |
| Structured logging | ✅ Done | structlog JSON, X-Request-ID |
| Rate limiting | ✅ Done | slowapi, per-endpoint limits |
| Docker Compose (PostgreSQL + Redis) | ✅ Done | Port 5434, 6380 |
| ESLint + TypeScript strict | ✅ Done | All frontend errors resolved |

### Known Gaps

| Gap | Impact | Target Phase |
|-----|--------|------|
| Account deletion (`DELETE /auth/me`) | GDPR blocker for EU customers | Phase 1.5 |
| Send email reply (Resend API in Inbox) | Inbox is read-only without it | Phase 1.5 |
| Incremental scraping (delta only) | Full re-scrape is slow and wastes quota | Phase 1.5 |
| Drag-and-drop Kanban | UX improvement, not blocking | Phase 2 |
| Apple App Store integration | Doubles addressable data sources | Phase 2 |
| Sentiment trend over time | Dashboard depth | Phase 2 |
| Sub-signal taxonomy (25 → 125 labels) | Reduces concept clustering around dominant labels | Phase 2 |
| Cross-source intelligence (reviews × docs) | High-value cross-referencing capability | Phase 2 |
| Multi-user team workspaces | Enterprise sales blocker | Phase 3 |
| SSO / SAML | Enterprise security requirement | Phase 3 |
| API access (scoped keys) | Agency and integration use cases | Phase 3 |

---

## 3. Phase 1.5 — Production Hardening (Month 1–2)

**Goal:** Get the product to a state where real paying customers can use it daily without friction.  
**Success criteria:** 3 customers using product weekly for 4+ consecutive weeks.

### P0: Must-Have for First Paying Customer

**Account Deletion (GDPR Art. 17)**
- `DELETE /auth/me` → cascade deletes user, datasources, reviews, signals, briefs, messages, tickets
- Confirmation email before deletion (Resend)
- Effort: 1 day

**Email Reply (Resend API)**
- "Antwort senden" button in Inbox → `POST /messages/{id}/send-reply`
- Resend API delivers email to customer_email
- Reply preview already exists in UI; add Send button
- Effort: 1 day

**Pipeline Retry UI**
- Failed pipeline shows "Erneut versuchen" button in /datasources
- Effort: 0.5 days

### P1: Quality of Life

**Incremental Scraping**
- Track `last_synced` per datasource
- On re-sync: only fetch reviews newer than `last_synced`
- Dedup via `external_id` (already stored)
- Effort: 2 days

**Message Filtering**
- Filter Inbox by sentiment: `/inbox?sentiment=negative`
- Frontend dropdown
- Effort: 1 day

**Performance Audit**
- Measure all endpoints with k6; ensure p95 <200ms for reads
- Add missing composite indexes (user_id + created_at for ordered queries)
- Effort: 1 day

---

## 4. Phase 2 — Breadth + Intelligence Depth (Month 2–5)

**Goal:** Retain customers by deepening value and expanding data sources.  
**Target:** 10 paying customers, €2,000 MRR.

### Sub-Signal Taxonomy

The current 25 feature labels are too broad. "Updates" covers OTA failures, UI changes after update, data loss on update, and slow downloads — four different product opportunities, all collapsed into one label.

**Plan:**
- Re-classify signals into 100–150 sub-labels under the existing 25 top-level labels
- Run `extract-all` re-extraction after taxonomy expansion
- Re-cluster with new granular labels
- Update Signal-Steuerung panel to show hierarchical chips (collapse/expand top-level)
- Expected impact: significantly more diverse brief concepts; "Updates" stops dominating every generation

Effort: 5 days (taxonomy design + re-extraction + UI update)

### Cross-Source Intelligence

The two existing intelligence layers (review signals + document RAG) are currently completely separate. Linking them would produce insights unavailable from either layer alone:

- "Users report data deletion after app updates" + "GDPR Article 17 mandates right to erasure" → regulatory-driven product opportunity
- "BMW app users complain about Scope 3 data unavailability" + "CSDDD requires Scope 3 disclosure" → compliance gap → product

**Plan:**
- Add `POST /intelligence/cross-query` endpoint
- Embed review signal summaries → find relevant regulatory chunks via pgvector
- Inject cross-source context into Innovation Brief prompt
- Effort: 5 days

### Apple App Store Integration

- Library: `apple-appstore-scraper` (Python)
- Same pipeline, new scraper adapter
- UI: "Apple App Store" option in datasource form
- Effort: 3 days

### Dashboard Depth

**Sentiment Trend Chart**
- Line chart: avg sentiment by week, using `reviewed_at`
- Frontend: recharts library
- Effort: 3 days

**Version Comparison**
- Side-by-side cluster view for two time ranges
- "v3.2.1 introduced Login issue that wasn't present in v3.2.0"
- Effort: 4 days

### Kanban Improvements

**Drag-and-Drop**
- `@dnd-kit/core` for React DnD
- Drop ticket on column → `PATCH /tickets/{id}` with new status
- Effort: 2 days

---

## 5. Phase 3 — Team & Enterprise (Month 5–10)

**Goal:** Land first enterprise deal.  
**Target:** €10,000 MRR, 1 enterprise account.

### Multi-User Team Workspaces

- New `Workspace` entity: container for datasources, briefs, tickets, messages
- Users can be members of multiple workspaces
- Roles: Owner, Admin, Member, Viewer
- Team invitation via email
- Data model change: all resources get `workspace_id` FK
- Effort: 10 days

### Enterprise Security

**SSO / SAML**
- Okta, Azure AD, Google Workspace
- Required for enterprise procurement
- Effort: 5 days + vendor setup

**2FA (TOTP)**
- TOTP via Google Authenticator / Authy
- Effort: 2 days

**Audit Log**
- Append-only: user_id, action, resource, timestamp
- Export as CSV for compliance
- Effort: 3 days

### API Access

- Scoped API keys per workspace
- Rate-limited separately from web UI
- Enables agency use cases (build own UI on top of MA Analytics data)
- Effort: 3 days

### Integration Marketplace

- Jira: export ticket with Jira issue creation
- Slack: weekly digest notification
- Linear: export ticket
- Effort: 2 days each

---

## 6. Phase 4 — Platform & Scale (Month 9–18)

**Goal:** €50,000 MRR, 100+ customers.

### Infrastructure

**Managed PostgreSQL Migration**
- Move from Docker to Neon or Supabase
- Point-in-time recovery, read replicas, PgBouncer connection pooling
- Zero-downtime via logical replication

**Horizontal Celery Scaling**
- Switch from `-P solo` to `prefork` with KEDA autoscaling
- Scale workers based on Redis queue depth

**CDN for Frontend**
- Move React build to Cloudflare Pages
- Backend API stays on server

**Monitoring Stack**
- Prometheus + Grafana: pipeline throughput, brief generation latency, queue depth
- Sentry: error tracking
- Uptime monitoring: BetterUptime

### Product Intelligence

**Real-Time Monitoring**
- Weekly re-scrape + delta analysis
- Alert when a signal cluster suddenly increases in severity (spike detection)
- "BMW Login issue severity increased 40% this week"

**Validation Loop**
- Track which briefs the user acted on (exported, shared, saved to Jira)
- Use those signals to improve generation: which signal combinations lead to actionable outputs

**Competitive Intelligence Layer**
- Index OEM job postings, patent filings, app changelog notes (via scraping)
- A signal with active OEM hiring behind it = not a third-party opportunity
- A signal with zero OEM investment = high opportunity

---

## 7. KPI Targets by Phase

| Metric | v1.0 Now | Phase 1.5 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|-----------|---------|---------|---------|
| Paying customers | 0 | 3 | 15 | 50 | 150+ |
| MRR | €0 | €500 | €3,000 | €12,000 | €60,000+ |
| Briefs generated/month | ~20 (internal) | 100 | 500 | 3,000 | 15,000+ |
| Pipeline success rate | >95% | >98% | >99% | >99.5% | >99.9% |
| Brief generation latency | <15s | <15s | <12s | <10s | <8s |
| Distinct concepts per 10 briefs | 6 | 8 | 9 | 10 | 10 |

---

## 8. Prioritization Framework

Features are prioritized using the **RICE framework**:

```
Score = (Reach × Impact × Confidence) / Effort
```

**Example — Sub-Signal Taxonomy:**
- Reach: 10 (every Innovation Lab user benefits)
- Impact: 3 (directly increases brief diversity — the core quality metric)
- Confidence: 80% (we've verified that "Updates" dominates all briefs)
- Effort: 1 week
- **Score: (10 × 3 × 0.8) / 1 = 24 — high priority**

**Example — Drag-and-Drop Kanban:**
- Reach: 8 (all Kanban users)
- Impact: 0.5 (nice-to-have, current UI works)
- Confidence: 100%
- Effort: 0.5 weeks
- **Score: (8 × 0.5 × 1.0) / 0.5 = 8 — medium priority**

---

## 9. What We Won't Build

| Feature | Why Not |
|---------|---------|
| Mobile app | Desktop tool for professionals; mobile adds cost without addressing core PM pain |
| Self-hosted enterprise (air-gapped) | Engineering overhead too high for one team at this stage |
| Real-time streaming analytics | Batch analysis (hourly/daily) is sufficient; latency isn't the bottleneck |
| Custom ML model fine-tuning | Pre-trained MiniLM/ABSA are sufficient; custom training needs 10x more data |
| Social media monitoring (Twitter/X) | Different buyer persona, different workflow — separate product |
| Survey creation | Not the job to be done; SurveyMonkey does this well |
| Mobile SDK / in-app feedback collection | Different surface area; out of scope for B2B analytics tool |

---

*Document Owner: Product Strategy*  
*Last Updated: 2026-07*  
*Status: v1.0 Complete — Phase 1.5 is the next milestone*
