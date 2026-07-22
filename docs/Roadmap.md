# Product Roadmap — MA Analytics

> *"A roadmap is a statement of intent, not a promise. Its value is not in the dates — it is in the thinking: what matters most, in what order, and why. A roadmap that everyone ignores is decoration. A roadmap that drives weekly decisions is strategy."*

---

## 1. Strategic Context

### Where We Are

MA Analytics has completed a full MVP build (Phase 1–7). The system is production-capable today:

- Google Play scraping + ML pipeline (sentiment → embeddings → clustering)
- Dashboard with clustered insights, KPI summary, AI narrative
- Customer Inbox with AI reply and ticket generation
- Kanban board for issue tracking
- Authentication, rate limiting, structured logging, Docker deployment

**v1.0 is the product. Everything below is the business.**

### Where We're Going

The immediate opportunity is **product-market fit validation**: get 10 paying customers using the product weekly, measure their behavior, and build exactly what they need next — nothing else.

The medium-term opportunity is **the integration layer**: the moment MA Analytics connects to real data sources in real time (Apple App Store, Zapier, email), it transforms from a batch analysis tool into a live customer intelligence platform.

The long-term opportunity is **the intelligence layer**: when enough customers have enough data, MA Analytics becomes the industry benchmark — not just "what are MY customers saying" but "how does my customer sentiment compare to competitors in my category?"

---

## 2. Current State: v1.0 (Completed)

### What's Built

| Area | Status | Notes |
|------|--------|-------|
| Auth (register, login, JWT) | ✅ Done | bcrypt, 24h tokens, rate limiting |
| Google Play data source | ✅ Done | Scraping + full ML pipeline |
| CSV upload | ✅ Done | Configurable column mapping |
| Async pipeline (Celery) | ✅ Done | 5-stage with progress tracking |
| Sentiment analysis | ✅ Done | Star rating primary, RoBERTa fallback |
| Semantic clustering | ✅ Done | Embeddings + KMeans → issues + strengths |
| Dashboard + KPIs | ✅ Done | 4 KPIs, sentiment bar, cluster cards |
| AI Insight | ✅ Done | Groq + rule-based fallback |
| Customer Inbox | ✅ Done | Messages, AI reply, ticket generation |
| Kanban Board | ✅ Done | 4 columns, ticket CRUD, priority |
| Structured logging | ✅ Done | structlog JSON, X-Request-ID |
| Rate limiting | ✅ Done | slowapi, per-endpoint limits |
| Docker Compose | ✅ Done | PostgreSQL + Redis |
| Full documentation | ✅ Done | 11 spec documents |
| GitHub repository | ✅ Done | github.com/Ayhan916/ma-analytics |

### What's Not Built (Known Gaps)

| Gap | Impact | When |
|-----|--------|------|
| Password reset | Blocker for paid users who forget passwords | Phase 1.5 |
| Email reply (Resend) | Inbox is read-only without it | Phase 1.5 |
| Account deletion | GDPR compliance | Phase 1.5 |
| Drag-and-drop Kanban | UX improvement | Phase 2 |
| Apple App Store | Doubles addressable data sources | Phase 2 |
| Trend charts | Dashboard depth | Phase 2 |
| Multi-user teams | Enterprise sales blocker | Phase 3 |

---

## 3. Phase 1.5 — Production Hardening (Month 1–2)

**Goal:** Get the product to a state where real customers can use it daily without friction.

**Success criteria:** 3 customers using product weekly for 4+ consecutive weeks.

### P0: Must-Have for First Paying Customer

**Password Reset**
- `POST /auth/forgot-password` → Resend API sends reset link
- `POST /auth/reset-password?token=...` → validates link, sets new password
- Reset tokens: 1-hour expiry, stored as hashed values
- Effort: 2 days

**Email Reply (Resend)**
- `POST /messages/{id}/send-reply` → Resend API sends actual email to customer
- Requires customer email on message
- Reply preview already exists in UI; add "Senden" button
- Effort: 1 day

**Account Deletion (GDPR)**
- `DELETE /auth/me` → cascade deletes all user data
- Confirmation email before deletion
- Effort: 1 day

**Pipeline Retry UI**
- Failed pipeline shows "Erneut versuchen" button in /datasources
- Calls existing `run_pipeline` task or `scrape_and_run` task
- Effort: 0.5 days

### P1: Quality of Life

**Incremental Scraping**
- Track `last_synced` timestamp per data source
- On re-sync: only fetch reviews newer than `last_synced`
- Prevents duplicate reviews, speeds up repeat analyses
- Effort: 2 days

**Message Filtering**
- `/inbox?sentiment=negative` filter in API + frontend dropdown
- Effort: 1 day

**Session Persistence**
- Replace `localStorage` token with `httpOnly` cookie + refresh token
- Security upgrade: XSS can't steal httpOnly cookies
- Effort: 3 days

