# User Flows — MA Analytics

> *"User research is not about asking people what they want. It's about understanding what they're trying to accomplish, what's getting in their way, and designing a system that removes those obstacles so completely that people barely notice the tool exists."*

---

## 1. Overview

This document maps every major user journey through MA Analytics from entry point to outcome. Each flow is defined by:
- **Trigger** — What causes the user to initiate this flow
- **Entry point** — Where in the UI the flow begins
- **Steps** — The exact sequence of actions and system responses
- **Exit point** — Where the user lands when the flow succeeds
- **Error paths** — What happens when something goes wrong
- **Success metric** — How we know the flow worked

---

## 2. Core Flows

### Flow 1: New User Onboarding → First Insight

**User type:** First-time user, no existing account  
**Trigger:** User lands on the app for the first time  
**Goal:** See their first clustered insight from their app's reviews  
**Target time:** Under 10 minutes total

```
1. User visits app (login page)
      │
      ▼
2. Clicks "Registrieren"
      │
      ▼
3. Fills registration form: Email + Password (min 8 chars)
      │
      ▼
4. Submits form → JWT access token set as HTTP-only cookie
   User redirected to /datasources
      │
      ▼
5. Sees empty Data Sources page
   Empty state: "Verbinde deine erste App-Datenquelle"
   + "Google Play verbinden" button
      │
      ▼
6. Fills Google Play form:
   ├── Name: "BMW Connected"
   ├── App ID: "de.bmw.connected" OR full Play Store URL
   ├── Review count: 200 (default)
   └── Language: "de"
      │
      ▼
7. Clicks "Verbinden & Analysieren"
   System: creates DataSource, dispatches Celery pipeline task
      │
      ▼
8. UI shows pipeline progress (polling every 4 seconds):
   scraping → language detection → sentiment → embeddings → signals → clustering
      │
      ▼
9. Pipeline complete (~60-120 seconds)
   UI shows: "✓ Analyse abgeschlossen — 200 Reviews analysiert"
      │
      ▼
10. User navigates to /dashboard
    Dashboard renders: KPI row, sentiment bar, Top Issues, Top Strengths, AI narrative
```

**Error paths:**
- Email already registered → inline error "E-Mail bereits vergeben"
- App ID not found on Google Play → pipeline fails, error shown with retry button
- Pipeline timeout → `failed` status, "Erneut versuchen" button appears

**Success metric:** First insight visible in <10 minutes

---

### Flow 2: Innovation Brief Generation (Standard)

**User type:** PM or founder with existing data  
**Trigger:** User wants product ideas based on review signals  
**Goal:** Generate a structured product brief with AI  
**Target time:** Under 5 minutes (generation itself takes 5–15 seconds)

```
1. User navigates to /innovation (Innovation Lab)
      │
      ▼
2. Selects Mode:
   ├── "Wettbewerb" — find weaknesses in existing app categories to exploit
   └── "Innovation" — find unoccupied market gaps
      │
      ▼
3. Selects Scope:
   ├── "Alle" — aggregate signals across all connected apps
   ├── "Industrie" — filter by industry (e.g. "Automotive")
   └── "Datasource" — select specific app(s)
      │
      ▼
4. (Optional) Clicks "Signal-Steuerung" to expand signal panel
   ├── Review available signals (chips with mention counts)
   ├── Toggle individual chips to enable/disable
   ├── Or use "Alle" / "Keine" quick actions
   └── Badge shows: "auto" | "X aus" | "alle aktiv"
      │
      ▼
5. Clicks "Idee generieren"
      │
   ┌──┴──────────────────────────────────────────────────────────┐
   │ Backend:                                                    │
   │ 1. Signal exclusion (manual from UI OR auto from history)   │
   │ 2. Aggregate review_signals with exclusion applied          │
   │ 3. Compute co-occurrence signal graph                       │
   │ 4. Build prompt (signals + graph + previous concepts)       │
   │ 5. Claude Haiku → JSON brief (temperature 0.6)             │
   │ 6. Claude text → concept description (temperature 0.4)     │
   │ 7. Save to innovation_briefs table                         │
   │ 8. Return SavedBriefFull                                   │
   └─────────────────────────────────────────────────────────────┘
      │
      ▼
6. Brief appears in right panel history list (newest first)
   Auto-selects and displays the new brief
      │
      ▼
7. User reads:
   ├── Product name + tagline
   ├── Core problem (with data references)
   ├── Feature list (with mention counts + priorities)
   ├── Target audience
   ├── Market gap description
   ├── Differentiation
   └── Risk assessment + risk level badge
```

