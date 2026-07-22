# Product Requirements — MA Analytics

> *"Requirements are not what customers ask for. Requirements are what customers need in order to accomplish what they're trying to do."*

---

## 1. Document Purpose

This document defines the complete functional and non-functional requirements for MA Analytics v1.0. It serves as the authoritative source of truth for what the system must do, why it must do it, and how well it must do it.

Every requirement is tagged with:
- **Priority:** P0 (must-have), P1 (important), P2 (nice-to-have)
- **Status:** ✅ Implemented | 🔄 In Progress | ⬜ Planned

---

## 2. User Roles

### Role: Product Manager (Primary)
**Goal:** Understand what customers want, prioritize the roadmap, communicate priorities to engineering.
**Frequency:** Weekly review of insights, daily Kanban management.
**Success metric:** Reduced time from "feedback received" to "ticket created" from 4 hours to 15 minutes.

### Role: Customer Success Manager (Secondary)
**Goal:** Respond to customer messages quickly and escalate systemic issues.
**Frequency:** Daily Inbox usage.
**Success metric:** Reply time reduced from 2 hours to 10 minutes.

### Role: Founder / Solo Operator (Tertiary)
**Goal:** Stay close to customer sentiment without dedicated PM/CS resources.
**Frequency:** 2-3x per week.
**Success metric:** Weekly feedback review takes <20 minutes.

---

## 3. Functional Requirements

### 3.1 Authentication & Account Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| AUTH-01 | User can register with email + password | P0 | ✅ |
| AUTH-02 | Password minimum 8 characters, validated server-side | P0 | ✅ |
| AUTH-03 | User can log in and receive a JWT access token | P0 | ✅ |
| AUTH-04 | Token expires after 24 hours; user must re-authenticate | P0 | ✅ |
| AUTH-05 | All protected routes require valid Bearer token | P0 | ✅ |
| AUTH-06 | User can view their profile (GET /auth/me) | P0 | ✅ |
| AUTH-07 | Password reset via email (Resend API) | P1 | ⬜ |
| AUTH-08 | OAuth login (Google) | P2 | ⬜ |
| AUTH-09 | Multi-user team workspace with role-based access | P1 | ⬜ |

---

### 3.2 Data Sources

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DS-01 | User can connect a Google Play app by App ID or full URL | P0 | ✅ |
| DS-02 | System extracts App ID from Play Store URLs automatically | P0 | ✅ |
| DS-03 | User can configure review count (50, 100, 200, 500) | P0 | ✅ |
| DS-04 | User can configure language and country for scraping | P0 | ✅ |
| DS-05 | User can upload a CSV file with review data | P0 | ✅ |
| DS-06 | CSV upload supports configurable column mapping | P0 | ✅ |
| DS-07 | User can view all connected data sources with status | P0 | ✅ |
| DS-08 | User can delete a data source (cascading delete of all data) | P0 | ✅ |
| DS-09 | Data source shows last sync timestamp | P0 | ✅ |
| DS-10 | Apple App Store support | P1 | ⬜ |
| DS-11 | Trustpilot / G2 / Capterra integration | P2 | ⬜ |
| DS-12 | Zapier / Webhook integration for real-time review ingestion | P2 | ⬜ |

---

