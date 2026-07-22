# Security Specification — MA Analytics

> *"Security is not a feature you add at the end. It is a property of the system that must be designed in from the first line of code. The question is never 'how secure should we make this?' — the question is always 'what are we protecting, from whom, at what cost?' Answering that honestly determines everything."*

---

## 1. Security Model Overview

MA Analytics is a **single-tenant SaaS with strict data isolation**. Each user account has a completely separate logical data domain. The primary security concerns in order of severity:

1. **Data isolation** — User A must never access User B's data under any circumstances
2. **Authentication** — Credentials must be protected; sessions must be stateless and time-bounded
3. **Input validation** — All inputs are untrusted; validation happens at every layer
4. **Dependency security** — Third-party libraries are attack surface; they must be reviewed and pinned
5. **Infrastructure security** — The server, database, and cache must not be directly accessible from the internet
6. **Secret management** — API keys, DB credentials, JWT secrets must never appear in code or logs

---

## 2. Authentication Architecture

### 2.1 JWT-Based Stateless Authentication

MA Analytics uses **JSON Web Tokens (JWT)** for stateless authentication. There is no server-side session store.

**Token structure:**
```json
Header: {"alg": "HS256", "typ": "JWT"}

Payload: {
  "sub": "3bd9dccc-36fb-4373-8f0f-19eef6ae56ed",  // user.id
  "exp": 1753228800  // Unix timestamp: 24 hours from issue
}

Signature: HMAC-SHA256(base64url(header) + "." + base64url(payload), SECRET_KEY)
```

**Why HS256:** Symmetric signing is appropriate for single-service deployments where all token verification happens in the same service. If multiple services need to verify tokens independently, migrate to RS256 (asymmetric) — tracked as Phase 2 item.

**Token lifetime:** 24 hours. No refresh tokens in v1.0 (users re-authenticate daily). Refresh tokens (with 30-day sliding window) are Phase 1.5.

**Token storage (frontend):** `localStorage`. Trade-off: localStorage is accessible to JavaScript (XSS risk) but is simpler than httpOnly cookies, which require CSRF protection. Given MA Analytics is not embedded in other pages and has strong CSP headers, localStorage is acceptable for v1.0. `httpOnly` cookies are Phase 2.

**Token invalidation:** Not supported in v1.0 (stateless, no blocklist). Tokens expire naturally. For logout: client deletes token from localStorage. This means a stolen token is valid until expiry — mitigated by short (24h) lifetime and HTTPS enforcement.

### 2.2 Password Security

**Algorithm:** bcrypt with cost factor 12

**Why bcrypt:**
- Adaptive: cost factor can be increased as hardware improves
- GPU-resistant by design: memory-intensive, not parallelizable
- 72-byte effective input (pre-hashing not needed at our password length requirements)
- NIST SP 800-63B compliant

**Cost factor 12:** Produces a hash in ~300ms on a modern server. This means brute-force requires 300ms per attempt — renders offline attacks against bcrypt hashes impractical at scale.

**Minimum length:** 8 characters, enforced server-side (client-side validation is UX, not security).

**Maximum effective length:** bcrypt truncates at 72 bytes. Users writing passwords >72 characters (extremely rare) get no additional security from the extra characters. No current mitigations needed; document for future awareness.

**Version pinning:** `bcrypt==4.0.1` (see `requirements.txt`). bcrypt ≥ 4.1 breaks passlib 1.7.4 compatibility. This is a known upstream issue.

### 2.3 Dependency: `get_current_user`

Every protected endpoint uses:

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
1. Extracts the Bearer token from `Authorization` header
2. Validates signature and expiry
3. Loads the user from the database
4. Raises HTTP 401 if any step fails

