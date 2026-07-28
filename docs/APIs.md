# API Reference — MA Analytics

**Base URL:** `http://localhost:8000` (development)  
**Auth:** HTTP-only cookie (`access_token`). Set automatically on login.  
**Content-Type:** `application/json` for all requests and responses.  
**OpenAPI UI:** `http://localhost:8000/docs` (requires `DEBUG=true`)

---

## Authentication

### POST /auth/register
Register a new user account.

**Request:**
```json
{ "email": "user@example.com", "password": "securepassword" }
```
**Response 200:**
```json
{ "id": "uuid", "email": "user@example.com" }
```

### POST /auth/login
Authenticate and receive JWT cookies.

**Request:**
```json
{ "email": "user@example.com", "password": "securepassword" }
```
**Response 200:** Sets `access_token` (15 min) and `refresh_token` (7 days) as HTTP-only cookies.
```json
{ "message": "Login successful" }
```

### POST /auth/logout
Clear auth cookies.

### POST /auth/refresh
Exchange refresh token for a new access token. Called automatically by the frontend on 401.

### GET /auth/me
Returns the currently authenticated user.
```json
{ "id": "uuid", "email": "user@example.com" }
```

### POST /auth/password-reset-request
Send a password reset email.
```json
{ "email": "user@example.com" }
```

### POST /auth/password-reset
Reset password using token from email.
```json
{ "token": "reset-token", "new_password": "newpassword" }
```

---

## Data Sources

### GET /datasources/
List all data sources for the authenticated user.
```json
[{
  "id": "uuid",
  "name": "My BMW App",
  "app_id": "de.bmw.connected",
  "industry": "Automotive",
  "job_status": "done",
  "job_id": "celery-task-id",
  "review_count": 8234,
  "created_at": "2026-07-01T10:00:00Z"
}]
```

### POST /datasources/
Create a data source by Google Play App ID.
```json
{ "app_id": "de.bmw.connected", "industry": "Automotive", "name": "My BMW App" }
```

### GET /datasources/{id}
Get a single data source with detailed stats.

### DELETE /datasources/{id}
Delete a data source and all associated reviews, signals, clusters.

### POST /datasources/{id}/scrape
Trigger the ML pipeline for a data source. Returns immediately; pipeline runs in background.
```json
{ "task_id": "celery-task-id" }
```

### POST /datasources/upload-csv
Upload a CSV file of reviews. Triggers the ML pipeline automatically.

**Form fields:** `file` (CSV), `name` (string), `industry` (string)

---

## Jobs

### GET /jobs/{task_id}
Poll Celery task status.
```json
{ "task_id": "...", "status": "running", "progress": 65, "message": "Generating embeddings..." }
```
Status values: `pending` | `running` | `done` | `failed`

---

## Dashboard

### GET /dashboard/
Returns aggregated KPIs, top signals, cluster summary, and AI-generated narrative for all data sources.

```json
{
  "total_reviews": 33649,
  "total_apps": 5,
  "top_issues": [{"feature": "Updates", "count": 3585, "severity": 4.6}],
  "top_strengths": [...],
  "clusters": [...],
  "ai_narrative": "Nutzer von Premium-Fahrzeug-Apps kämpfen vor allem mit..."
}
```

---

## Innovation Lab

### POST /innovation/signals
Returns all available signal clusters for the given filter scope. Used by the Signal-Steuerung panel in the UI.

**Request:** Same body as `/innovation/generate` (without `excluded_signals`).
```json
{ "mode": "competitor", "scope": "all" }
```

**Response:**
```json
[{
  "feature": "Updates",
  "total_mentions": 3585,
  "fr_mentions": 214,
  "bug_mentions": 3078,
  "app_count": 5,
  "avg_severity": 4.6
}]
```

### POST /innovation/generate
Generate a full Innovation Brief. Saves to DB automatically and returns the saved brief.

**Request:**
```json
{
  "mode": "competitor",
  "scope": "all",
  "industry": null,
  "datasource_ids": null,
  "market": "de",
  "user_hypothesis": "Fahrer wollen Software-Updates ohne Werkstattbesuch",
  "excluded_signals": ["Updates", "Account"]
}
```

- `mode`: `"competitor"` (attack existing app weaknesses) | `"innovation"` (find unoccupied market gaps)
- `scope`: `"all"` | `"industry"` (requires `industry`) | `"datasource"` (requires `datasource_ids`)
- `excluded_signals`: Optional. If `null`, auto-excludes signals from previous briefs. If `[]`, no exclusion. If list, excludes those signals.
- `user_hypothesis`: Optional. If provided, enables hypothesis-guided RAG retrieval (semantic search over reviews before signal aggregation).

**Response:** `SavedBriefFull` — see GET /innovation/briefs/{id}.

**Errors:**
- `422` — Not enough data for the given filter
- `429` — All AI providers rate-limited
- `500` — AI response could not be parsed

### GET /innovation/briefs
List all saved Innovation Briefs (metadata only, no full content).

