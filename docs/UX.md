# UX Design Specification — MA Analytics

> *"Design is not how something looks. Design is how something works. The most powerful design decisions are invisible — they eliminate friction so completely that the user never notices the tool, only the outcome."*

---

## 1. Design Philosophy

MA Analytics serves a specific archetype: the **time-pressured product builder** — a PM, founder, or customer success manager who has 15 minutes, not 2 hours, to get insight from customer feedback.

Every design decision derives from this constraint:

**Principle 1: Insight before configuration**
The user's first action should produce value, not ask them to set preferences. Defaults are carefully chosen so the first run works without customization.

**Principle 2: Progressive disclosure**
Complex information is hidden until the user asks for it. Cluster cards show a label and count; the details (examples, summary) appear on expansion. The Kanban detail panel is a drawer, not a page.

**Principle 3: Explicit state**
The user always knows what the system is doing. Pipelines show stages. Buttons have loading states. Empty states explain why they're empty and what to do next.

**Principle 4: Irreversibility is marked**
Every destructive action (delete) requires confirmation. The confirmation text names the specific thing being deleted and states the consequence. No generic "Are you sure?"

**Principle 5: No dead ends**
Every empty state and every error state provides an actionable next step. The user is never stranded.

---

## 2. Color System

### 2.1 Base Palette (Tailwind CSS)

| Token | Tailwind Class | Hex | Usage |
|-------|---------------|-----|-------|
| Background | `bg-gray-50` | #F9FAFB | Page background |
| Surface | `bg-white` | #FFFFFF | Cards, panels, modals |
| Border | `border-gray-200` | #E5E7EB | Card borders, dividers |
| Text Primary | `text-gray-900` | #111827 | Headings, body |
| Text Secondary | `text-gray-500` | #6B7280 | Metadata, labels |
| Text Muted | `text-gray-400` | #9CA3AF | Placeholders, disabled |

### 2.2 Semantic Colors

| Semantic | Tailwind | Hex | Usage |
|----------|---------|-----|-------|
| Brand Primary | `bg-blue-600` | #2563EB | Primary buttons, links, active states |
| Brand Hover | `bg-blue-700` | #1D4ED8 | Button hover state |
| Success | `text-green-600` / `bg-green-50` | #16A34A / #F0FDF4 | Positive sentiment, success toasts |
| Warning | `text-yellow-600` / `bg-yellow-50` | #CA8A04 / #FEFCE8 | Medium priority, running state |
| Danger | `text-red-600` / `bg-red-50` | #DC2626 / #FEF2F2 | Negative sentiment, delete actions, errors |
| Neutral | `text-gray-500` / `bg-gray-100` | #6B7280 / #F3F4F6 | Neutral sentiment, disabled |

### 2.3 Sentiment Color Mapping

Sentiment colors are used consistently across the entire UI — in badges, bars, and cluster cards:

| Sentiment | Background | Text | Icon |
|-----------|-----------|------|------|
| Positive | `bg-green-100` | `text-green-700` | ↑ or 😊 |
| Neutral | `bg-gray-100` | `text-gray-600` | → or 😐 |
| Negative | `bg-red-100` | `text-red-700` | ↓ or 😞 |

### 2.4 Priority Color Mapping

| Priority | Background | Text |
|----------|-----------|------|
| High | `bg-red-100` | `text-red-700` |
| Medium | `bg-yellow-100` | `text-yellow-700` |
| Low | `bg-green-100` | `text-green-700` |

---

## 3. Typography

| Role | Tailwind | Size | Weight | Usage |
|------|---------|------|--------|-------|
| Page Title | `text-2xl font-bold` | 24px | 700 | Page headers |
| Section Header | `text-lg font-semibold` | 18px | 600 | Card titles, section labels |
| Body | `text-sm` | 14px | 400 | Most content text |
| Small | `text-xs` | 12px | 400 | Metadata, timestamps, badges |
| Code | `font-mono text-xs` | 12px | 400 | App IDs, technical values |

**Font family:** System UI stack (Tailwind default):
`ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial`

No custom fonts — system fonts load instantly, look native on every platform, and need no CDN.

---

## 4. Spacing System

Based on Tailwind's default 4px grid:

| Token | Size | Tailwind | Usage |
|-------|------|---------|-------|
| XS | 4px | `p-1` / `gap-1` | Icon padding, tight inline |
| SM | 8px | `p-2` / `gap-2` | Badge padding, tight spacing |
| MD | 12px | `p-3` | Default card padding (small) |
| LG | 16px | `p-4` | Standard card padding |
| XL | 24px | `p-6` | Section padding |
| 2XL | 32px | `p-8` | Page padding |