**Error paths:**
- Not enough data for scope → `422` error toast: "Nicht genug Daten für diesen Filter"
- AI rate limited → Groq fallback cascade; if all fail → error toast with retry
- JSON parse error → error toast (rare, retry usually succeeds)

**Success metric:** Brief generated and displayed in <20 seconds total round-trip

---

### Flow 3: Hypothesis-Guided Brief Generation

**User type:** PM or founder with a specific product hypothesis to validate  
**Trigger:** User has a hypothesis ("I think drivers want OTA updates without garage visits") and wants evidence  
**Goal:** Generate a brief where signals and reviews come from reviews semantically aligned with the hypothesis  
**Target time:** Under 2 minutes (backend adds ~2-5 seconds for embedding + vector search)

```
1. User is on /innovation, selects Mode + Scope as in Flow 2
      │
      ▼
2. Types hypothesis in "Ihre Hypothese" textarea:
   "Fahrer wollen Software-Updates ohne Werkstattbesuch und
    transparente Kommunikation über Update-Status"
      │
      ▼
3. (Optional) Adjusts Signal-Steuerung as in Flow 2
      │
      ▼
4. Clicks "Idee generieren"
      │
   ┌──┴──────────────────────────────────────────────────────────┐
   │ Backend (hypothesis path):                                  │
   │ 1. Embed hypothesis text (384-dim MiniLM vector)           │
   │ 2. pgvector cosine search → top 500 semantically           │
   │    similar reviews to hypothesis                           │
   │ 3. Aggregate signals FROM those 500 reviews only           │
   │ 4. Compute signal graph on those signals                   │
   │ 5. Enrich each signal with hypothesis-relevant reviews      │
   │    (sorted by cosine distance to hypothesis, not severity) │
   │ 6. Inject: retrieval_header "Hypothese-gesteuerte          │
   │    Signalauswahl" into prompt                              │
   │ 7. Generate brief + concept as normal                      │
   └─────────────────────────────────────────────────────────────┘
      │
      ▼
5. Brief includes:
   ├── hypothesis_check: "Die Hypothese wird durch X Reviews bestätigt..."
   ├── hypothesis_alignment: "stark" / "mittel" / "schwach"
   └── Review quotes sorted by semantic similarity to hypothesis
      │
      ▼
6. User reads brief and sees:
   ├── Evidence specifically from hypothesis-relevant reviews
   ├── Alignment assessment
   └── Signal sources that responded to the hypothesis
```

**Benefit over standard flow:** Instead of pulling signals from the full corpus (where dominant signals like "Updates" always rank first), the hypothesis filters the review pool to only the most semantically relevant reviews. The resulting signals are topic-specific rather than corpus-dominant.

**Error path:** If hypothesis text cannot be embedded (model unavailable), falls back to standard aggregation with a log warning.

---

### Flow 4: Concept Document Generation

**User type:** PM or founder who has a brief and wants a deep-dive document  
**Trigger:** User wants to extend a brief into a full strategic product document  
**Goal:** Generate a ~1200+ word structured product concept document  

