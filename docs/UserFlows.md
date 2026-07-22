# User Flows — MA Analytics

> *"User research is not about asking people what they want. It's about understanding what they're trying to accomplish, what's getting in their way, and designing a system that removes those obstacles so completely that people barely notice the tool exists."*

---

## 1. Overview

This document maps every user journey through MA Analytics from entry to outcome. Each flow is defined by:
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
2. Clicks "Registrieren" (Register)
      │
      ▼
3. Fills registration form
   ├── Full name (optional)
   ├── Email address
   └── Password (min 8 chars)
      │
      ▼
4. Submits form
      │
   ┌──┴──┐
   │ ERROR PATHS:                           │
   │ • Email already registered → show       │
   │   "Email already in use" inline        │
   │ • Password too short → show inline     │
   │   validation before submission         │
   │ • Network error → show generic error   │
   │   with retry                           │
   └────────────────────────────────────────┘
      │ SUCCESS
      ▼
5. JWT token stored in localStorage
   User redirected to /datasources
      │
      ▼
6. Sees empty Data Sources page
   Empty state: "Verbinde deine erste App-Datenquelle"
   + "Google Play verbinden" button (prominent)
      │
      ▼
7. Clicks "Google Play verbinden"
   → Form slides in (or modal opens)
      │
      ▼
8. Fills Google Play form:
   ├── Name: "BMW Connected"
   ├── App ID: "de.bmw.connected" OR full Play Store URL
   │   (URL auto-parsed: play.google.com/store/apps/details?id=X)
   ├── Review count: 200 (default, dropdown: 50/100/200/500)
   ├── Language: "de" (dropdown)
   └── Country: "de" (dropdown)
      │
      ▼
9. Clicks "Verbinden & Analysieren"
      │
      ▼
10. System:
    ├── Creates DataSource record
    ├── Creates PipelineJob (status: pending)
    ├── Dispatches Celery task
    └── Returns job_id
      │
      ▼
11. UI shows pipeline progress indicator:
    ├── "Scraping reviews from Google Play..." (spinner)
    ├── Progress updates every 4 seconds via polling
    └── Stages: scraping → saving → sentiment → embeddings → clustering
      │
      ▼
12. [30-120 seconds later] Pipeline complete
    PipelineJob.status = "done"
    UI detects completion on next poll
      │
      ▼
13. UI shows success state:
    "✓ Analyse abgeschlossen — 200 Reviews analysiert"
    + "Zum Dashboard" button
      │
      ▼
14. User clicks "Zum Dashboard"
    Redirected to /dashboard
    DataSource auto-selected (only one exists)
      │
      ▼
15. Dashboard renders:
    ├── KPI row: 200 reviews | Ø 2.8★ | 40% positive | 45% negative
    ├── Sentiment bar (green/grey/red)
    ├── Top Issues (3-5 cards)
    ├── Top Strengths (3-5 cards)
    └── AI Insight paragraph
```

**Exit point:** User is on Dashboard, seeing their first insight
**Success metric:** User completed flow in <10 minutes AND saw at least 1 cluster

---

### Flow 2: Returning User — Daily Review Check

**User type:** Active user, existing data sources
**Trigger:** Monday morning — user wants to check if anything changed
**Goal:** Quickly assess current customer sentiment, identify new issues
**Target time:** Under 5 minutes

```
1. User navigates to app (auto-logged in if token valid)
      │
      ▼
2. Lands on Dashboard (last page visited, or /dashboard as default)
      │
      ▼
3. Selects data source from dropdown
   (If only one source: auto-selected)
      │
      ▼
4. Scans KPI row:
   ├── Are numbers better or worse than last week?
   └── Note the average rating trend
      │
      ▼
5. Reads AI Insight paragraph
      │
   ┌──┴──────────────────────────┐
   │ BRANCH A: No new concerns   │
   │ User closes app — done      │
   └─────────────────────────────┘
      │
   ┌──┴──────────────────────────┐
   │ BRANCH B: Sees an issue     │
   │ cluster with high mentions  │
   └─────────────────────────────┘
      │
      ▼