---

## 5. Component Library

### 5.1 Navigation Sidebar

**Layout:** Fixed left sidebar, 256px wide, full viewport height

```
┌─────────────────────────────────────────────┐
│  MA Analytics                (logo + name)  │
│                                             │
│  [icon] Dashboard                           │ ← active: blue bg + text
│  [icon] Datenquellen                        │ ← inactive: gray hover
│  [icon] Posteingang                         │
│  [icon] Kanban                              │
│                                             │
│  ─────────────────────────────────────────  │
│  [avatar] ayhan@company.com      (footer)   │
└─────────────────────────────────────────────┘
```

**Active state:** `bg-blue-100 text-blue-700 font-medium rounded-lg`
**Hover state:** `hover:bg-gray-100 rounded-lg`
**Icons:** lucide-react (LayoutDashboard, Database, Mail, LayoutKanban)

---

### 5.2 KPI Cards

Four horizontal cards showing the most important dashboard metrics.

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Gesamt Reviews  │  │ Ø Bewertung      │  │ Positiv          │  │ Negativ          │
│                  │  │                  │  │                  │  │                  │
│      200         │  │    2.8 ★         │  │    40%           │  │    45%           │
│                  │  │                  │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

**Styling:** `bg-white rounded-xl shadow-sm border border-gray-200 p-6`
**Number:** `text-3xl font-bold text-gray-900`
**Label:** `text-sm text-gray-500 mb-1`

---

### 5.3 Sentiment Bar

Visual distribution of positive/neutral/negative reviews.

```
┌──────────────────────────────────────────────────────────────┐
│ Sentiment-Verteilung                                         │
│                                                              │
│  [█████████████████████░░░░░████████████████████████]       │
│  40% positiv              3%    45% negativ                  │
│  (green, proportional)  (grey) (red, proportional)           │
└──────────────────────────────────────────────────────────────┘
```

**Implementation:** Flexbox with percentage widths, `rounded-full overflow-hidden`, `h-3` height.

**CSS pattern:**
```css
.sentiment-bar { display: flex; height: 12px; border-radius: 9999px; overflow: hidden; }
.positive { background: #16A34A; width: 40%; }
.neutral  { background: #9CA3AF; width: 3%; }
.negative { background: #DC2626; width: 45%; }
```

---

### 5.4 Cluster Cards (Issues / Strengths)

The primary insight surface. Collapsed by default, expands to show detail.

**Collapsed state:**
```
┌──────────────────────────────────────────────────────────────────┐
│  🔴 login / nicht / möglich                    11 Erwähnungen ▼  │
└──────────────────────────────────────────────────────────────────┘
```

**Expanded state:**
```
┌──────────────────────────────────────────────────────────────────┐
│  🔴 login / nicht / möglich                    11 Erwähnungen ▲  │
│  ─────────────────────────────────────────────────────────────── │
│  11 reviews mention this issue.                                  │
│                                                                  │
│  Beispiele:                                                      │
│  • "Anmeldung nicht möglich.. Peinliche app"                    │
│  • "Kein Login mehr möglich."                                    │
│  • "Keine login möglichkeit seit dem letzten Update"             │
└──────────────────────────────────────────────────────────────────┘
```

**Styling — collapsed:** `bg-white rounded-lg border border-gray-200 p-4 cursor-pointer hover:shadow-md transition-shadow`
**Styling — header:** `flex justify-between items-center`
**Issue indicator:** Red dot or red cluster icon
**Strength indicator:** Green checkmark or green cluster icon
**Example quotes:** `text-sm text-gray-600 italic border-l-2 border-gray-200 pl-3 my-1`
**Expand animation:** `transition-all duration-200`

---

### 5.5 Pipeline Status Indicator

Shows during active pipeline execution in /datasources.

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

**Loading spinner:** Tailwind `animate-spin` on a Loader2 icon from lucide
**Status badge:** `StatusBadge` component:

| Status | Badge |
|--------|-------|
| `pending` | `bg-gray-100 text-gray-600` + Clock icon |
| `running` | `bg-blue-100 text-blue-600` + animated Loader2 icon |
| `done` | `bg-green-100 text-green-700` + CheckCircle icon |
| `failed` | `bg-red-100 text-red-700` + AlertCircle icon |

