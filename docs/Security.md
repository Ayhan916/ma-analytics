# Security Specification — MA Analytics

> *"Security is not a feature you add at the end. It is a property of the system that must be designed in from the first line of code. The question is never 'how secure should we make this?' — the question is always 'what are we protecting, from whom, at what cost?' Answering that honestly determines everything."*

---

## 1. Security Model Overview

MA Analytics is a **single-tenant SaaS with strict data isolation**. Each user account has a completely separate logical data domain. The primary security concerns in order of severity:

1. **Data isolation** — User A must never access User B's data under any circumstances
2. **Authentication** — Credentials must be protected; sessions must be stateless and time-bounded
3. **Input validation** — All inputs are untrusted; validation happens at every layer
4. **Dependency security** — Third-party libraries are attack surface; they must be reviewed and pinned
5. **Secret management** — API keys (JWT secret, Anthropic, Groq, Resend), DB credentials must never appear in code or logs
6. **Infrastructure security** — Database and cache must not be directly accessible from the internet

---

## 2. Authentication Architecture

### 2.1 JWT-Based Stateless Authentication with HTTP-Only Cookies

MA Analytics uses **JSON Web Tokens (JWT)** stored as **HTTP-only cookies**. There is no server-side session store.

**Token structure:**
```json
Header: {"alg": "HS256", "typ": "JWT"}

Payload: {
  "sub": "3bd9dccc-36fb-4373-8f0f-19eef6ae56ed",  // user.id
  "exp": 1753228800  // Unix timestamp
}

Signature: HMAC-SHA256(base64url(header) + "." + base64url(payload), SECRET_KEY)
```

**Token types:**

| Token | Cookie Name | Lifetime | HttpOnly | SameSite |
|-------|------------|---------|---------|---------|
| Access token | `access_token` | 15 minutes | ✅ Yes | Strict |
| Refresh token | `refresh_token` | 7 days | ✅ Yes | Strict |

**Token refresh flow:**
1. `access_token` expires → API returns 401
2. `apiClient` interceptor detects 401 → calls `POST /auth/refresh` (using refresh token cookie)
3. Server issues new access token → sets new cookie
4. Retry original request
5. If refresh also returns 401 → redirect to `/login`

**Critical implementation note:** `login()` and `register()` must use `authAxios` (a separate axios instance with no interceptors). Using `apiClient` for auth endpoints would cause an infinite redirect loop when a 401 is returned during refresh.

**Why HTTP-only cookies over localStorage:**
- HTTP-only cookies are inaccessible to JavaScript — XSS attacks cannot steal them
- `SameSite: Strict` prevents CSRF attacks (cookie is never sent to third-party origins)
- Refresh token pattern enables seamless 7-day sessions without re-login
- The dual-instance axios pattern (`apiClient` with interceptors vs `authAxios` without) handles the logout loop edge case cleanly

### 2.2 Password Security

**Algorithm:** bcrypt with cost factor 12

**Why bcrypt:**
- Adaptive: cost factor can be increased as hardware improves
- GPU-resistant: memory-intensive, not parallelizable
- NIST SP 800-63B compliant

**Cost factor 12:** ~300ms hash time on a modern server. Makes offline brute-force attacks against stolen hashes impractical.

**Minimum length:** 8 characters, enforced server-side (client-side validation is UX, not security).

**Version pinning:** `bcrypt==4.0.1`. bcrypt ≥ 4.1 breaks passlib 1.7.4 compatibility — a known upstream issue, accepted and documented.

### 2.3 Protected Endpoint Pattern

Every protected endpoint uses `Depends(get_current_user)`:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user
```

This dependency:
1. Extracts the token from the `access_token` cookie
2. Validates signature and expiry
3. Loads the user from the database
4. Raises HTTP 401 if any step fails

The DB lookup confirms the user still exists on every request — necessary for future account deletion support.

---

## 3. Authorization & Data Isolation

### 3.1 User-Scoped Queries

**Rule:** Every query that returns user-sensitive data (datasources, reviews, signals, briefs, tickets, messages) MUST include `user_id == current_user.id` as a predicate.

```python
# CORRECT — always filter by current user
result = await db.execute(
    select(DataSource).where(DataSource.user_id == current_user.id)
)

