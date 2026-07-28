# UX Design Specification — MA Analytics

> *"Design is not how something looks. Design is how something works. The most powerful design decisions are invisible — they eliminate friction so completely that the user never notices the tool, only the outcome."*

---

## 1. Design Philosophy

MA Analytics serves a specific archetype: the **time-pressured product builder** — a PM, founder, or analyst who has 30 minutes to extract a product insight from thousands of customer reviews.

Every design decision derives from this constraint:

**Principle 1: Insight before configuration**  
The user's first action should produce value, not ask them to set preferences. Defaults are carefully chosen so the first run works without customization.

**Principle 2: Progressive disclosure**  
Complex controls (signal exclusion, hypothesis input, graph visualization) are hidden behind collapsible panels. The primary path is always one click: "Idee generieren."

**Principle 3: Explicit state**  
The user always knows what the system is doing. Pipeline progress shows stages. Brief generation shows a spinner with status text. Signal exclusion badges show the current mode (auto / manual count / all active).

**Principle 4: Irreversibility is marked**  
Every destructive action requires confirmation. The confirmation text names the specific thing being deleted and states the consequence.

**Principle 5: No dead ends**  
Every empty state and every error state provides an actionable next step. The user is never stranded with a blank screen.

---

## 2. Color System

The application uses an **exclusively dark theme**. There is no light mode.

### 2.1 Base Palette (Tailwind CSS)

| Token | Tailwind Class | Usage |
|-------|---------------|-------|
| Page Background | `bg-slate-950` | Outer page background |
| Card Surface | `bg-slate-800/40` | Cards, panels, modals — 40% opacity |
| Card Border | `border-slate-700/50` | Card borders, dividers |
| Surface Hover | `bg-slate-700/30` | Hovered cards, table rows |
| Text Primary | `text-white` or `text-slate-100` | Headings, primary content |
| Text Secondary | `text-slate-400` | Metadata, labels, helper text |
| Text Muted | `text-slate-500` | Placeholders, disabled states |

### 2.2 Semantic Colors (Dark Theme Variants)

| Semantic | Tailwind | Usage |
|----------|---------|-------|
| Brand Primary | `bg-indigo-600` / `text-indigo-400` | Primary buttons, links, active states, signal chips |
| Brand Hover | `bg-indigo-500` | Button hover |
| Success | `text-green-400` / `bg-green-900/30` | Positive sentiment, success toasts, edge signals |
| Warning | `text-amber-400` / `bg-amber-900/30` | Medium priority, running state, manual exclusion badge |
| Danger | `text-red-400` / `bg-red-900/30` | Negative sentiment, delete actions, hub signal warning |
| Neutral | `text-slate-400` / `bg-slate-700/50` | Neutral sentiment, disabled chips, auto exclusion badge |
| Violet | `text-violet-400` / `bg-violet-900/30` | FR-dominant signals (feature request heavy) |

### 2.3 Sentiment Color Mapping

| Sentiment | Badge Style | Usage |
|-----------|-----------|-------|
| Positive | `bg-green-900/30 text-green-400` | Review sentiment, dashboard KPI |
| Neutral | `bg-slate-700 text-slate-400` | Review sentiment |
| Negative | `bg-red-900/30 text-red-400` | Review sentiment, customer messages |

### 2.4 Signal Chip Color System (Innovation Lab)

Signal chips in the Signal-Steuerung panel use three colors based on data characteristics:

| Condition | Color | Meaning |
|-----------|-------|---------|
| `fr_mentions > 50` (feature request dominant) | `bg-violet-900/30 text-violet-400 border-violet-700/50` | Product opportunity signal |
| `bug_mentions > 200 AND fr_mentions ≤ 50` (bug dominant) | `bg-red-900/30 text-red-400 border-red-700/50` | Pain/bug signal |
| All others | `bg-indigo-900/30 text-indigo-400 border-indigo-700/50` | General signal |
| Disabled chip | `opacity-50 line-through cursor-pointer text-slate-500 bg-slate-800 border-slate-700` | Excluded from generation |

### 2.5 Risk Level Colors

Used in Innovation Brief cards and detail panels:

| Risk Level | Style |
|------------|-------|
| `hoch` | `bg-red-900/30 text-red-400` |
| `mittel` | `bg-amber-900/30 text-amber-400` |
| `niedrig` | `bg-green-900/30 text-green-400` |