---

### 5.6 Sentiment Badge

Used in message list (Inbox) to label message sentiment at a glance.

```
[🟢 Positiv]   [🔴 Negativ]   [⚪ Neutral]
```

**Styling:** `inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium`
**Colors:** See Section 2.3

---

### 5.7 Priority Badge

Used in Kanban ticket cards and detail panel.

```
[🔴 Hoch]   [🟡 Mittel]   [🟢 Niedrig]
```

**Styling:** Same as SentimentBadge, colors from Section 2.4

---

### 5.8 Buttons

| Variant | Class | Usage |
|---------|-------|-------|
| Primary | `bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors` | Main actions (Connect, Analyze, Save) |
| Secondary | `bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-lg` | Secondary actions (Cancel, Back) |
| Danger | `bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg` | Delete, irreversible actions |
| Ghost | `text-gray-600 hover:text-gray-900 hover:bg-gray-100 px-3 py-1 rounded-lg` | Inline actions, icon buttons |

**Loading state:** Replace icon/text with `<Loader2 className="animate-spin" />` while async in progress. Disable button to prevent double-submit.

---

### 5.9 Form Fields

**Text input:**
```
label: text-sm font-medium text-gray-700 mb-1
input: w-full px-3 py-2 border border-gray-300 rounded-lg
       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
       placeholder:text-gray-400
       transition-shadow
```

**Select/Dropdown:**
Same as text input + `appearance-none bg-white`

**Inline validation error:**
```
text-sm text-red-600 mt-1
```

Error appears below the field it belongs to (not in a toast for form validation).

---

### 5.10 Modal

Used for: New Message form, confirmations.