# WRONG — never do this
result = await db.execute(
    select(DataSource).where(DataSource.id == datasource_id)
)
```

The Innovation Lab's `_aggregate_signals`, `_aggregate_signals_hypothesis`, `_compute_signal_graph`, and `_get_excluded_signals` functions all include the user scope via a `WHERE` clause that references `datasources.user_id = :uid`. This scope is injected as the `where` clause parameter and cannot be bypassed by request body manipulation.

### 3.2 Resource Ownership Validation

For operations on specific resources (DELETE, PATCH on specific IDs):

```python
# Load with ownership check in single query
result = await db.execute(
    select(DataSource).where(
        DataSource.id == datasource_id,
        DataSource.user_id == current_user.id  # ownership check
    )
)
if not result.scalar_one_or_none():
    raise HTTPException(status_code=404, detail="DataSource not found")
```

**Important:** Return 404 (not 403) when a resource exists but belongs to another user. This prevents user enumeration — an attacker cannot distinguish "doesn't exist" from "exists but not yours."

### 3.3 Public Endpoints

| Endpoint | Reason |
|----------|--------|
| `GET /health` | Load balancer health checks require no auth |
| `POST /auth/register` | Must be accessible before account creation |
| `POST /auth/login` | Must be accessible before token exists |
| `POST /auth/refresh` | Must be accessible to refresh expired access tokens |

**All other endpoints** require a valid access token.

---

## 4. Input Validation

### 4.1 Pydantic Schemas

All request bodies are validated by Pydantic v2 models before processing:

```python
class InnovationRequest(BaseModel):
    mode: str
    scope: str
    industry: Optional[str] = None
    datasource_ids: Optional[List[str]] = None
    market: Optional[str] = None
    user_hypothesis: Optional[str] = None
    excluded_signals: Optional[List[str]] = None  # null=auto, []=none, [...]= manual
```

Pydantic validates: type correctness, required fields, enum values. Business rules (e.g., "scope='industry' requires industry field") are validated at the service layer.

### 4.2 File Upload Validation (CSV, PDF)

```python
# Size check before processing
if file.size > 10 * 1024 * 1024:  # 10MB
    raise HTTPException(400, "File too large")

# Extension check
if not file.filename.endswith('.csv'):
    raise HTTPException(400, "Only CSV files accepted")
```

PDF uploads for Document Intelligence use a similar pattern with `.pdf` extension check.

### 4.3 SQL Injection Prevention

All database queries use **SQLAlchemy parameterized queries**. Raw SQL uses `text()` with named parameters:

```python
# SAFE — parameterized
sql = text("""
    SELECT feature, COUNT(*) AS total
    FROM review_signals rs
    JOIN datasources ds ON rs.datasource_id = ds.id
    WHERE ds.user_id = :uid
    GROUP BY feature
""")
await db.execute(sql, {"uid": current_user.id})

# UNSAFE — never do this
f"SELECT * FROM review_signals WHERE user_id = '{user_id}'"
```

The signal exclusion list in `_aggregate_signals` uses dynamic parameter binding, not f-strings:

```python
if exclude_features:
    keys = {f"excl_{i}": f for i, f in enumerate(exclude_features)}
    clause = "AND rs.feature NOT IN (" + ", ".join(f":{k}" for k in keys) + ")"
    params.update(keys)