**Performance Budget**
- API response p95 under 200ms for all read endpoints (measure with k6)
- Add missing composite indexes (`user_id` + status for tickets)
- Effort: 1 day

---

## 4. Phase 2 — Growth Features (Month 2–4)

**Goal:** Retain customers by deepening value. Target: 10 paying customers, €1,000 MRR.

**Guiding insight:** Customers churn when the product stops showing them new things. Phase 2 makes the dashboard richer and adds the second data source type that doubles addressable apps.

### Data Sources

**Apple App Store Integration**
- Library: `app-store-scraper` (npm) or `apple_appstore_scraper` (Python)
- Same pipeline: scrape → sentiment → embeddings → clustering
- UI: add "Apple App Store" option in data source form
- Business impact: iOS-first companies (major segment of B2C apps)
- Effort: 3 days

**Webhook / Zapier Integration**
- `POST /webhooks/review` → authenticated, receives single review object
- Enables real-time ingestion from any source via Zapier
- Triggers pipeline on accumulated reviews (batch every 50, or time-based)
- Effort: 4 days

### Dashboard

**Sentiment Trend Chart**
- Line chart: sentiment scores over time (week-by-week)
- Requires `reviewed_at` column (already stored)
- Populate `mentions_over_time` in Cluster model
- Frontend: recharts or nivo library
- Effort: 3 days

**Version Comparison**
- "Compare this week vs. last week" toggle
- Side-by-side cluster lists from two time ranges
- Shows regression: "Login issues appeared in v3.2.1 but not v3.2.0"
- Effort: 4 days

**Competitor Benchmarking**
- User connects competitor's Google Play app
- Dashboard shows: our app vs. competitor, cluster overlap, rating gap
- Effort: 5 days

### Kanban

**Drag-and-Drop**
- `@dnd-kit/core` library for React DnD
- Drop ticket on column → `PATCH /tickets/{id}` with new status
- Visual feedback: ghost card during drag
- Effort: 2 days

**Subtasks**
- Checkbox list within ticket detail panel
- Already in DB schema (`subtasks` JSON column)
- Frontend: add/remove/check subtasks inline
- Effort: 1 day

**Jira Export**
- `POST /integrations/jira/export-ticket/{id}`
- Requires: Jira API key (user provides in settings)
- Creates Jira issue, stores Jira issue key on ticket
- Effort: 3 days

### Intelligence Upgrades

**AI-Suggested Priority**
- When ticket is generated from a message or cluster, use Groq to suggest priority
- "Login bug with 11+ mentions, negative sentiment → High priority"
- Effort: 1 day

**HDBSCAN Clustering (better clusters)**
- Replace KMeans with HDBSCAN for datasets >500 reviews
- HDBSCAN: handles irregular cluster shapes, identifies noise, no fixed k
- Dramatically better clusters for large datasets
- Effort: 2 days

**Multilingual Support**
- Detect language of review text (`langdetect`)
- Translate to English before embedding (Google Translate API or LibreTranslate)
- Improves clustering quality for multilingual apps
- Effort: 3 days

---

## 5. Phase 3 — Team & Enterprise (Month 5–8)

**Goal:** Land first enterprise deal. Target: €5,000 MRR, 1 enterprise account.

**Guiding insight:** Enterprise buyers need three things beyond product functionality: team collaboration, security controls, and a vendor that won't disappear. Phase 3 addresses all three.

### Multi-User Teams

**Workspace Model**
- New entity: `Workspace` — a container for data sources, tickets, messages
- Users can be members of multiple workspaces
- Roles: Owner, Admin, Member, Viewer
- Effort: 8 days (significant data model change)

**Team Invitation**
- `POST /workspaces/{id}/invite` → sends invitation email
- Invitation link with scoped token
- Effort: 2 days

**Activity Feed**
- Real-time log of who did what: "Anna moved ticket #42 to Done"
- WebSocket or server-sent events (SSE)
- Effort: 3 days

### Enterprise Security

**SSO / SAML**
- Okta, Azure AD, Google Workspace integration
- Required for Enterprise procurement
- Effort: 5 days (plus vendor setup)

**Audit Log**
- Append-only log: `user_id`, `action`, `resource`, `timestamp`
- API: `GET /audit-log` with date range filter
- Export as CSV for compliance
- Effort: 3 days

**2FA (TOTP)**
- TOTP (Google Authenticator compatible)
- `POST /auth/setup-2fa` → generates QR code
- `POST /auth/verify-2fa` → validates TOTP code
- Effort: 2 days

### Analytics & Reporting

**Scheduled Reports**
- Weekly digest email: top 3 issues, sentiment trend, new clusters
- Configurable frequency (daily/weekly/monthly)
- Effort: 3 days

**PDF Export**
- Executive summary PDF: cover page, KPIs, top issues, AI insight
- `GET /reports/pdf?datasource_id=...`
- Effort: 2 days (pdfkit or Playwright)

