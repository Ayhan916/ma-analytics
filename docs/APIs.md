# API Reference — MA Analytics

> *"A great API is a product. It has a target customer (developers), a value proposition (making their job easier), and a UX (consistency, predictability, clarity). Design it like a product, not like an implementation detail."*

---

## 1. Overview

**Base URL:** `http://localhost:8001` (development) | `https://api.your-domain.com` (production)

**Authentication:** Bearer token (JWT). Include in all protected requests:
```
Authorization: Bearer <access_token>
```

**Content-Type:** `application/json` for all requests and responses.

**API Versioning:** Currently unversioned. Breaking changes will be introduced with `/v2/` prefix.

**Rate Limits:**
- `POST /auth/register` — 10 requests/minute per IP
- `POST /auth/login` — 20 requests/minute per IP
- All other endpoints — 200 requests/minute per IP

**OpenAPI Docs:** Available at `/docs` when `DEBUG=true`.

---

## 2. Error Format

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message",
  "errors": [
    {
      "field": "email",
      "msg": "value is not a valid email address"
    }
  ]
}
```

`errors` array is only present for validation errors (HTTP 422).

**HTTP Status Codes Used:**

| Code | Meaning |
|------|---------|
| `200` | Success (GET, PATCH) |
| `201` | Created (POST) |
| `204` | No Content (DELETE) |
| `400` | Bad Request (business logic violation) |
| `401` | Unauthorized (missing or invalid token) |
| `404` | Not Found |
| `422` | Unprocessable Entity (validation error) |
| `429` | Too Many Requests (rate limited) |
| `500` | Internal Server Error |

---

## 3. Authentication

### POST /auth/register

Create a new user account.

**Rate limit:** 10/minute

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "Max Mustermann"
}
```

**Validation:**
- `email` — valid email format, must be unique
- `password` — minimum 8 characters
- `full_name` — optional

**Response 201:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `400 Email already registered` — email exists
- `400 Password must be at least 8 characters`

---

### POST /auth/login

Authenticate and receive an access token.

**Rate limit:** 20/minute

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401 Invalid credentials` — wrong email or password (intentionally vague to prevent user enumeration)

---

### GET /auth/me

Get the current authenticated user's profile.

**Auth:** Required

**Response 200:**
```json
{
  "id": "3bd9dccc-36fb-4373-8f0f-19eef6ae56ed",
  "email": "user@example.com",
  "full_name": "Max Mustermann"
}
```

**Token expiry:** Tokens expire after 24 hours. A `401` response on this endpoint means the token has expired — the client should redirect to `/login`.

---

## 4. Data Sources

### POST /datasources/google-play

Create a new Google Play data source and immediately trigger scraping + ML pipeline.

**Auth:** Required

**Request:**
```json
{
  "name": "BMW Connected",
  "app_id": "de.bmw.connected",
  "count": 200,
  "lang": "de",
  "country": "de"
}
```

**Field reference:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Display name for the data source |
| `app_id` | string | ✅ | Play Store App ID (e.g. `de.bmw.connected`) or full Play Store URL |
| `count` | integer | ❌ | Number of reviews to scrape. Default: 200. Options: 50, 100, 200, 500 |
| `lang` | string | ❌ | Review language code. Default: `de`. Options: `de`, `en`, `fr`, `es` |
| `country` | string | ❌ | Store country code. Default: `de`. Options: `de`, `us`, `gb`, `at`, `ch` |

**Note:** `app_id` accepts full Play Store URLs. The API automatically extracts the `id=` parameter.

**Response 201:**
```json
{
  "id": "de6e6e9c-9ebe-4a02-8d30-abfb5be6f986",
  "name": "BMW Connected",
  "type": "google_play",
  "app_id": "de.bmw.connected",
  "job_id": "05a1eb2a-074d-4cfc-8e4a-369b7790c0b4",
  "job_status": "pending",
  "review_count": 0,
  "last_synced": null
}
```

**Behavior:** Returns immediately. The `job_id` should be used to poll `GET /jobs/{job_id}` for pipeline progress.

---

### POST /datasources/upload-csv

Upload a CSV file and trigger the ML pipeline on its contents.

**Auth:** Required

**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Display name for the data source |
| `file` | file | ✅ | CSV file. Max size: 10MB |
| `text_col` | string | ❌ | Column name for review text. Default: `content` |
| `score_col` | string | ❌ | Column name for star rating (1-5). Default: `score` |
| `date_col` | string | ❌ | Column name for review date. Default: `at` |
| `version_col` | string | ❌ | Column name for app version. Default: `reviewCreatedVersion` |

**Expected CSV format (default columns):**
```csv
content,score,at,reviewCreatedVersion
"Gute App, funktioniert gut",5,2024-01-15,3.2.1
"Login funktioniert nicht",1,2024-01-16,3.2.1
```

**Response 201:** Same format as Google Play response.

---

### GET /datasources

List all data sources for the authenticated user.

**Auth:** Required

**Response 200:**
```json
[
  {
    "id": "98c2c412-a28a-42ff-8026-868f5f74f6b9",
    "name": "BMW Test v2",
    "type": "google_play",
    "app_id": "de.bmw.connected",
    "job_id": "55723fe9-3a5d-4424-b919-c4bfddbcab2b",
    "job_status": "done",
    "review_count": 50,
    "last_synced": "2026-07-22T17:23:55.246878+00:00"
  }
]
```

**Sorted:** By `created_at` descending (newest first).

---

### DELETE /datasources/{datasource_id}

Delete a data source and all associated data (reviews, clusters, jobs).

**Auth:** Required

**Response 204:** No content.

**Errors:**
- `404 DataSource not found` — does not exist or belongs to another user

---

## 5. Pipeline Jobs

### GET /jobs/{job_id}

Get the current status of a pipeline job. Used by the frontend for progress polling.

**Auth:** Required

**Response 200:**
```json
{
  "id": "55723fe9-3a5d-4424-b919-c4bfddbcab2b",
  "datasource_id": "98c2c412-a28a-42ff-8026-868f5f74f6b9",
  "status": "done",
  "progress": "done",
  "review_count": 50,
  "error": null
}
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `pending` | Task queued in Redis, not yet picked up by worker |
| `running` | Worker is actively processing |
| `done` | Pipeline completed successfully |
| `failed` | Pipeline encountered an error |