### 2.6 Priority Color Mapping

| Priority | Style |
|----------|-------|
| High | `bg-red-900/30 text-red-400` |
| Medium | `bg-amber-900/30 text-amber-400` |
| Low | `bg-green-900/30 text-green-400` |

---

## 3. Typography

| Role | Tailwind | Usage |
|------|---------|-------|
| Page Title | `text-2xl font-bold text-white` | Page headers |
| Section Header | `text-lg font-semibold text-white` | Card titles, section labels |
| Body | `text-sm text-slate-300` | Most content text |
| Small | `text-xs text-slate-400` | Metadata, timestamps, badges |
| Code / Technical | `font-mono text-xs text-slate-400` | App IDs, technical values |
| KPI Number | `text-3xl font-bold text-white` | Dashboard KPI values |

**Font family:** System UI stack (Tailwind default). No custom fonts — system fonts load instantly and look native.

---

## 4. Spacing System

Based on Tailwind's default 4px grid:

| Token | Size | Tailwind | Usage |
|-------|------|---------|-------|
| XS | 4px | `p-1` / `gap-1` | Icon padding, tight inline |
| SM | 8px | `p-2` / `gap-2` | Badge padding, chip padding |
| MD | 12px | `p-3` | Compact card padding |
| LG | 16px | `p-4` | Standard card padding |
| XL | 24px | `p-6` | Section padding |
| 2XL | 32px | `p-8` | Page padding |

---

## 5. Component Library

### 5.1 Navigation Sidebar

**Layout:** Fixed left sidebar, dark background, full viewport height.

```
┌────────────────────────────────────────────┐
│  MA Analytics                (logo + name) │
│                                            │
│  [icon] Dashboard                          │ ← active: indigo bg + text
│  [icon] Datenquellen                       │ ← inactive: slate hover
│  [icon] Innovation Lab    ← NEW            │
│  [icon] Posteingang                        │
│  [icon] Kanban                             │
│  [icon] Suche                              │
│  [icon] Intelligence                       │
│                                            │
│  ──────────────────────────────────────    │
│  [avatar] user@email.com      (footer)     │
└────────────────────────────────────────────┘
```

**Active state:** `bg-indigo-500/20 text-indigo-400 font-medium rounded-lg`  
**Hover state:** `hover:bg-slate-700/50 text-slate-300 rounded-lg`  
**Icons:** lucide-react (LayoutDashboard, Database, Lightbulb, Mail, LayoutKanban, Search, Brain)

---

### 5.2 KPI Cards

Four horizontal cards on the Dashboard.

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Gesamt Reviews  │  │ Ø Bewertung      │  │ Positiv          │  │ Negativ          │
│                  │  │                  │  │                  │  │                  │
│      33.649      │  │    2.8 ★         │  │    40%           │  │    45%           │
│                  │  │                  │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

**Styling:** `bg-slate-800/40 rounded-xl border border-slate-700/50 p-6`  
**Number:** `text-3xl font-bold text-white`  
**Label:** `text-sm text-slate-400 mb-1`

---

### 5.3 StatusBadge Component

Reusable component for pipeline status, job status, datasource state.

| Status | Style |
|--------|-------|
| `pending` | `bg-slate-700 text-slate-400` + Clock icon |
| `running` | `bg-blue-900/30 text-blue-400` + animated Loader2 icon |
| `done` | `bg-green-900/30 text-green-400` + CheckCircle icon |
| `failed` | `bg-red-900/30 text-red-400` + AlertCircle icon |

---

### 5.4 Innovation Lab — Main Layout