```
┌─────────────────────────────────────────────────────────────┐
│  Backdrop: fixed inset-0 bg-black/50 z-40                  │
│                                                             │
│  ┌───────────────────────────────────────────────────┐     │
│  │  Modal: bg-white rounded-xl shadow-xl p-6 max-w-lg│     │
│  │                                                   │     │
│  │  Title (text-lg font-semibold)            [✕]     │     │
│  │                                                   │     │
│  │  Content                                          │     │
│  │                                                   │     │
│  │                    [Cancel] [Confirm]             │     │
│  └───────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

**Accessibility:** `role="dialog"`, `aria-modal="true"`, focus trapped inside, `Escape` closes.
**Animation:** `transition-opacity duration-200`.

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

**Column header:** `bg-gray-100 rounded-t-lg px-3 py-2 font-medium text-sm text-gray-700`
**Column count:** `bg-gray-200 text-gray-600 text-xs px-2 py-0.5 rounded-full ml-2`
**Ticket card:** `bg-white rounded-lg border border-gray-200 p-3 cursor-pointer hover:shadow-md`
**Ticket detail panel:** Right-side drawer, `w-96 fixed right-0 top-0 h-full bg-white shadow-xl border-l border-gray-200`

---

### 5.12 Empty States

Every empty state has:
1. An illustration or icon (large, centered, muted)
2. A title explaining the state
3. A subtitle with context
4. A primary CTA button

**Example — Dashboard with no data:**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    [📊 icon, 48px, gray-300]                   │
│                                                                 │
│              Noch keine Analyse vorhanden                       │
│                                                                 │
│     Verbinde eine App-Datenquelle, um loszulegen.              │
│                                                                 │
│              [→ Datenquellen verbinden]                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 5.13 Toast Notifications

Non-blocking confirmation of background actions.

| Type | Position | Color | Auto-dismiss |
|------|----------|-------|-------------|
| Success | Bottom-right | `bg-green-600 text-white` | 3 seconds |
| Error | Bottom-right | `bg-red-600 text-white` | 5 seconds (longer = more urgent) |
| Info | Bottom-right | `bg-blue-600 text-white` | 3 seconds |

**Anatomy:** Icon + message text + close button
**Animation:** slide-in from right, fade-out on dismiss

---

## 6. Page Layouts

### 6.1 Two-Column App Shell

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [Sidebar 256px fixed]  │  [Main Content, flex-1, overflow-auto]          │
│                         │                                                  │
│  MA Analytics           │  Page Title                                      │
│                         │                                                  │
│  Dashboard              │  ┌───────────────────────────────────────────┐   │
│  Datenquellen           │  │  Content                                  │   │
│  Posteingang            │  └───────────────────────────────────────────┘   │
│  Kanban                 │                                                  │
│                         │                                                  │
│  ─────────────────      │                                                  │
│  user@email.com         │                                                  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Main content:** `flex-1 overflow-auto bg-gray-50 p-8`
**Max width:** `max-w-7xl mx-auto` (contents don't stretch to 4K width)

### 6.2 Three-Panel Layout (Inbox)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Sidebar │  Message List (1/3)    │  Message Detail (2/3)                   │
│         │                        │                                         │
│         │  [Neg] Max M.  ━━━━━━  │  Max Mustermann                        │
│         │  Ich kann mich...      │  max@company.com                       │
│         │                        │  🔴 Negativ                             │
│         │  [Pos] Anna K. ─────── │                                        │
│         │  Super App...          │  Ich kann mich seit 2 Wochen nicht... │
│         │                        │                                         │
│         │  + Neue Nachricht      │  [Antwort generieren] [Tickets erstellen]│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Responsive Design

**Breakpoints (Tailwind defaults):**

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| Default | <640px | Single column, no sidebar (mobile — future) |
| `sm` | 640px | Minimal support, not primary target |
| `md` | 768px | Sidebar shown, reduced padding |
| `lg` | 1024px | Full layout, standard |
| `xl` | 1280px | Wide content areas, full KPI row |

**Primary target resolution:** 1280×800+ (MacBook 13", standard office displays)

**Mobile:** Not a v1.0 requirement. The product is a desktop tool for professional users. Mobile is deferred to Phase 3.

---

## 8. Accessibility

### 8.1 Keyboard Navigation

| Action | Shortcut |
|--------|---------|
| Close modal / panel | `Escape` |
| Submit form | `Enter` |
| Navigate sidebar | `Tab` |
| Toggle cluster card | `Space` / `Enter` on focused card |

### 8.2 ARIA Labels

| Element | ARIA |
|---------|------|
| Modal | `role="dialog"` + `aria-modal="true"` + `aria-labelledby="modal-title"` |
| Icon-only buttons | `aria-label="Löschen"` etc. |
| Status badges | `aria-label="Status: running"` |
| Loading spinner | `aria-label="Wird geladen..."` + `aria-live="polite"` |
| Form fields | `htmlFor` + matching `id` on all inputs |

### 8.3 Color Contrast

All text/background color combinations meet WCAG AA (4.5:1 ratio minimum):
- `gray-900` on `white` = 16.1:1 ✅
- `blue-600` on `white` = 4.5:1 ✅
- `red-700` on `red-100` = 5.1:1 ✅
- `green-700` on `green-100` = 5.0:1 ✅

---

## 9. Interaction Patterns

### Loading States

Every async operation shows a loading state. Rules:
1. Disable the triggering button immediately on click (prevents double-submit)
2. Replace button text with spinner (Loader2 icon, `animate-spin`)
3. Show loading indicator in the content area if loading takes >300ms
4. Never show empty state and loading state simultaneously

### Optimistic UI

For status changes in Kanban: update UI immediately, persist in background. If persist fails, revert with error toast.

### Polling Strategy

For pipeline status: `setInterval` at 4-second intervals.
- Start polling when a job is `pending` or `running`
- Stop polling when job is `done` or `failed`
- Clear interval on component unmount (`useEffect` cleanup)
- Use typed intervals: `ReturnType<typeof setInterval>` (not `NodeJS.Timeout`)

### Confirmation Dialogs

Used for: delete data source, delete ticket.

Pattern:
1. User clicks delete
2. Modal appears naming the specific resource: *"BMW Connected wirklich löschen?"*
3. States the consequence: *"Alle 200 Reviews und Analysen werden unwiderruflich gelöscht."*
4. Two buttons: [Abbrechen] (secondary) [Löschen] (danger/red)
5. Enter key = cancel (safe default). Red button requires explicit click.

---

## 10. Micro-interactions

| Trigger | Response |
|---------|---------|
| Hover on card | `shadow-md` transition (`transition-shadow duration-200`) |
| Click on cluster | Smooth expand (`transition-all duration-200`) |
| Button click (loading) | Immediate spinner, button disabled |
| Pipeline stage change | Progress text updates with fade |
| Ticket moved to Done | Card slides into Done column |
| Form submit error | Red border on invalid field, error text below |
| Toast appears | Slides in from right (`translate-x` animation) |

---

*Document Owner: Design / Frontend*
*Last Updated: 2026-07*
*Status: v1.0 — Implemented in React + Tailwind CSS*