**Progress stages (during `running` status):**

| Progress | Meaning |
|----------|---------|
| `scraping` | Fetching reviews from Google Play |
| `saving_reviews` | Storing reviews in database |
| `analyzing_sentiment` | Running sentiment classification |
| `creating_embeddings` | Generating sentence embeddings |
| `clustering` | Running KMeans clustering |
| `done` | All steps completed |

**Polling recommendation:** Poll every 4 seconds while `status` is `pending` or `running`. Stop when `done` or `failed`.

---

## 6. Dashboard

### GET /dashboard/summary

Get a complete summary for a data source: KPIs, top issues, top strengths.

**Auth:** Required

**Query parameters:**
- `datasource_id` (required) — UUID of the data source

**Response 200:**
```json
{
  "datasource_id": "98c2c412-a28a-42ff-8026-868f5f74f6b9",
  "datasource_name": "BMW Test v2",
  "review_count": 50,
  "avg_rating": 2.82,
  "sentiment": {
    "positive": 23,
    "negative": 25,
    "neutral": 2,
    "total": 50
  },
  "top_issues": [
    {
      "id": "0c8f22b9-9931-40b7-9a84-21b02554da9a",
      "label": "login / nicht / möglich",
      "mentions": 11,
      "summary": "11 reviews mention this issue.",
      "examples": [
        "Anmeldung nicht möglich.. Peinliche app",
        "Kein Login mehr möglich."
      ]
    }
  ],
  "top_strengths": [
    {
      "id": "8aa2efa6-61b1-4a24-a617-f077ada6d769",
      "label": "super / app / einwandfrei",
      "mentions": 10,
      "summary": "10 reviews mention this strength.",
      "examples": [
        "super App, funktioniert einwandfrei, Daumen hoch"
      ]
    }
  ]
}
```

**Notes:**
- `top_issues` and `top_strengths` are sorted by `mentions` descending
- Max 5 items each
- `examples` contains up to 5 real review quotes

---

### GET /dashboard/issues

Get all issue clusters for a data source.

**Auth:** Required

**Query parameters:**
- `datasource_id` (required)

**Response 200:** Array of cluster objects (same structure as `top_issues` above), all issues, sorted by mentions descending.

---

### GET /dashboard/strengths

Get all strength clusters for a data source.

**Auth:** Required

**Query parameters:**
- `datasource_id` (required)

**Response 200:** Array of cluster objects, all strengths, sorted by mentions descending.

---

### GET /dashboard/insight

Get an AI-generated executive summary for a data source.

**Auth:** Required

**Query parameters:**
- `datasource_id` (required)

**Response 200:**
```json
{
  "insight": "50 reviews analyzed: 46% positive sentiment. Main issue: 'login / nicht / möglich' (11 mentions). Top strength: 'super / app / einwandfrei' (10 mentions).",
  "generated_by": "rule-based"
}
```

**`generated_by` values:**
- `groq` — Groq LLM generated the insight (higher quality, requires `GROQ_API_KEY`)
- `rule-based` — Template-based generation (always available)

---

## 7. Tickets

### GET /tickets

List all tickets for the authenticated user.

**Auth:** Required