```
1. User has a saved brief selected in the right panel
      │
      ▼
2. Clicks "Konzeptdokument" tab
      │
      ▼
3. If no concept exists:
   Shows "Konzept generieren" button + description of what will be generated
      │
      ▼
4. Clicks "Konzept generieren"
      │
   ┌──┴──────────────────────────────────────────────────────────┐
   │ POST /innovation/briefs/{id}/generate-concept               │
   │ Claude text generation, temperature 0.4                     │
   │ 9 sections: Executive Summary · Market Analysis ·           │
   │ Product Vision · Feature Details · Target Audience ·        │
   │ Differentiation · Risk Assessment · Go-to-Market · Roadmap  │
   └─────────────────────────────────────────────────────────────┘
      │
      ▼
5. Document renders as formatted markdown
   (headings, bullet lists, paragraphs)
      │
      ▼
6. "Konzept neu generieren" button appears for regeneration
```

---

### Flow 5: PDF Export

**User type:** PM, founder, investor presentation preparer  
**Trigger:** User wants to export a brief as a shareable PDF  
**Goal:** Download a formatted A4 PDF of the selected brief  

```
1. User has a saved brief selected in the right panel
      │
      ▼
2. Clicks "PDF Export" tab
      │
      ▼
3. Sees preview description of PDF structure:
   Header + product name + hypothesis validation + signal analysis +
   feature table + risk block + concept excerpt + data sources table
      │
      ▼
4. Clicks "PDF herunterladen"
      │
   ┌──┴──────────────────────────────────────────────────────────┐
   │ Client-side (no server call):                               │
   │ exportBriefPdf.ts → jsPDF                                   │
   │ Multi-page A4 document generated in browser                 │
   │ Font: Helvetica, layout: text-based (no screenshots)        │
   └─────────────────────────────────────────────────────────────┘
      │
      ▼
5. Browser prompts download: "TrustSync_Brief.pdf"
   (or auto-downloads depending on browser settings)
```

---

### Flow 6: Brief Copilot Chat

**User type:** PM or founder doing strategic exploration  
**Trigger:** User wants to ask follow-up questions about a generated brief  
**Goal:** Conversational deep-dive into the brief's strategic implications  

```
1. User has a saved brief selected in the right panel
      │
      ▼
2. Clicks "Copilot" button or chat icon
      │
      ▼
3. Right-side drawer opens:
   "Brief Copilot — Fragen Sie über [Product Name]"
      │
      ▼
4. User types question:
   "Was wäre ein realistischer Preis für dieses Produkt?"
      │
      ▼
5. System calls POST /innovation/briefs/{id}/chat
   with message + conversation history
   Claude responds with brief context injected into system prompt
      │
      ▼
6. AI reply renders in chat bubble
   User can continue conversation (full history maintained in frontend state)
      │
      ▼
7. User closes drawer → history preserved if user reopens in same session
```

---

### Flow 7: Data Source → Pipeline → Dashboard

**User type:** Any authenticated user  
**Trigger:** User wants to analyze a new Google Play app  
**Goal:** See analyzed signals and dashboard for the new app

```
1. Navigate to /datasources → Click "Google Play verbinden"
2. Fill form: Name + App ID + options
3. Submit → Celery pipeline starts, DataSource shows "running" status
4. Wait while polling shows progress every 4 seconds
5. Pipeline completes → status shows "done"
6. Navigate to Dashboard → select the new datasource from dropdown
7. Dashboard populates with signals, clusters, KPIs
```

**Error flow:** If pipeline fails → red "failed" badge + error message + "Erneut versuchen" button. Retry creates a new pipeline job without re-creating the DataSource.

---

### Flow 8: Document Intelligence — Upload and Query

**User type:** PM, analyst, compliance researcher  
**Trigger:** User has a PDF document (CSDDD, CSRD, regulation, competitor report) to index  
**Goal:** Ask semantic questions over the document content  