```

### 4.4 User Hypothesis Validation

The `user_hypothesis` field is user-controlled text that gets embedded and used in SQL as a vector parameter. It is never directly interpolated into SQL. The embedding step produces a numeric vector; the SQL uses `CAST(:hyp_vec AS vector)` where `hyp_vec` is `str(list_of_floats)` — a controlled representation with no injection surface.

### 4.5 AI Prompt Injection Defense

User-provided content (hypotheses, chat messages) is included in AI prompts. Mitigations:
- Hypothesis text is only used for vector embedding, not directly in the main generation prompt
- Chat messages are clearly delimited as user content vs. system context
- Brief generation uses `HIER_ECHTER_PRODUKTNAME` style placeholders in the schema definition to prevent the model from copying instruction text as output
- The JSON schema is fixed and returned content is validated structurally before persistence

---

## 5. Rate Limiting

Rate limiting via `slowapi` (FastAPI wrapper around `limits`).

### 5.1 Current Limits

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /auth/register` | 10/minute per IP | Prevent account creation floods |
| `POST /auth/login` | 20/minute per IP | Prevent credential stuffing |
| All other endpoints | 200/minute per IP | General API abuse prevention |

### 5.2 Rate Limit Response

```http
HTTP/1.1 429 Too Many Requests
{"error": "Rate limit exceeded: 10 per 1 minute"}
```

### 5.3 AI Provider Rate Limits

The Innovation Lab handles external AI rate limits separately:

- `_is_rate_limit(exc)` checks for `"429"`, `"rate_limit"`, `"overloaded"` in exception strings
- Claude 429 → automatic Groq cascade fallback (no user-visible delay)
- Groq key 1 exhausted → switch to Groq key 2
- All providers exhausted → HTTP 429 returned to client with human-readable message

---

## 6. Transport Security

### 6.1 HTTPS Enforcement (Production)

All production traffic must use TLS 1.2+. HTTP requests redirect to HTTPS.

```nginx
server {
    listen 80;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    add_header Strict-Transport-Security "max-age=31536000" always;
}
```

### 6.2 CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # from .env, never "*" in production
    allow_credentials=True,  # required for HTTP-only cookie transmission
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Development:** `ALLOWED_ORIGINS=["http://localhost:3002"]`  
**Production:** `ALLOWED_ORIGINS=["https://your-domain.com"]`

`allow_credentials=True` is required because the frontend transmits cookies with every request. Without it, the browser strips cookies from cross-origin requests.

**Never use `"*"` with `allow_credentials=True`** — this combination is rejected by browsers and would expose all cookies to any origin.

### 6.3 Security Headers (Phase 2)

```nginx
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 7. Secret Management

### 7.1 Environment Variables

All secrets are loaded via `pydantic-settings` from `.env`. **No secrets are hardcoded.**

**Required secrets:**
```bash
# JWT signing key — generate with: openssl rand -hex 32
SECRET_KEY=<64-character-hex-string>

# Database connection (never expose publicly)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5434/dbname

# AI providers (at least one required for Innovation Lab)
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GROQ_API_KEY_2=gsk_...   # optional second key for fallback rotation

# Email (required for password reset)
RESEND_API_KEY=re_...
```

**Optional:**
```bash
# Override default Claude model
ANTHROPIC_MODEL=claude-haiku-4-5-20251001

# Frontend
VITE_API_URL=http://localhost:8000
```

### 7.2 Secret Generation

```bash
# Generate SECRET_KEY (256-bit entropy)
openssl rand -hex 32