The Innovation Lab page (`/innovation`) has a two-panel layout:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Innovation Lab                                                              │
│                                                                             │
│  ┌──────────────────────────────────────┐   ┌───────────────────────────┐   │
│  │ BRIEF GENERIEREN (left panel)        │   │ BRIEFS HISTORY (right)    │   │
│  │                                      │   │                           │   │
│  │ Modus: [Wettbewerb] [Innovation]     │   │ [TrustSync         Lö]    │   │
│  │ Scope: [Alle] [Industrie] [App]      │   │  Jul 27 · mittel · 892    │   │
│  │                                      │   │                           │   │
│  │ Hypothese (optional):                │   │ [UpdateGuard       Lö]    │   │
│  │ ┌────────────────────────────────┐   │   │  Jul 25 · hoch · 1240     │   │
│  │ │ Textarea...                    │   │   │                           │   │
│  │ └────────────────────────────────┘   │   └───────────────────────────┘   │
│  │                                      │                                   │
│  │ ▼ Signal-Steuerung [auto badge]      │   ┌───────────────────────────┐   │
│  │ ┌────────────────────────────────┐   │   │ SELECTED BRIEF DETAIL     │   │
│  │ │ [Alle] [Keine]                 │   │   │                           │   │
│  │ │ [Updates 3585] [Bluetooth 892] │   │   │ TrustSync                 │   │
│  │ │ [Navigation 744] [Login 612]   │   │   │ Fahrzeugdaten, die...     │   │
│  │ └────────────────────────────────┘   │   │                           │   │
│  │                                      │   │ [Details] [Konzept] [PDF] │   │
│  │      [Idee generieren]               │   │                           │   │
│  └──────────────────────────────────────┘   └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.5 Signal-Steuerung Panel

Collapsible panel showing all available signal clusters for manual control.

**Header (collapsed):**
```
▼ Signal-Steuerung  [auto]        ← gray badge: auto-exclusion active
▼ Signal-Steuerung  [3 aus]       ← amber badge: 3 signals manually excluded
▼ Signal-Steuerung  [alle aktiv]  ← green badge: user cleared all exclusions
```

**Expanded state:**
```
┌──────────────────────────────────────────────────────────────────────────┐
│ ▲ Signal-Steuerung [3 aus]                                               │
│                                                                          │
│ [Alle] [Keine]                                                           │
│                                                                          │
│ [Updates 3585⚙] [Bluetooth 892] [Navigation 744] [Login 612]            │
│ [Connectivity 534] [Performance 487] [Account 423⚙]                     │
│ [Charging 388] [CarPlay 352] [Maps 318]                                  │
│                                                                          │
│ Chip with ⚙: hub signal (infrastructure-level OEM problem)              │
└──────────────────────────────────────────────────────────────────────────┘
```

**Badge states:**
- `auto` → `bg-slate-700 text-slate-400 text-xs px-2 py-0.5 rounded-full`
- `X aus` → `bg-amber-900/30 text-amber-400 text-xs px-2 py-0.5 rounded-full`
- `alle aktiv` → `bg-green-900/30 text-green-400 text-xs px-2 py-0.5 rounded-full`

**Chip styling (enabled):**
```
bg-indigo-900/30 text-indigo-400 border border-indigo-700/50 
text-xs px-2 py-1 rounded-full cursor-pointer 
hover:bg-indigo-800/40 transition-colors
```

**Chip styling (disabled/excluded):**
```
bg-slate-800 text-slate-500 border border-slate-700 
text-xs px-2 py-1 rounded-full cursor-pointer opacity-50 line-through
```

---

### 5.6 Innovation Brief Card (History Panel)

```
┌──────────────────────────────────────────────────────┐
│  TrustSync                              [🗑 Löschen]  │
│  Fahrzeugdaten, die wirklich aktualisi...             │
│                                                      │
│  [mittel risk]  892 Anfragen  5 Apps  27 Jul         │
│  [💡 Hypothese] Fahrer wollen OTA-Updates ohne...    │
└──────────────────────────────────────────────────────┘
```

**Active/selected card:** `ring-2 ring-indigo-500` border  
**Default card:** `bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 cursor-pointer hover:bg-slate-700/30`

---

### 5.7 Innovation Brief Detail — Tab Navigation

The selected brief shows three tabs: Details, Konzeptdokument, PDF Export.

**Details tab** shows:
- Product name + tagline
- Core problem description
- Market gap analysis
- Feature list (table with mentions + priority)
- Target audience
- Differentiation
- Risk assessment block
- Signal sources table
- Copilot chat button → opens chat drawer

**Konzeptdokument tab** shows:
- Long-form ~1200+ word strategic document
- Rendered markdown (headings, paragraphs)
- "Konzept generieren / neu generieren" button
- Loading state during generation

**PDF Export tab** shows:
- Preview of what will be exported
- "PDF herunterladen" button → triggers client-side jsPDF generation

---

### 5.8 Brief Copilot Chat Drawer

Right-side drawer (full height) for conversational Q&A about the selected brief.