```
1. Navigate to /intelligence (Document Intelligence)
      │
      ▼
2. Click "Dokument hochladen"
      │
      ▼
3. Fill form:
   ├── Upload PDF file
   ├── Title: "CSDDD 2024 — Corporate Sustainability Due Diligence"
   ├── Type: "regulation"
   └── Year: 2024
      │
      ▼
4. System: POST /intelligence/upload
   ├── Extracts text per page
   ├── Chunks with overlap
   ├── Embeds each chunk (same 384-dim MiniLM model as reviews)
   └── Stores in intelligence_documents + intelligence_chunks tables
      │
      ▼
5. Document appears in list with status "indexed"
      │
      ▼
6. User types question:
   "Was sind die Kernpflichten für Unternehmen aus der CSDDD?"
      │
      ▼
7. System: POST /intelligence/query
   ├── Embeds question
   ├── pgvector cosine search → top K relevant chunks
   ├── Claude answers from retrieved context
   └── Returns answer + source page references
      │
      ▼
8. Answer displays with:
   ├── Full text answer
   └── Source citations: "Seite 12 — 'Unternehmen sind verpflichtet zu...'"
```

---

### Flow 9: Customer Message → AI Reply → Send

**User type:** Customer Success Manager, Founder  
**Trigger:** Customer complaint or inquiry  
**Goal:** Draft a response using AI assistance  

```
1. Navigate to /inbox
2. Click customer message in list
3. Detail panel shows message content + sentiment badge
4. Click "Antwort generieren"
5. System calls POST /messages/{id}/generate-reply
   → Claude/Groq drafts personalized response
6. Reply text appears in editable text area
7. User edits if needed
8. Copy text to clipboard → send via email client
   (or: "Senden" button → Resend API, Phase 2)
```

---

### Flow 10: Message → Ticket → Kanban

**User type:** Product Manager  
**Trigger:** Customer message contains actionable product issues  
**Goal:** Convert message into Kanban tickets  

```
1. User viewing customer message in Inbox
2. Click "Tickets erstellen"
3. System: POST /messages/{id}/create-ticket
   → AI parses message, identifies issues, creates 1-3 tickets
4. Toast: "3 Tickets erstellt"
5. User navigates to /tickets (Kanban)
6. New tickets appear in Backlog column with:
   ├── AI-suggested title and description
   └── AI-suggested priority (High/Medium/Low)
7. User moves tickets to appropriate status
```

---

### Flow 11: Hybrid Search

**User type:** PM or analyst doing deep research  
**Trigger:** User wants to find specific reviews about a topic  
**Goal:** Find the most relevant reviews using semantic + keyword search  

```
1. Navigate to /search
2. Type query: "Bluetooth verbindung verliert sich nach Update"
3. Select search type: Hybrid (default), Vector only, Fulltext only
4. (Optional) Filter by app, star rating, language
5. Click "Suchen"
6. Results render with:
   ├── Review text
   ├── Similarity score
   ├── App source
   ├── Star rating + sentiment
   └── Review date
7. User clicks review to expand full text
```

---

## 3. Error Flow Patterns

### Authentication Failure
```
Protected page → 401 (token expired)
  → apiClient interceptor detects 401
  → Redirect to /login
  → After login → returned to last intended page
```

Note: `login()` and `register()` use `authAxios` (no interceptors) to avoid redirect loops.

### All AI Providers Unavailable
```
Innovation brief generation fails after all Groq fallbacks exhausted
  → HTTP 429 returned
  → Error toast: "Alle KI-Anbieter sind momentan ausgelastet. Bitte später erneut versuchen."
  → "Erneut versuchen" button (no auto-retry)
```

### Pipeline Failure
```
Celery task fails (scraping blocked, model OOM, timeout)
  → datasource.job_status = "failed", error_message stored
  → UI shows: "⚠ Analyse fehlgeschlagen: [error_message]"
  → "Erneut versuchen" button creates new pipeline job
```

### Signal Exclusion Fallback
```
User's exclusion list leaves < 5 signals
  → Backend automatically re-runs aggregation without exclusion
  → Brief generated from full signal set
  → No error shown (silent fallback)
```

### Hypothesis Embedding Failure
```
ML model unavailable for hypothesis embedding
  → Falls back to standard (non-hypothesis) signal aggregation
  → Brief generated from full corpus without hypothesis filtering
  → Log warning, no user-visible error
```

---

## 4. Navigation Map