**API Access**
- Customers can use MA Analytics API from their own tools
- Scoped API keys per workspace
- Rate-limited separately from web UI
- Effort: 3 days

---

## 6. Phase 4 — Platform & Scale (Month 9–18)

**Goal:** €50,000 MRR, 100+ customers, platform stability.

**Guiding insight:** At this scale, the bottleneck shifts from features to infrastructure. Every architectural shortcut taken in Phase 1 needs to be paid back.

### Infrastructure

**Managed PostgreSQL Migration**
- Move from self-hosted Docker to Neon or Supabase
- Point-in-time recovery, read replicas, connection pooling (PgBouncer)
- Zero-downtime migration via logical replication

**Horizontal Celery Scaling**
- Switch from `-P solo` (macOS dev) to `prefork` with KEDA autoscaling
- Scale workers based on Redis queue depth
- Target: 10 concurrent pipeline jobs at peak

**CDN for Frontend**
- Move static React build to Cloudflare Pages or Vercel
- Global edge distribution: <50ms asset load globally
- Backend API stays on server

**Monitoring Stack**
- Prometheus + Grafana: pipeline throughput, queue depth, API latency p99
- Sentry: error tracking and alerting
- Uptime: BetterUptime or Checkly

### Product Intelligence

**Cross-Customer Benchmarking**
- Anonymous, aggregated benchmarking: "Your login issue rate vs. top apps in your category"
- This is the network effect moat — more customers → more valuable benchmarks
- Legal: requires explicit opt-in, anonymization, privacy review

**LLM Upgrade Path**
- Current: Groq llama3-8b as optional enhancement
- Phase 4: Claude Haiku 4.5 as default (superior German language understanding)
- Fine-tuned cluster labeling (trained on MA Analytics customer data)

**Predictive Analytics**
- "Based on current trajectory, this issue will affect 30% more users in 30 days"
- Requires 6+ months of historical data per customer — hence Phase 4 timing

---

## 7. KPI Targets by Phase

| Metric | v1.0 Now | Phase 1.5 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|-----------|---------|---------|---------|
| Paying customers | 0 | 3 | 10 | 50 | 100+ |
| MRR | €0 | €500 | €2,000 | €10,000 | €50,000+ |
| NPS | — | ≥40 | ≥50 | ≥55 | ≥60 |
| Pipeline success rate | >95% | >98% | >99% | >99.5% | >99.9% |
| Time-to-first-insight | <10min | <7min | <5min | <3min | <3min |
| Monthly pipeline runs | — | 50 | 300 | 2,000 | 10,000+ |

---

## 8. Prioritization Framework

Features are prioritized using the **RICE framework**:

```
Score = (Reach × Impact × Confidence) / Effort
```

| Factor | Definition | Scale |
|--------|-----------|-------|
| Reach | How many customers affected per quarter | # of customers |
| Impact | How much it improves their core metric | 0.25 / 0.5 / 1 / 2 / 3 |
| Confidence | How sure we are the estimate is right | 20% / 50% / 80% / 100% |
| Effort | Engineering time in person-weeks | Number |

**Example — Password Reset:**
- Reach: 10 (every customer eventually needs it)
- Impact: 3 (blocker for retention)
- Confidence: 100% (certain it's needed)
- Effort: 0.5 weeks
- **Score: (10 × 3 × 1.0) / 0.5 = 60 — high priority**

**Example — PDF Export:**
- Reach: 3 (enterprise customers with reporting needs)
- Impact: 1 (nice-to-have, not blocking)
- Confidence: 50%
- Effort: 0.5 weeks
- **Score: (3 × 1 × 0.5) / 0.5 = 3 — low priority**

---

## 9. Feature Flags Strategy

As the product scales, feature flags become essential for:
1. Rolling out features to subset of customers (beta testing)
2. A/B testing (does the new dashboard increase engagement?)
3. Monetization (features gated by pricing tier)

**Phase 1.5:** Simple env-var flags (`GROQ_API_KEY` already acts as a feature flag)
**Phase 2:** Proper feature flag system (`posthog-python` or `unleash`)
**Phase 3:** Per-customer feature overrides (enterprise early access)

---

## 10. What We Won't Build

Being explicit about what we're NOT building is as important as the roadmap.

| Feature | Why Not |
|---------|---------|
| Mobile app | Desktop tool for professionals; mobile adds cost without addressing pain |
| Self-hosted enterprise | Engineering overhead too high for one team at this stage |
| Real-time streaming analytics | Batch analysis (hourly/daily) is sufficient for the use case |
| Custom ML model training | Pre-trained models (MiniLM, RoBERTa) are good enough; custom training requires 100x more reviews |
| Social media monitoring (Twitter/X) | Different buyer, different workflow; separate product |
| Survey creation | Not the job to be done; SurveyMonkey does this well |

---

*Document Owner: Product Strategy*
*Last Updated: 2026-07*
*Status: v1.0 Complete — Phase 1.5 next milestone*