# Never use:
# SECRET_KEY=changeme
# SECRET_KEY=secret
# Any default or reused value
```

### 7.3 .gitignore Rules

```
.env
.env.local
.env.production
*.key
*.pem
```

`.env` must never be committed. The repository contains `.env.example` with placeholder values.

### 7.4 Secrets in Logs

structlog is configured to never log:
- JWT tokens or cookie values
- Passwords (even hashed)
- `SECRET_KEY`, `DATABASE_URL`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `RESEND_API_KEY`
- IP addresses (used for rate limiting only, not persisted)

Logged per request: `request_id` (X-Request-ID), `method`, `path`, `status`, `duration_ms`, `user_id` (never email).

---

## 8. Threat Model

### 8.1 Threat Actors

| Actor | Capability | Primary Threat |
|-------|-----------|----------------|
| External attacker | Public internet access | Credential stuffing on /auth/login, session hijacking |
| Competitor | Targeted | Review data exfiltration via authenticated API |
| Malicious insider | Has account | Access to other users' Innovation Briefs |
| Automated bot | High request volume | API abuse, Celery queue flooding |
| Prompt injector | User input field | Manipulating AI outputs via hypothesis or chat input |

### 8.2 Threat Analysis (STRIDE)

| Category | Threat | Mitigation |
|----------|--------|-----------|
| **Spoofing** | Impersonate another user | JWT signature verification; user_id from token only, never from request body |
| **Tampering** | Modify database records | Parameterized queries; ownership check on every mutation |
| **Tampering** | Inject malicious SQL via hypothesis | Hypothesis is only embedded, never SQL-interpolated |
| **Repudiation** | Deny performing action | structlog records user_id + X-Request-ID for every request |
| **Info Disclosure** | Access another user's data | user_id filter on every query; 404 on unauthorized access (not 403) |
| **Info Disclosure** | Steal session cookie | HTTP-only + SameSite:Strict; inaccessible to XSS; HTTPS required |
| **Info Disclosure** | Steal Anthropic/Groq API keys | Keys only in .env, never logged, never returned by any endpoint |
| **Info Disclosure** | User enumeration | 401 for both "wrong email" and "wrong password" — same error message |
| **Denial of Service** | Flood Celery queue with pipeline jobs | Rate limiting + per-user datasource quota (enforced by DB) |
| **Denial of Service** | Exhaust AI provider quota | Rate limiting; Groq fallback; hard 429 when all exhausted |
| **Elevation of Privilege** | Gain admin access | No admin role in v1.0; all users are equal |
| **Prompt Injection** | Manipulate brief generation via hypothesis | Hypothesis used for embedding only; not directly in generation prompt |

### 8.3 Known Limitations (Accepted Risks)

| Risk | Severity | Accepted? | Rationale |
|------|----------|-----------|-----------|
| No token revocation before expiry | Medium | ✅ Yes | 15-minute access token window is short; refresh tokens can be invalidated in Phase 2 |
| No 2FA | Medium | ✅ Yes | Phase 2 — TOTP support planned |
| No audit log | Medium | ⚠️ Deferred | Phase 3 — needed for enterprise; not blocking for v1.0 |
| passlib 1.7.4 unmaintained | Low | ✅ Yes | No active CVEs; replacement with argon2-cffi tracked for Phase 2 |
| No security headers | Low | ⚠️ Deferred | Phase 2; HSTS + CSP + X-Frame-Options ready to add |
| Celery task loss on Redis crash | Low | ✅ Yes | User can retry; tasks are idempotent |

---

## 9. Dependency Security

### 9.1 Pinned Dependencies

All dependencies are pinned to exact versions:

```
# requirements.txt
fastapi==0.115.0
sqlalchemy==2.0.35
bcrypt==4.0.1          # pinned — see password security notes
anthropic>=0.120.0
groq==1.0.0
sentence-transformers==2.7.0
torch==2.4.1
```

```json
// package.json
"react": "^18.3.1",
"typescript": "^5.5.3",
"vite": "^6.0.0"
```

### 9.2 Dependency Review Process

**Current:** Manual review when adding new dependencies.

**Phase 2 (CI):**
- `pip audit` — Python dependencies vs. PyPI advisory database
- `npm audit` — Node dependencies vs. npm advisory database
- Run on every PR before merge

### 9.3 Known Dependency Notes

| Package | Issue | Status |
|---------|-------|--------|
| passlib 1.7.4 | Unmaintained since 2020 | ⚠️ Accepted — no active CVEs; replace with `argon2-cffi` in Phase 2 |
| bcrypt 4.0.1 | Pinned below latest due to passlib compat | ✅ Documented — acceptable constraint |

---

## 10. GDPR Compliance

### 10.1 Data Processed

| Data Type | Source | Purpose | Legal Basis |
|-----------|--------|---------|-------------|
| User email | Registration | Authentication | Contract |
| User password (bcrypt hash) | Registration | Authentication | Contract |
| App reviews | Google Play public data | Product analysis | Legitimate interest |
| Customer messages | User-provided | Inbox feature | Contract |
| Innovation Briefs | AI-generated + user data | Core product | Contract |

### 10.2 Data Retention

- User + associated data: retained until account deletion (`DELETE /auth/me` — Phase 1.5)
- Reviews/clusters/signals: retained until datasource deletion
- Innovation Briefs: retained until manually deleted or account deletion
- Pipeline job logs: no PII, retained indefinitely

### 10.3 Right to Erasure (GDPR Art. 17)

**Current status:** Datasource cascade-delete removes reviews, signals, clusters, jobs. Innovation briefs can be deleted manually. No account deletion endpoint yet.

**Phase 1.5 requirement:** `DELETE /auth/me`:
1. Sends confirmation email (Resend)
2. User confirms via email link
3. Cascade deletes: user → datasources → reviews → review_signals → review_sentences → review_aspects → clusters → innovation_briefs → messages → tickets → intelligence_documents → intelligence_chunks → pipeline_jobs

### 10.4 Data Minimization

- No PII stored beyond email + hashed password + explicitly user-provided data
- Customer message names/emails only if user explicitly provides them
- IP addresses not persisted (rate limiting only, in-memory)
- No analytics tracking, no third-party cookies, no pixel tracking

---

## 11. Security Checklist (Pre-Launch)

### OWASP Top 10 Review

| # | Vulnerability | Status |
|---|--------------|--------|
| A01 | Broken Access Control | ✅ Mitigated — user_id filter on every query; 404 on unauthorized |
| A02 | Cryptographic Failures | ✅ Mitigated — bcrypt, HS256 JWT, HTTP-only cookies, TLS in prod |
| A03 | Injection | ✅ Mitigated — SQLAlchemy parameterized; dynamic exclusion lists use named params |
| A04 | Insecure Design | ✅ Mitigated — threat model reviewed; ownership checks on mutations |
| A05 | Security Misconfiguration | ⚠️ CORS set, docs hidden in prod; security headers are Phase 2 |
| A06 | Vulnerable Components | ⚠️ passlib unmaintained; `pip audit` in Phase 2 CI |
| A07 | Auth & Session Failures | ✅ Mitigated — JWT 15min, HTTP-only cookies, bcrypt, rate limiting |
| A08 | Software & Data Integrity | ⚠️ Pinned deps; no automated scanning yet |
| A09 | Logging & Monitoring | ✅ structlog JSON logging; Sentry alerting is Phase 4 |
| A10 | Server-Side Request Forgery | ✅ Not applicable — no user-controlled URL fetching |

### Pre-Production Checklist

- [ ] `SECRET_KEY` generated with `openssl rand -hex 32` (not a default)
- [ ] Database password is strong (≥24 chars, randomly generated)
- [ ] HTTPS enforced with valid TLS certificate
- [ ] `ALLOWED_ORIGINS` set to production domain only (never `*`)
- [ ] `DEBUG=false` in production (API docs hidden, no stack traces in responses)
- [ ] `.env` file not in repository
- [ ] Redis not exposed on public port
- [ ] PostgreSQL not exposed on public port
- [ ] `ANTHROPIC_API_KEY` and `GROQ_API_KEY` are production keys (not test keys)
- [ ] Security headers configured in Nginx/Caddy
- [ ] Rate limiting verified with curl (`curl -X POST /auth/login` 25 times)
- [ ] HTTP-only cookie set confirmed in browser DevTools (not visible in document.cookie)

---

*Document Owner: Engineering / Security Architecture*  
*Last Updated: 2026-07*  
*Status: v1.0 — Production-ready security posture; Phase 2 items tracked above*