```
/login ───────────────────── Register → /register
  │
  └── (auth cookie set) ──────────────────────────────────────────┐
                                                                   │
/dashboard                                                         │
  ├── DataSource selector dropdown                                 │
  ├── KPI cards, sentiment bar                                     │
  ├── Top Issues cluster cards (expand/collapse)                   │
  ├── Top Strengths cluster cards                                  │
  ├── AI Insight paragraph                                         │
  └── (empty state) → /datasources                                │
                                                                   │
/datasources                                                       │
  ├── Data source cards with status badges                         │
  ├── "Google Play verbinden" form                                 │
  ├── "CSV hochladen" form                                         │
  ├── Pipeline progress polling                                    │
  └── Delete datasource → confirmation → deleted                  │
                                                                   │
/innovation  (Innovation Lab)                                      │
  ├── Mode selector (Wettbewerb / Innovation)                      │
  ├── Scope selector (Alle / Industrie / App)                      │
  ├── Hypothesis textarea (optional)                               │
  ├── Signal-Steuerung panel (collapsible)                         │
  │     └── Signal chips, Alle/Keine buttons, exclusion badge      │
  ├── "Idee generieren" button                                     │
  └── Brief history panel (right side)                            │
        └── Selected brief detail                                  │
              ├── Details tab (brief content)                      │
              ├── Konzeptdokument tab (long-form)                  │
              ├── PDF Export tab                                    │
              └── Copilot button → chat drawer                     │
                                                                   │
/search                                                            │
  ├── Query input + type selector + filters                        │
  └── Results list (review text + metadata + similarity)           │
                                                                   │
/inbox                                                             │
  ├── Message list (sentiment badge + preview)                     │
  ├── Message detail panel                                         │
  │     ├── "Antwort generieren" → editable reply text            │
  │     └── "Tickets erstellen" → creates Kanban tickets          │
  └── "Neue Nachricht" modal                                       │
                                                                   │
/tickets  (Kanban)                                                 │
  ├── 4 columns: Backlog / Todo / In Progress / Done              │
  ├── Ticket cards (title + priority badge)                        │
  ├── Ticket detail panel (right side)                             │
  │     ├── Edit title, description, status, priority             │
  │     └── Delete with confirmation                              │
  └── "Erstellen" form in Backlog column                          │
                                                                   │
/intelligence  (Document Intelligence)                             │
  ├── Document list (title, type, page count, status)             │
  ├── Upload PDF form                                              │
  ├── Question input → AI answer + source citations               │
  └── "Extraktion starten" → batch metric extraction              │
```

---

## 5. Edge Cases & Corner Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User generates briefs until all signals are excluded | Exclusion list leaves <5 signals → auto-fallback to no exclusion → brief generated from full corpus |
| User clicks "Alle" in Signal-Steuerung | All chips enabled, `userControlledSignals=true`, `excluded_signals=[]` sent to backend → no exclusion at all |
| User clicks "Keine" in Signal-Steuerung | All chips disabled → no signals → same fallback as above (empty list triggers no-exclusion fallback in backend) |
| User types hypothesis but then clears it | Hypothesis field becomes empty string → treated as no hypothesis → standard aggregation |
| Hypothesis language is English, reviews are German | Embedding model (paraphrase-multilingual-MiniLM-L12-v2) handles cross-lingual similarity; results are still meaningful |
| PDF export of brief with no concept document | PDF generates without concept section; concept section replaced by "Noch kein Konzeptdokument" notice |
| User deletes all briefs | History panel shows empty state; auto-exclusion has no briefs to exclude → no exclusion applied automatically |
| Two tabs open, brief generated in one | Other tab's history is stale until refresh; no real-time sync |
| CSV with 0 rows | 422 error: "CSV enthält keine Bewertungen" |
| Google Play app has 0 reviews in selected language | Pipeline completes but produces empty signal table; dashboard shows "0 Reviews" |
| Document intelligence query with no indexed documents | 422: "Keine Dokumente vorhanden" |

---

*Document Owner: Product / UX Research*  
*Last Updated: 2026-07*  
*Status: v1.0 — All flows implemented and tested*