**Query parameters:**
- `status` (optional) — Filter by status: `Backlog`, `Todo`, `In Progress`, `Done`
- `priority` (optional) — Filter by priority: `High`, `Medium`, `Low`

**Response 200:**
```json
[
  {
    "id": "8846f96a-e0ad-40db-a8cc-3289588fab73",
    "title": "Login-Bug beheben",
    "description": "Nutzer können sich nicht einloggen (Authentifizierungsfehler)",
    "priority": "High",
    "status": "In Progress",
    "customer_name": null,
    "labels": ["bug", "auth"],
    "subtasks": [],
    "comments": [],
    "created_at": "2026-07-22T17:31:04.000824+00:00",
    "updated_at": "2026-07-22T17:31:22.000000+00:00"
  }
]
```

**Sorted:** By `created_at` descending.

---

### POST /tickets

Create a new ticket.

**Auth:** Required

**Request:**
```json
{
  "title": "Login-Bug beheben",
  "description": "Nutzer können sich nicht einloggen",
  "priority": "High",
  "status": "Backlog",
  "customer_name": "Max Mustermann",
  "labels": ["bug", "auth"],
  "subtasks": [
    {"text": "Reproduce the error", "done": false},
    {"text": "Fix authentication flow", "done": false}
  ]
}
```

**Response 201:** Full ticket object.

---

### PATCH /tickets/{ticket_id}

Update any fields of a ticket. Only provided fields are updated (partial update).

**Auth:** Required

**Request (all fields optional):**
```json
{
  "title": "Updated title",
  "description": "Updated description",
  "priority": "Medium",
  "status": "In Progress",
  "customer_name": "Max Mustermann",
  "labels": ["bug"],
  "subtasks": [{"text": "Task 1", "done": true}],
  "comments": ["Fixed in v3.2.2"]
}
```

**Response 200:** Updated ticket object.

---

### DELETE /tickets/{ticket_id}

Delete a ticket permanently.

**Auth:** Required

**Response 204:** No content.

---

## 8. Messages

### GET /messages

List all customer messages for the authenticated user.

**Auth:** Required

**Response 200:**
```json
[
  {
    "id": "8fa0594d-0791-4c1e-bc84-c5e9587a1453",
    "name": "Max Mustermann",
    "email": "max@example.com",
    "text": "Ich kann mich seit 2 Wochen nicht einloggen. Das ist sehr frustrierend!",
    "sentiment": "negative",
    "created_at": "2026-07-22T17:31:16.104898+00:00"
  }
]
```

**Sorted:** By `created_at` descending (newest first).

---

### POST /messages

Create a new customer message. Sentiment is automatically detected.

**Auth:** Required

**Request:**
```json
{
  "name": "Max Mustermann",
  "email": "max@example.com",
  "text": "Ich kann mich seit 2 Wochen nicht einloggen. Das ist sehr frustrierend!"
}
```

**Response 201:** Full message object with auto-detected `sentiment`.

---

### POST /messages/{message_id}/generate-reply

Generate an AI-powered reply suggestion for a customer message.

**Auth:** Required

**Request:** No body required.

**Response 200:**
```json
{
  "reply": "Thank you for reaching out! We're sorry to hear you're experiencing login issues. Our team is actively investigating this problem. Please expect an update within 24 hours.",
  "generated_by": "groq"
}
```

**`generated_by` values:**
- `groq` — LLM-generated, personalized to the message content
- `rule-based` — Template based on message sentiment (fallback)

---

### POST /messages/{message_id}/generate-tickets

Generate and create Jira-style tickets from a customer message using AI.

**Auth:** Required

**Request:** No body required.

**Response 200:**
```json
{
  "tickets": [
    {
      "title": "Fix authentication error on login",
      "description": "Customer reports being unable to log in for 2 weeks. Error occurs despite correct credentials.",
      "priority": "High"
    }
  ],
  "created": 1
}
```

**Behavior:**
- Creates 1-3 tickets in the database (immediately visible in Kanban Board)
- Groq LLM used if API key configured; falls back to rule-based single ticket
- Ticket inherits `customer_name` from the message
- All tickets created with `status: Backlog`

---

## 9. Health

### GET /health

Health check endpoint. Used by load balancers, Docker health checks, and monitoring.

**Auth:** Not required

**Response 200:**
```json
{
  "status": "ok",
  "service": "MA Analytics API"
}
```

---

## 10. Response Headers

Every response includes:

| Header | Value | Description |
|--------|-------|-------------|
| `X-Request-ID` | `a1b2c3d4` (8-char hex) | Unique ID for this request — use for log correlation |
| `Content-Type` | `application/json` | Always JSON |

---

*Document Owner: Engineering / API Design*
*Last Updated: 2026-07*
*Status: v1.0 — All endpoints implemented and tested*