```
┌─────────────────────────────────────────────────────┐
│  Brief Copilot                              [✕]     │
│  Fragen Sie über TrustSync                          │
│                                                     │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  AI: Basierend auf den Signaldaten fokussiert...    │
│                                                     │
│  User: Was wäre ein realistischer Preis?            │
│                                                     │
│  AI: Für das B2B-Segment würde ich empfehlen...     │
│                                                     │
│  ─────────────────────────────────────────────────  │
│  ┌─────────────────────────────────────────────┐    │
│  │ Frage eingeben...                       [→] │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Chat message styles:**
- AI messages: `bg-slate-700/50 rounded-xl p-3 text-sm text-slate-300`
- User messages: `bg-indigo-600/30 rounded-xl p-3 text-sm text-indigo-200 ml-8`

---

### 5.9 Buttons

| Variant | Dark Theme Class | Usage |
|---------|-------|-------|
| Primary | `bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors` | Main actions (Generieren, Speichern) |
| Secondary | `bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600 px-4 py-2 rounded-lg` | Secondary actions (Abbrechen) |
| Danger | `bg-red-900/50 hover:bg-red-800 text-red-400 border border-red-700/50 px-4 py-2 rounded-lg` | Delete, irreversible actions |
| Ghost | `text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 px-3 py-1 rounded-lg` | Inline actions, icon buttons |

**Loading state:** Replace content with `<Loader2 className="animate-spin" />`. Disable button to prevent double-submit.

---

### 5.10 Form Fields (Dark Theme)

**Text input:**
```
bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200
placeholder:text-slate-500
focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
```

**Textarea:**
Same as text input with `resize-none` and explicit `rows` attribute.

**Select/Dropdown:**
Same as text input + `appearance-none`

**Inline validation error:**
```
text-sm text-red-400 mt-1
```

---

### 5.11 Kanban Board

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Backlog (3)          Todo (1)            In Progress (2)      Done (4)             │
│                                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ + Erstellen  │    │              │    │              │    │              │      │
│  └──────────────┘    │ Login-Bug    │    │ CSV Upload   │    │ Ticket #12   │      │
│  ┌──────────────┐    │ [🔴 Hoch]   │    │ [🟡 Mittel]  │    │ [🟢 Niedrig] │      │
│  │ CSV Export   │    └──────────────┘    └──────────────┘    └──────────────┘      │
│  │ [🟢 Niedrig] │                                                                   │
│  └──────────────┘                                                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Column header:** `bg-slate-800/60 rounded-t-lg px-3 py-2 font-medium text-sm text-slate-300`  
**Ticket card:** `bg-slate-800/40 rounded-lg border border-slate-700/50 p-3 cursor-pointer hover:bg-slate-700/30`  
**Ticket detail panel:** Right-side drawer, `w-96 fixed right-0 top-0 h-full bg-slate-900 shadow-xl border-l border-slate-700/50`

---

### 5.12 Empty States

Every empty state has:
1. A muted icon (large, centered, `text-slate-600`)
2. A title in `text-slate-400`
3. A subtitle with context in `text-slate-500`
4. A primary action button

**Example — Innovation Lab with no briefs:**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                  [💡 icon, 48px, slate-600]                    │
│                                                                 │
│              Noch keine Briefs generiert                        │
│                                                                 │
│     Geben Sie einen Modus und Scope an und                      │
│     klicken Sie auf "Idee generieren".                          │
│                                                                 │
│              [→ Ersten Brief generieren]                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 5.13 Toast Notifications

| Type | Style | Auto-dismiss |
|------|-------|-------------|
| Success | `bg-green-900/80 text-green-200 border border-green-700` | 3 seconds |
| Error | `bg-red-900/80 text-red-200 border border-red-700` | 5 seconds |
| Info | `bg-indigo-900/80 text-indigo-200 border border-indigo-700` | 3 seconds |

**Position:** Bottom-right corner, stacked if multiple  
**Animation:** slide-in from right, fade-out on dismiss

---

### 5.14 Pipeline Progress Indicator

```
┌──────────────────────────────────────────────────────────────────┐
│  BMW Connected                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  ⟳ Analyse läuft...                                       │  │
│  │  Sentiment analysieren...                                  │  │
│  │  [━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░]  50%                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

Progress bar: `bg-indigo-600 rounded-full transition-all` on `bg-slate-700 rounded-full h-2`

---

## 6. Page Layouts