### 3.3 ML Pipeline

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PIPE-01 | Pipeline runs as background job (non-blocking) | P0 | ✅ |
| PIPE-02 | Job status is trackable (queued → running → done/failed) | P0 | ✅ |
| PIPE-03 | Frontend polls job status every 4 seconds while running | P0 | ✅ |
| PIPE-04 | Text preprocessing: clean, lowercase, remove URLs/punctuation | P0 | ✅ |
| PIPE-05 | Sentiment classification: positive / negative / neutral | P0 | ✅ |
| PIPE-06 | Sentiment derived from star rating if available (1-2=neg, 4-5=pos) | P0 | ✅ |
| PIPE-07 | Fallback: transformer-based sentiment model (RoBERTa) | P0 | ✅ |
| PIPE-08 | Sentence embeddings generated for all reviews (all-MiniLM-L6-v2) | P0 | ✅ |
| PIPE-09 | KMeans clustering on negative reviews → Issues clusters | P0 | ✅ |
| PIPE-10 | KMeans clustering on positive reviews → Strengths clusters | P0 | ✅ |
| PIPE-11 | Cluster count auto-determined: max(3, min(10, n_reviews//10)) | P0 | ✅ |
| PIPE-12 | Cluster labels via TF-IDF keyword extraction | P0 | ✅ |
| PIPE-13 | Cluster summaries via Groq LLM if API key is configured | P1 | ✅ |
| PIPE-14 | Rule-based fallback summary if no Groq key | P0 | ✅ |
| PIPE-15 | Pipeline job stores: status, progress stage, review count, error | P0 | ✅ |
| PIPE-16 | On failure: error message stored and surfaced to user | P0 | ✅ |
| PIPE-17 | Re-run pipeline on existing data (without re-scraping) | P1 | ✅ |
| PIPE-18 | GPU acceleration via Apple Silicon MPS (local dev) | P1 | ✅ |
| PIPE-19 | Incremental scraping (only fetch new reviews since last sync) | P1 | ⬜ |
| PIPE-20 | Multilingual support (auto-detect language, translate to EN) | P2 | ⬜ |

---

### 3.4 Dashboard

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DASH-01 | Dashboard shows KPI: total review count | P0 | ✅ |
| DASH-02 | Dashboard shows KPI: average star rating | P0 | ✅ |
| DASH-03 | Dashboard shows KPI: % positive reviews | P0 | ✅ |
| DASH-04 | Dashboard shows KPI: % negative reviews | P0 | ✅ |
| DASH-05 | Sentiment distribution bar (visual breakdown) | P0 | ✅ |
| DASH-06 | Top issues list (sorted by mention count, expandable) | P0 | ✅ |
| DASH-07 | Top strengths list (sorted by mention count, expandable) | P0 | ✅ |
| DASH-08 | Each cluster shows: label, mention count, summary, 3 example quotes | P0 | ✅ |
| DASH-09 | AI Insight: executive summary paragraph | P0 | ✅ |
| DASH-10 | AI Insight source labeled (groq / rule-based) | P0 | ✅ |
| DASH-11 | DataSource selector (switch between connected apps) | P0 | ✅ |
| DASH-12 | Empty state: redirect to Data Sources if no data | P0 | ✅ |
| DASH-13 | Sentiment trend over time (line chart) | P1 | ⬜ |
| DASH-14 | Version comparison (compare reviews across app versions) | P1 | ⬜ |
| DASH-15 | Competitor benchmarking dashboard | P2 | ⬜ |

---

### 3.5 Customer Inbox

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| INBOX-01 | User can view all customer messages in a list | P0 | ✅ |
| INBOX-02 | Message list shows: name, sentiment badge, text preview, date | P0 | ✅ |
| INBOX-03 | User can create a new message (name, email, text) | P0 | ✅ |
| INBOX-04 | Sentiment auto-detected on message creation | P0 | ✅ |
| INBOX-05 | User can select a message and view full detail | P0 | ✅ |
| INBOX-06 | User can generate an AI reply for any message | P0 | ✅ |
| INBOX-07 | AI reply uses Groq if configured, else rule-based template | P0 | ✅ |
| INBOX-08 | User can generate tickets from a message | P0 | ✅ |
| INBOX-09 | Generated tickets appear immediately in Kanban Board | P0 | ✅ |
| INBOX-10 | Ticket generation creates 1-3 tickets from message content | P0 | ✅ |
| INBOX-11 | Generated tickets carry customer name as context | P0 | ✅ |
| INBOX-12 | Send reply via email (Resend API integration) | P1 | ⬜ |
| INBOX-13 | Filter messages by sentiment | P1 | ⬜ |
| INBOX-14 | Search messages | P1 | ⬜ |
| INBOX-15 | Mark message as resolved | P1 | ⬜ |

---

### 3.6 Kanban Board

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| KAN-01 | Four columns: Backlog, Todo, In Progress, Done | P0 | ✅ |
| KAN-02 | Each column shows ticket count | P0 | ✅ |
| KAN-03 | Ticket card shows: title, priority badge, labels | P0 | ✅ |
| KAN-04 | User can create a new ticket from Backlog column | P0 | ✅ |
| KAN-05 | User can click any ticket to open a detail panel | P0 | ✅ |
| KAN-06 | Detail panel: edit title, description, status, priority | P0 | ✅ |
| KAN-07 | Status change updates the ticket's column immediately | P0 | ✅ |
| KAN-08 | User can delete a ticket with confirmation dialog | P0 | ✅ |
| KAN-09 | Ticket shows customer name if generated from inbox message | P0 | ✅ |
| KAN-10 | Unsaved changes highlighted with "Save" button | P0 | ✅ |
| KAN-11 | Drag-and-drop between columns | P1 | ⬜ |
| KAN-12 | Add subtasks to a ticket | P1 | ⬜ |
| KAN-13 | Add comments to a ticket | P1 | ⬜ |
| KAN-14 | Filter tickets by priority | P1 | ⬜ |
| KAN-15 | Jira / Linear export | P2 | ⬜ |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| PERF-01 | API response time (p95) for read endpoints | < 200ms |
| PERF-02 | API response time (p95) for write endpoints | < 500ms |
| PERF-03 | Dashboard page initial load | < 1.5s |
| PERF-04 | ML pipeline completion (500 reviews) | < 5 minutes |
| PERF-05 | ML pipeline completion (100 reviews) | < 90 seconds |
| PERF-06 | Frontend bundle size (gzip) | < 100KB |

### 4.2 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| REL-01 | API uptime | ≥ 99.5% |
| REL-02 | Pipeline job failure rate | < 2% |
| REL-03 | Failed jobs surface error message to user | 100% |
| REL-04 | Database backup | Daily, 7-day retention |

### 4.3 Security

| ID | Requirement | Target |
|----|-------------|--------|
| SEC-01 | All endpoints require authentication (except /health, /auth/*) | 100% |
| SEC-02 | Users can only access their own data | 100% |
| SEC-03 | Passwords hashed with bcrypt (cost factor 12) | 100% |
| SEC-04 | JWT tokens expire after 24 hours | 100% |
| SEC-05 | Rate limiting on authentication endpoints | 10/min register, 20/min login |
| SEC-06 | API docs hidden in production | 100% |

### 4.4 Usability

| ID | Requirement | Target |
|----|-------------|--------|
| UX-01 | New user can create first data source in < 3 minutes | 95% of users |
| UX-02 | First insight visible within 5 minutes of connecting app | 90% of users |
| UX-03 | All actions have loading states (no silent waiting) | 100% |
| UX-04 | All destructive actions require confirmation | 100% |
| UX-05 | Empty states provide actionable next step | 100% |

### 4.5 Scalability

| ID | Requirement | Target |
|----|-------------|--------|
| SCALE-01 | System handles 100 concurrent users | Phase 1 |
| SCALE-02 | System handles 1,000 concurrent users (horizontal scaling) | Phase 2 |
| SCALE-03 | Database supports 10M reviews total | Phase 2 |
| SCALE-04 | Celery worker pool scales horizontally | Phase 2 |

---

## 5. Constraints

**Technical:**
- Backend must run on Python 3.9+ (macOS MPS compatibility)
- ML models must run locally (no external API calls for inference)
- Google Play scraping is subject to Google's rate limiting and HTML changes

**Business:**
- MVP must be deployable by a single developer
- Infrastructure cost must remain under €200/month at 100 customers

**Legal:**
- Google Play reviews are public data — scraping is legally permissible
- No PII stored beyond what the user explicitly provides
- GDPR compliance required for EU customers (data deletion endpoint: P1)

---

## 6. Acceptance Criteria (v1.0 Launch)

MA Analytics v1.0 is ready to launch when:

- [ ] A new user can register, connect a Google Play app, and see clustered insights in under 10 minutes
- [ ] The pipeline processes 200 reviews without error in under 3 minutes
- [ ] All P0 requirements above are marked ✅
- [ ] The system handles 10 simultaneous pipeline jobs without degradation
- [ ] No critical security vulnerabilities (OWASP Top 10 checked)
- [ ] Docker build passes for both backend and frontend
- [ ] README is complete and a developer can set up the project from scratch in under 30 minutes

---

*Document Owner: Product Management*
*Last Updated: 2026-07*
*Status: v1.0 — All P0 requirements implemented*