```json
[{
  "id": "uuid",
  "created_at": "2026-07-27T19:00:00Z",
  "mode": "competitor",
  "scope": "all",
  "product_name": "TrustSync",
  "tagline": "Fahrzeugdaten, die wirklich aktualisieren...",
  "risk_level": "mittel",
  "total_demand": 892,
  "apps_analyzed": 5,
  "user_hypothesis": null,
  "industry": null
}]
```

### GET /innovation/briefs/{id}
Get a single saved brief with full content.

```json
{
  "id": "uuid",
  "created_at": "...",
  "mode": "competitor",
  "scope": "all",
  "product_name": "TrustSync",
  "tagline": "...",
  "core_problem": "...",
  "market_gap": "...",
  "features": [{ "name": "OTA-Updates ohne Werkstatt", "mentions": 214, "priority": "hoch" }],
  "target_audience": "...",
  "differentiation": "...",
  "risk": "...",
  "risk_level": "mittel",
  "hypothesis_check": null,
  "hypothesis_alignment": null,
  "total_demand": 892,
  "apps_analyzed": 5,
  "sources": [{ "feature": "Updates", "fr_mentions": 214, "total_mentions": 3585, ... }],
  "concept_description": "# TrustSync — Produktkonzeptdokumentation\n..."
}
```

### DELETE /innovation/briefs/{id}
Delete a saved brief.

### POST /innovation/briefs/{id}/generate-concept
Generate (or regenerate) the long-form concept description for a saved brief. Updates the brief in place.

**Response:**
```json
{ "concept_description": "# ProductName — Produktkonzeptdokumentation\n..." }
```

### POST /innovation/briefs/{id}/chat
Copilot chat about a saved brief. Sends conversation history and gets an AI response.

**Request:**
```json
{
  "message": "Was wäre ein realistischer Preis für dieses Produkt?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```
**Response:**
```json
{ "reply": "Basierend auf dem Zielmarkt..." }
```

---

## Search

### POST /search/
Hybrid semantic + full-text search over all reviews.

**Request:**
```json
{
  "query": "Bluetooth verbindung verliert sich ständig",
  "search_type": "hybrid",
  "datasource_ids": ["uuid1", "uuid2"],
  "limit": 20,
  "min_score": 1.0,
  "max_score": 3.0,
  "language": "de"
}
```

- `search_type`: `"hybrid"` (default, RRF fusion) | `"vector"` | `"fulltext"`
- `datasource_ids`: Filter to specific apps. Omit for all apps.
- `min_score` / `max_score`: Filter by star rating (1.0–5.0)
- `language`: `"de"` | `"en"` | omit for all

**Response:**
```json
[{
  "id": "review-uuid",
  "content": "Bluetooth bricht nach jedem Update ab...",
  "score": 1.0,
  "sentiment": "negative",
  "datasource_name": "My BMW App",
  "reviewed_at": "2026-01-15T...",
  "similarity": 0.87
}]
```

---

## Intelligence (Document RAG)

### POST /intelligence/upload
Upload a PDF document for indexing and RAG.

**Form fields:** `file` (PDF), `title` (string), `doc_type` (e.g. "regulation"), `year` (int)

### GET /intelligence/documents
List all indexed documents.

### POST /intelligence/query
Ask a question over indexed documents.

**Request:**
```json
{
  "question": "Was sind die Kernpflichten aus der CSDDD?",
  "doc_ids": ["uuid1"]
}
```
**Response:**
```json
{
  "answer": "Die CSDDD verpflichtet Unternehmen zu...",
  "sources": [{ "doc_title": "CSDDD 2024", "page": 12, "chunk": "..." }]
}
```

### POST /intelligence/extract-all
Trigger batch metric extraction from all indexed documents. Extracts Scope 1/2/3 emissions, reduction targets, regulatory obligations.

---

## Messages (Inbox)

### GET /messages/
List customer messages with pagination.

### POST /messages/
Create a new message (manual entry).

### PUT /messages/{id}
Update message status (`new` → `in_progress` → `resolved`).

### POST /messages/{id}/generate-reply
Generate an AI reply for a customer message.
```json
{ "reply": "Vielen Dank für Ihre Nachricht..." }
```

### POST /messages/{id}/create-ticket
Create a Kanban ticket from a message.

---

## Tickets (Kanban)

### GET /tickets/
List all tickets for the authenticated user.

### POST /tickets/
Create a ticket.
```json
{
  "title": "Bluetooth Verbindungsabbrüche untersuchen",
  "description": "...",
  "priority": "high",
  "status": "backlog"
}
```

### PUT /tickets/{id}
Update ticket (title, description, priority, status, assignee).

### DELETE /tickets/{id}
Delete a ticket.

---

## Health

### GET /health/
Returns `{ "status": "ok" }`. Used for deployment health checks.

---

## Error Format

All errors follow a consistent format:
```json
{ "detail": "Human-readable error message in German or English" }
```

Common HTTP status codes:
- `400` — Bad request / validation error
- `401` — Not authenticated
- `403` — Forbidden (wrong user)
- `404` — Resource not found
- `422` — Unprocessable entity (not enough data, validation failed)
- `429` — Rate limit reached (auth endpoints or AI providers)
- `500` — Internal server error