6. Clicks on top issue cluster card
   Card expands → shows example quotes
      │
      ▼
7. Reads quotes → confirms issue is real
      │
      ▼
8. Navigates to Kanban (/tickets)
      │
      ▼
9. Creates ticket from issue:
   ├── Title: based on cluster label
   ├── Description: pastes example quote
   ├── Priority: High
   └── Clicks "Erstellen"
      │
      ▼
10. Ticket appears in Backlog column
    User assigns it or leaves in Backlog for review
```

**Exit point:** Kanban board with new ticket created
**Success metric:** Daily check completed in <5 minutes

---

### Flow 3: CSV Upload (Non-Google-Play Data)

**User type:** User with reviews from app store reviews export, survey data, or support tickets in CSV format
**Trigger:** User has data that isn't on Google Play (Apple App Store, Trustpilot export, survey CSV)
**Goal:** Analyze the custom dataset through the same ML pipeline

```
1. User navigates to /datasources
      │
      ▼
2. Clicks "CSV hochladen"
      │
      ▼
3. CSV upload area appears:
   ├── Drag-and-drop zone
   └── "Datei auswählen" fallback button
      │
      ▼
4. User prepares CSV (or uses existing export):
   Required column: review text
   Optional columns: rating (1-5), date, version
      │
      ▼
5. User drags CSV onto drop zone OR clicks to select file
   ├── File validates: is it a .csv? Is it <10MB?
   │   ERROR: "Nur CSV-Dateien unter 10MB erlaubt"
   └── File accepted: filename shown with ✓
      │
      ▼
6. User fills in form fields:
   ├── Name: "App Store Reviews Q1 2025"
   ├── Text column: "content" (default) OR custom column name
   │   If user's CSV uses "review_text", they type "review_text"
   ├── Score column: "score" (default, optional)
   └── Date column: "at" (default, optional)
      │
      ▼
7. Clicks "Hochladen & Analysieren"
      │
      ▼
8. System:
   ├── Parses CSV rows
   ├── Maps columns according to user config
   ├── Stores Review records
   └── Dispatches run_pipeline task (no scraping needed)
      │
      ▼
9. Pipeline runs (same as Google Play flow, steps 11-15)
   Completes faster (no scraping step)
```

**Exit point:** Dashboard showing CSV data analysis
**Error paths:**
- File too large → immediate error before upload
- CSV has no recognizable text column → error with column names found listed
- CSV is empty → error "0 reviews found"

---

### Flow 4: Customer Message → AI Reply → Send

**User type:** Customer Success Manager, Founder
**Trigger:** Customer sends a complaint email / support message
**Goal:** Draft and send a response quickly using AI assistance

```
1. User navigates to /inbox
      │
      ▼
2. Sees message list:
   ├── [negative] Max M. — "Ich kann mich seit 2 Wochen nicht einloggen..."
   ├── [positive] Anna K. — "Super App, genau was ich gesucht habe!"
   └── [neutral] Thomas B. — "Wann kommt das Update für iOS?"
      │
      ▼
3. User clicks on Max M.'s negative message
      │
      ▼
4. Detail panel opens:
   ├── Name: Max Mustermann
   ├── Email: max@company.com
   ├── Sentiment: 🔴 Negativ
   ├── Full message text
   └── Buttons: "Antwort generieren" | "Tickets erstellen"
      │
      ▼
5. User clicks "Antwort generieren"
      │
   ┌──┴──────────────────────────────────────┐
   │ System calls POST /messages/{id}/       │
   │ generate-reply                          │
   │ → Groq: personalizes to message content │
   │ → Fallback: template based on sentiment │
   └─────────────────────────────────────────┘
      │
      ▼