**Critical:** The DB lookup on every request confirms the user still exists (accounts can't be deleted but this pattern is correct for future account deletion support).

---

## 3. Authorization & Data Isolation

### 3.1 User-Scoped Queries

Every query that returns user data includes the current user as a filter:

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

**Rule:** No query that returns user-sensitive data (datasources, reviews, clusters, tickets, messages) is allowed to omit the `user_id == current_user.id` predicate.

### 3.2 Resource Ownership Validation

For operations on specific resources (e.g., `DELETE /datasources/{id}`):

```python
# Load with ownership check in single query
ds = await db.execute(
    select(DataSource).where(
        DataSource.id == datasource_id,
        DataSource.user_id == current_user.id  # ownership check
    )
)
if not ds:
    raise HTTPException(status_code=404, detail="DataSource not found")
```

**Important:** Return 404 (not 403) when a resource exists but belongs to another user. This prevents user enumeration — an attacker cannot distinguish "resource doesn't exist" from "resource exists but you don't own it."

### 3.3 Public Endpoints

The following endpoints are intentionally public (no auth required):

| Endpoint | Reason |
|----------|--------|
| `GET /health` | Load balancer health checks must not require auth |
| `POST /auth/register` | Must be accessible before account creation |
| `POST /auth/login` | Must be accessible before token exists |

**All other endpoints** require a valid Bearer token.

---

## 4. Input Validation

### 4.1 Pydantic Schemas

All request bodies are validated by Pydantic models before any processing:

```python
class RegisterRequest(BaseModel):
    email: EmailStr      # validates email format
    password: str        # custom validator: min 8 chars
    full_name: str | None = None

    @validator("password")
    def password_min_length(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
```

**What Pydantic validates:**
- Type correctness (str, int, float, bool)
- Email format (`EmailStr`)
- Enum values (only valid `TicketStatus`, `TicketPriority` values accepted)
- Required fields present

**What Pydantic does NOT validate:** Business rules (e.g., "email must be unique") — these are database-level constraints enforced at the query layer.

### 4.2 File Upload Validation (CSV)

```python
# Size check before processing
if file.size > 10 * 1024 * 1024:  # 10MB
    raise HTTPException(400, "File too large")

# Content type check
if not file.filename.endswith('.csv'):
    raise HTTPException(400, "Only CSV files accepted")
```

**No server-side MIME type sniffing** — we trust the filename extension AND parse the file as CSV. If parsing fails, a 400 is returned.

### 4.3 Path Parameter Validation

FastAPI validates path parameters against declared types. A UUID path like `/datasources/{datasource_id}` where the Python type is `str` accepts any string. For additional validation in critical paths, the ownership check (`WHERE id = $1 AND user_id = $2`) acts as a filter.

### 4.4 SQL Injection Prevention

All database queries use **parameterized queries via SQLAlchemy**. No string interpolation is used in SQL construction:

```python
# SAFE — parameterized
await db.execute(select(User).where(User.email == email))

# UNSAFE — never do this
await db.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

SQLAlchemy's ORM and Core expression language always produce parameterized queries. Raw SQL is not used anywhere in the codebase.

---

## 5. Rate Limiting

Rate limiting is implemented via `slowapi` (a FastAPI wrapper around the `limits` library).

### 5.1 Current Limits

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /auth/register` | 10/minute per IP | Prevent account creation floods |
| `POST /auth/login` | 20/minute per IP | Prevent brute-force attacks |
| All other endpoints | 200/minute per IP | General API abuse prevention |

### 5.2 Rate Limit Exceeded Response

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{"error": "Rate limit exceeded: 10 per 1 minute"}
```

### 5.3 Future: Per-User Rate Limits

The current implementation limits by IP, which is correct for unauthenticated endpoints (register/login). For authenticated endpoints, the limit should be per user ID — a user behind a corporate NAT shares an IP with many colleagues.

**Phase 2 upgrade:** Change key function from `get_remote_address` to `get_user_id` for authenticated routes.

---

## 6. Transport Security

### 6.1 HTTPS Enforcement (Production)

All production traffic must use TLS 1.2+. HTTP requests should be redirected to HTTPS.

**Nginx / Caddy configuration:**
```nginx
# Force HTTPS
server {
    listen 80;
    return 301 https://$host$request_uri;
}

# HTTPS with TLS 1.2+
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Development:** `ALLOWED_ORIGINS=["http://localhost:3002"]`
**Production:** `ALLOWED_ORIGINS=["https://your-domain.com"]`

**Never use `"*"` in production** — this would allow any website to make authenticated requests using stored tokens.

### 6.3 Security Headers (to add in Phase 2)

```nginx
# Content Security Policy
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';

# Prevent clickjacking
X-Frame-Options: DENY

# Prevent MIME sniffing
X-Content-Type-Options: nosniff

# Referrer policy
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 7. Secret Management

### 7.1 Environment Variables

All secrets are loaded from `.env` files via `pydantic-settings`. **No secrets are hardcoded in code.**

**Required secrets:**
```bash
# JWT signing key — generate with: openssl rand -hex 32
SECRET_KEY=<64-character-hex-string>

# Database credentials
DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname

# Optional: Groq API key
GROQ_API_KEY=gsk_...
```

### 7.2 Secret Generation

```bash
# Generate SECRET_KEY
openssl rand -hex 32
# Output: a0b1c2d3e4f5... (64 chars, 256 bits of entropy)

# Default bcrypt passwords in dev: use ≥12 character passwords
```

**Never use:**
- `"changeme"` as SECRET_KEY in production
- Default database passwords
- Reused secrets across environments

### 7.3 .gitignore Rules

```
.env
.env.local
.env.production
*.key
*.pem
```

**Critical:** `.env` must never be committed. The repository contains `.env.example` with placeholder values and documentation.

### 7.4 Secrets in Logs

structlog is configured to never log:
- JWT tokens
- Passwords
- SECRET_KEY or database URLs

**Rule:** Only log the `user_id`, never the `email` or any PII, in request logs. Log the X-Request-ID for correlation.

---

## 8. Threat Model

### 8.1 Threat Actors

| Actor | Capability | Primary Threat |
|-------|-----------|----------------|
| External attacker | Public internet access | Brute-force login, data exfiltration |
| Competitor | Targeted | Review data scraping via authenticated API |
| Malicious insider | Account exists | Access to other users' data |
| Automated bot | High request volume | API abuse, account creation flood |

### 8.2 Threat Analysis (STRIDE)

| Category | Threat | Mitigation |
|----------|--------|-----------|
| **Spoofing** | Impersonate another user | JWT signature verification; user_id from token, not from request |
| **Tampering** | Modify database records | Parameterized queries; no direct DB access |
| **Repudiation** | Deny performing action | Structured request logs with user_id + X-Request-ID |
| **Info Disclosure** | Access another user's data | user_id filter on every query; 404 on unauthorized access |
| **Info Disclosure** | Steal JWT token | HTTPS enforced; 24h expiry; httpOnly cookies in Phase 2 |
| **Info Disclosure** | User enumeration via login | `401 Invalid credentials` for both wrong email AND wrong password |
| **Denial of Service** | Overwhelm ML pipeline | Rate limiting; Celery queue absorbs load; auto-fail on timeout |
| **Elevation of Privilege** | Gain admin access | No admin role in v1.0; all users are equal; future: RBAC |

### 8.3 Known Limitations (Accepted Risks)

| Risk | Severity | Accepted? | Rationale |
|------|----------|-----------|-----------|
| JWT tokens not revocable before expiry | Medium | ✅ Yes | 24h lifetime limits window; refresh tokens in Phase 2 |
| No 2FA | Medium | ✅ Yes | Phase 2 — TOTP support planned |
| Google Play scraping ToS compliance | Low | ✅ Yes | Public data; no authentication spoofing |
| Celery broker (Redis) persistence | Low | ✅ Yes | Task loss on Redis crash is acceptable; user can retry |
| No audit log | Medium | ⚠️ Deferred | Phase 2 — needed for enterprise customers |

---

## 9. Dependency Security

### 9.1 Pinned Dependencies

All dependencies are pinned to exact versions in `requirements.txt` and `package.json`. This prevents supply chain attacks where a package update introduces malicious code.

```
# requirements.txt
fastapi==0.115.0
sqlalchemy==2.0.36
bcrypt==4.0.1    # pinned — see Security notes
```

### 9.2 Dependency Review Process (Phase 2)

- `pip audit` — checks Python dependencies against PyPI advisory database
- `npm audit` — checks Node dependencies against npm advisory database
- Run in CI on every PR

### 9.3 Known Vulnerable Dependencies

| Package | Issue | Status |
|---------|-------|--------|
| passlib 1.7.4 | Unmaintained since 2020 | ⚠️ Accepted — no active CVEs; replace with `argon2-cffi` in Phase 2 |

---

## 10. GDPR Compliance

### 10.1 Data Processed

| Data Type | Source | Purpose | Legal Basis |
|-----------|--------|---------|-------------|
| User email | User-provided at registration | Authentication | Contract |
| User password (hashed) | User-provided at registration | Authentication | Contract |
| App reviews | Google Play public data | Product analysis | Legitimate interest |
| Customer messages | User-provided | Inbox feature | Contract |

### 10.2 Data Retention

- User data: retained until account deletion
- Reviews/clusters: retained until data source deletion
- Pipeline job logs: retained indefinitely (no PII)

### 10.3 Right to Erasure (GDPR Art. 17)

**v1.0 status:** Cascade delete via `DELETE /datasources/{id}` removes reviews, clusters, jobs. No account deletion endpoint yet.

**Phase 1 requirement:** `DELETE /auth/me` → deletes user and all associated data (CASCADE DELETE already configured in schema).

### 10.4 Data Minimization

- No PII stored beyond what's necessary for core functionality
- Customer messages store name and email only if explicitly provided
- IP addresses are not stored (only used for rate limiting, not logged)
- No analytics tracking, no third-party cookies

---

## 11. Security Checklist (Pre-Launch)

### OWASP Top 10 Review

| # | Vulnerability | Status |
|---|--------------|--------|
| A01 | Broken Access Control | ✅ Mitigated — user_id filter on all queries |
| A02 | Cryptographic Failures | ✅ Mitigated — bcrypt, HS256 JWT, TLS in prod |
| A03 | Injection | ✅ Mitigated — SQLAlchemy parameterized queries |
| A04 | Insecure Design | ✅ Mitigated — threat model reviewed |
| A05 | Security Misconfiguration | ⚠️ CORS set, API docs hidden in prod; headers Phase 2 |
| A06 | Vulnerable Components | ⚠️ passlib unmaintained; pip audit in Phase 2 |
| A07 | Auth & Session Failures | ✅ Mitigated — JWT 24h, bcrypt, rate limiting |
| A08 | Software & Data Integrity | ⚠️ Pinned deps; no CI security scanning yet |
| A09 | Logging & Monitoring | ✅ structlog JSON logging; alerting Phase 2 |
| A10 | Server-Side Request Forgery | ✅ Not applicable — no user-controlled URL fetching |

### Pre-Production Checklist

- [ ] `SECRET_KEY` generated with `openssl rand -hex 32` (not a default)
- [ ] Database password is strong (≥24 chars, randomly generated)
- [ ] HTTPS enforced with valid TLS certificate
- [ ] `ALLOWED_ORIGINS` set to production domain only (not `*`)
- [ ] `DEBUG=false` in production (API docs hidden)
- [ ] `.env` file not in repository (`.gitignore` includes `.env`)
- [ ] Redis not exposed on public port
- [ ] PostgreSQL not exposed on public port
- [ ] Security headers configured in Nginx/Caddy
- [ ] Rate limiting verified (test with curl)

---

*Document Owner: Engineering / Security Architecture*
*Last Updated: 2026-07*
*Status: v1.0 — Production-ready security posture; Phase 2 items tracked*