### 6.1 App Shell

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Sidebar ~256px fixed, bg-slate-900]  │  [Main, flex-1, overflow-auto]     │
│                                        │   bg-slate-950 p-8                 │
│  MA Analytics                          │                                    │
│                                        │  Page Title  text-2xl font-bold   │
│  Dashboard                             │                                    │
│  Datenquellen                          │  ┌─────────────────────────────┐   │
│  Innovation Lab                        │  │ Content                     │   │
│  Posteingang                           │  └─────────────────────────────┘   │
│  Kanban                                │                                    │
│  Suche                                 │                                    │
│  Intelligence                          │                                    │
│  ─────────────────                     │                                    │
│  user@email.com                        │                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Main content max width:** `max-w-7xl mx-auto`

### 6.2 Innovation Lab Two-Column Layout

Left panel (~40% width): generation controls  
Right panel (~60% width): brief history + selected brief detail  

### 6.3 Three-Panel Layout (Inbox)

Sidebar | Message List (1/3) | Message Detail (2/3)

---

## 7. Responsive Design

**Primary target:** Desktop (1280×800+, MacBook 13" and above)  
**Mobile:** Not a v1.0 requirement. The product is a desktop tool.  
**Min supported width:** 1024px

---

## 8. Accessibility

### 8.1 Keyboard Navigation

| Action | Shortcut |
|--------|---------|
| Close modal / drawer | `Escape` |
| Submit form | `Enter` |
| Navigate sidebar | `Tab` |
| Toggle Signal chip | `Space` / `Enter` on focused chip |

### 8.2 ARIA Labels

| Element | ARIA |
|---------|------|
| Modal | `role="dialog"` + `aria-modal="true"` + `aria-labelledby` |
| Icon-only buttons | `aria-label="Brief löschen"` etc. |
| Signal chip (disabled) | `aria-pressed="false"` |
| Loading spinner | `aria-label="Wird geladen..."` + `aria-live="polite"` |

### 8.3 Color Contrast

All dark theme combinations meet WCAG AA (4.5:1 minimum):
- `slate-100` on `slate-950` = 18:1 ✅
- `indigo-400` on `slate-950` = 4.8:1 ✅
- `red-400` on `slate-950` = 4.6:1 ✅
- `green-400` on `slate-950` = 5.1:1 ✅

---

## 9. Interaction Patterns

### Loading States

Every async operation shows a loading state:
1. Disable the triggering button immediately (prevents double-submit)
2. Show spinner (Loader2, `animate-spin`) in button or content area
3. Never show empty state and loading state simultaneously

### Signal Panel Lazy Loading

Signal chips load only when the Signal-Steuerung panel is expanded. `useRef` tracks the pending fetch and cancels stale requests when the scope changes. This prevents race conditions when the user quickly changes filters.

### Brief Generation Feedback

During generation (typically 5–15 seconds):
1. Button shows "Generiere..." + spinner, disabled
2. Status text appears below: "Signale aggregieren → Prompt erstellen → KI-Brief generieren → Speichern"
3. On success: brief appears in history panel, scrolled into view
4. On error: error toast with retry option

### Polling Strategy

For pipeline status: `setInterval` at 4-second intervals.
- Start: when a job is `pending` or `running`
- Stop: when job is `done` or `failed`
- Cleanup: `useEffect` cleanup function clears interval on unmount

### Confirmation Dialogs

Used for: delete data source, delete brief, delete ticket.

Pattern:
1. User clicks delete
2. Modal appears naming the specific resource
3. States the consequence ("Alle Daten werden unwiderruflich gelöscht")
4. [Abbrechen] (secondary) [Löschen] (danger)
5. Enter key = cancel (safe default); red button requires explicit click

---

## 10. Micro-interactions

| Trigger | Response |
|---------|---------|
| Hover on brief card | `bg-slate-700/30` transition |
| Click on signal chip | Toggle disabled state with `line-through opacity-50` |
| Click "Alle" / "Keine" | All chips update simultaneously with transition |
| Brief generation complete | Brief slides into history panel |
| New badge state | Animate color change (`transition-colors duration-200`) |
| Copilot chat send | Message appears immediately; AI response streams in |
| Pipeline stage change | Progress bar grows with `transition-all` |

---

*Document Owner: Design / Frontend*  
*Last Updated: 2026-07*  
*Status: v1.0 — Implemented in React + Tailwind CSS (dark theme)*