6. AI reply displayed in text area:
   "Vielen Dank für Ihre Nachricht, Herr Mustermann.
    Wir bedauern, dass Sie Probleme mit dem Login haben.
    Unser Team untersucht dieses Problem aktiv..."
      │
      ▼
7. User edits reply if needed:
   ├── Personalizes tone
   ├── Adds specific details
   └── Removes anything inaccurate
      │
      ▼
8. [Phase 1 — Manual copy] User copies text, sends via email client
   [Phase 2 — Send button] Clicks "Antwort senden" → Resend API delivers email
```

**Exit point:** Reply sent (Phase 2) or copied to clipboard (Phase 1)
**Success metric:** Time to first reply draft <30 seconds

---

### Flow 5: Message → Auto-Generated Tickets

**User type:** Product Manager
**Trigger:** Customer sends a message with multiple product issues
**Goal:** Convert message into actionable Jira-style tickets instantly

```
1. User is viewing a customer message in Inbox
   (Same starting state as Flow 4, step 4)
      │
      ▼
2. User clicks "Tickets erstellen"
      │
   ┌──┴──────────────────────────────────────┐
   │ System calls POST /messages/{id}/        │
   │ generate-tickets                         │
   │ → Groq parses message, identifies        │
   │   distinct issues, suggests titles +     │
   │   descriptions + priority               │
   │ → Creates 1-3 tickets in DB             │
   └─────────────────────────────────────────┘
      │
      ▼
3. Success message: "3 Tickets erstellt"
   List of created ticket titles shown
      │
      ▼
4. User navigates to /tickets (Kanban)
      │
      ▼
5. Tickets appear in Backlog column with:
   ├── [High] "Login-Problem beheben"
   ├── [Medium] "Passwort-Reset-Email verbessern"
   └── [Low] "App-Version auf Onboarding anzeigen"
      │
      ▼
6. User clicks "Login-Problem beheben"
   Detail panel opens
      │
      ▼
7. User moves ticket to "Todo"
   Status dropdown → "Todo"
   → Auto-save (or Save button)
      │
      ▼
8. Ticket disappears from Backlog column,
   reappears in Todo column
```

**Exit point:** Tickets in Kanban board in correct status
**Success metric:** 0 minutes of manual ticket writing vs. previous 5-10 minutes per ticket

---

### Flow 6: Kanban Ticket Lifecycle

**User type:** Engineering lead or Product Manager
**Trigger:** Sprint planning session
**Goal:** Move tickets from Backlog through Done

```
Backlog → Todo
──────────────
1. User opens /tickets
2. Clicks ticket in Backlog
3. Detail panel: change Status → "Todo"
4. Clicks "Speichern"
5. Ticket moves to Todo column

Todo → In Progress
──────────────────
1. Developer picks up ticket
2. Opens ticket detail
3. Changes Status → "In Progress"
4. (Optional) Edits description to add implementation notes
5. Saves

In Progress → Done
──────────────────
1. Feature shipped
2. Opens ticket
3. Changes Status → "Done"
4. (Optional) Adds comment: "Fixed in v3.2.2"
5. Saves

Done → Delete (if not needed)
──────────────────────────────
1. User clicks "Löschen" in ticket detail
2. Confirmation dialog: "Ticket wirklich löschen?"
3. User confirms → ticket deleted
4. List refreshes, ticket gone
```

**Priority editing:**
```
1. Open ticket
2. Change Priority dropdown (Low / Medium / High)
3. PriorityBadge color updates immediately in preview
4. Save → badge updates in list
```

---

### Flow 7: Data Source Deletion

**User type:** Any user
**Trigger:** User connected wrong app, or wants to clean up old data
**Goal:** Remove a data source and all associated analysis
**Risk level:** High (irreversible action)

```
1. User navigates to /datasources
      │
      ▼
2. Finds the data source to delete
      │
      ▼
3. Clicks trash icon (🗑) on the source card
      │
      ▼
4. Confirmation dialog:
   "BMW Connected wirklich löschen?
    Alle 200 Reviews und Analysen werden unwiderruflich gelöscht."
   [Abbrechen] [Löschen]
      │
   ┌──┴──────────────────────────────────────┐
   │ User clicks "Abbrechen" → no action     │
   └─────────────────────────────────────────┘
      │ User clicks "Löschen"
      ▼
5. System:
   ├── DELETE /datasources/{id}
   ├── Cascade: deletes reviews, clusters, pipeline_jobs
   └── Returns 204
      │
      ▼
6. Data source removed from list
   Success toast: "Datenquelle gelöscht"

   [If user is on Dashboard with this source selected]
   → Dashboard shows empty state, prompts to select another source
```

**Error path:** If delete fails (network error) → show error toast, source remains in list

---

## 3. Error Flow Patterns

### Authentication Failure
```
Any protected page → 401 Unauthorized (token expired)
  → User redirected to /login
  → After login → returned to last intended page
```

### Pipeline Failure
```
Pipeline job fails (network error, scraping block, etc.)
  → PipelineJob.status = "failed", error message stored
  → UI shows: "⚠ Analyse fehlgeschlagen"
             + error message (e.g., "App not found on Play Store")
             + "Erneut versuchen" button
  → Retry creates new PipelineJob, runs pipeline again
```

### Empty Dashboard (no completed pipeline)
```
User navigates to /dashboard with no data source
  → Empty state: "Verbinde eine App, um loszulegen"
               + "Zu Datenquellen" button
```

---

## 4. Navigation Map

```
/login ──────────────────── Register link → /register
  │
  └── (auth) ──────────────────────────────────────────────────────┐
                                                                    │
/dashboard ←──── (after login / after pipeline completes)          │
  │                                                                  │
  ├── DataSource selector dropdown                                  │
  ├── Cluster card expand                                           │
  └── (empty state) → /datasources                                 │
                                                                    │
/datasources ←──── Sidebar nav item                                │
  │                                                                  │
  ├── Google Play form → POST → pipeline running → back to list    │
  ├── CSV upload form → POST → pipeline running → back to list     │
  └── Delete → confirm → removed from list                         │
                                                                    │
/inbox ←──── Sidebar nav item                                      │
  │                                                                  │
  ├── Message list → click → detail panel                          │
  ├── Generate Reply → shows text → copy                           │
  └── Generate Tickets → creates tickets → navigate to /tickets   │
                                                                    │
/tickets ←──── Sidebar nav item, link from Inbox                  │
  │                                                                  │
  ├── 4 columns: Backlog | Todo | In Progress | Done               │
  ├── Click ticket → detail panel on right                         │
  ├── Create ticket (inline form in Backlog)                       │
  └── Edit / Delete ticket                                         │
```

---

## 5. Edge Cases & Corner Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User opens Dashboard with no data sources | Empty state with CTA to connect first source |
| User opens Dashboard while pipeline is running | Loading state / disabled selector until done |
| User connects same Google Play app twice | System allows it — different DataSource records with separate analysis |
| CSV has 0 rows | Error: "CSV enthält keine Bewertungen" |
| CSV has 1 row | Pipeline runs, but clustering skipped (not enough data for KMeans) |
| CSV has 10,000 rows | Works, but pipeline may take 5-10 minutes; progress stages visible |
| Pipeline runs while user navigates away | Polling stops. User sees "running" state on return to /datasources |
| Token expires mid-session | On next API call: 401 → redirect to /login |
| Groq API key invalid | Fallback to rule-based — user sees result labeled "rule-based", not an error |
| Message with no discernible sentiment | Classified as "neutral" |
| Delete datasource that's currently being analyzed | Allowed — Celery task will fail gracefully (DataSource not found), job marked failed |

---

*Document Owner: Product / UX Research*
*Last Updated: 2026-07*
*Status: v1.0 — All flows implemented and tested*
