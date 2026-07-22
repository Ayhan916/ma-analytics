# Business Model — MA Analytics

> *"Price is what you pay. Value is what you get. The job of pricing strategy is to make those two numbers as close together as possible — for the customer."*

---

## 1. Business Model Overview

MA Analytics operates on a **SaaS subscription model** with usage-based scaling. Revenue is predictable and recurring. The unit economics are favorable: marginal cost per additional customer is near zero (ML inference runs locally on the server), while customer lifetime value scales with team size and app portfolio size.

**Model type:** B2B SaaS
**Billing:** Monthly and annual (annual at 20% discount)
**Primary value metric:** Number of data sources (apps/CSV files) analyzed

---

## 2. Ideal Customer Profile (ICP)

### Primary ICP: Growth-Stage Mobile App Company

| Dimension | Profile |
|-----------|---------|
| **Company size** | 10–200 employees |
| **Industry** | Mobile apps, SaaS, Consumer tech, E-commerce |
| **Geography** | DACH region (primary), EU (secondary), English-speaking markets (tertiary) |
| **Tech maturity** | Has a PM team, uses Jira/Linear, ships 2-4 releases/month |
| **Review volume** | 100–10,000 reviews/month on Google Play |
| **Current pain** | PM manually reads/tags reviews; no systematic process |
| **Budget** | €500–2,000/month for product intelligence tooling |
| **Decision maker** | Head of Product, VP Product, or Founder |

### Secondary ICP: Agency / Consultancy

| Dimension | Profile |
|-----------|---------|
| **Company type** | Digital agency, product consultancy |
| **Use case** | Analyze client apps, deliver insights as a service |
| **Value prop** | White-label MA Analytics under their own brand |
| **Budget** | €200–500/month per client account |

### Negative ICP (explicitly not targeted)

- Companies with fewer than 50 reviews/month (not enough signal for clustering)
- Enterprise companies requiring on-premise deployment (Phase 2+)
- Companies without a product manager role (no one to act on insights)

---

## 3. Pricing Tiers

### Starter — €49/month

**For:** Indie developers, founders, single-app teams

| Feature | Included |
|---------|----------|
| Data sources | 1 |
| Reviews analyzed/month | up to 500 |
| Google Play scraping | ✅ |
| CSV upload | ✅ |
| Dashboard (issues + strengths) | ✅ |
| AI Insight (rule-based) | ✅ |
| Inbox | ✅ |
| Kanban Board | ✅ |
| AI-powered summaries (Groq) | ❌ |
| Team seats | 1 |
| Data retention | 3 months |
| Support | Email, 48h response |

**Target conversion:** Free trial → Starter in week 1 if they see at least 3 actionable insights.

---

### Growth — €149/month

**For:** Product teams at growing apps, small-to-medium companies

| Feature | Included |
|---------|----------|
| Data sources | 5 |
| Reviews analyzed/month | up to 2,000 |
| Google Play scraping | ✅ |
| CSV upload | ✅ |
| Dashboard | ✅ |
| AI-powered summaries (Groq) | ✅ |
| AI Reply generation | ✅ |
| AI Ticket generation | ✅ |
| Team seats | 3 |
| Data retention | 12 months |
| Trend analysis (over time) | ✅ |
| Support | Email, 24h response |

---

### Scale — €399/month

**For:** Multi-app portfolios, product departments

| Feature | Included |
|---------|----------|
| Data sources | 20 |
| Reviews analyzed/month | up to 10,000 |
| Everything in Growth | ✅ |
| Competitor analysis (any public app) | ✅ |
| Slack integration | ✅ |
| Jira/Linear integration | ✅ |
| Team seats | 10 |
| Data retention | 24 months |
| Custom cluster labels | ✅ |
| Priority support | 4h response, dedicated Slack channel |

---

### Agency / White-Label — €299/month per client workspace

**For:** Agencies, consultancies

| Feature | Included |
|---------|----------|
| Unlimited workspaces | ✅ (billed per workspace) |
| White-label branding | ✅ |
| Client-facing reports (PDF export) | ✅ |
| API access | ✅ |
| Custom onboarding | ✅ |
| Revenue share option | negotiable |

---

## 4. Unit Economics

### Customer Acquisition Cost (CAC) Target

| Channel | Est. CAC |
|---------|----------|
| Content marketing (SEO) | €80–150 |
| Product Hunt launch | €20–60 |
| LinkedIn outreach (PM community) | €150–300 |
| App store developer targeting | €100–200 |

**Target blended CAC:** ≤ €200

### Customer Lifetime Value (LTV)

| Tier | MRR | Avg. Lifespan | LTV |
|------|-----|---------------|-----|
| Starter | €49 | 8 months | €392 |
| Growth | €149 | 18 months | €2,682 |
| Scale | €399 | 30 months | €11,970 |

**LTV:CAC ratio target:** ≥ 5:1 (healthy SaaS benchmark is 3:1)

### Gross Margin

Infrastructure cost per customer per month:
- Server (Hetzner VPS, 8 vCPU): ~€40 fixed, amortized across customers
- ML inference: runs on same server, no per-API-call cost
- PostgreSQL: negligible per customer
- Groq API (if used): ~€0.01 per 1,000 tokens → ~€0.10/customer/month

**Estimated gross margin: 85–92%**

This is the defining advantage of running ML locally vs. calling GPT-4 API per review.

---

## 5. Go-to-Market Strategy

### Phase 1: Community-Led Growth (Months 1–6)

**Target:** Product managers in DACH region

**Channels:**
- **Product Hunt launch** — Single biggest early spike. Target #1 Product of the Day.
- **Indie Hackers** — Document the build-in-public story. "I built an AI review analyzer in 6 weeks."
- **LinkedIn content** — Post weekly "what X customer reviews actually reveal" breakdowns using MA Analytics output. Show the product, don't tell.
- **r/androiddev, r/ProductManagement** — Genuine value contributions + soft product mentions
- **Direct outreach** — 50 PM LinkedIn messages/week, personalized with their specific app's review analysis as a hook

**Goal:** 50 paying customers, €5,000 MRR

### Phase 2: SEO + Content Moat (Months 6–18)

**Target:** Organic PM/developer traffic

**Content strategy:**
- "How to analyze Google Play reviews" — high-intent keyword
- "App review sentiment analysis" — growing keyword
- Case studies: "How [Company X] used customer feedback to reduce churn by 30%"
- Free tools: "Free Google Play review analyzer" (lead magnet, limited features)

**Goal:** 200 paying customers, €25,000 MRR

### Phase 3: Integration Partnerships (Months 12–24)

- Jira Marketplace listing
- Slack App Directory
- AppFollow / SensorTower competitive positioning

**Goal:** 500 customers, €75,000 MRR

---

## 6. Competitive Landscape

| Competitor | Strength | Weakness | MA Analytics Advantage |
|------------|----------|----------|------------------------|
| **AppFollow** | Established brand, multi-store | Expensive (€299+/mo), no ML clustering | 5x cheaper, better NLP |
| **Appbot** | Good UI, App Store + Play | No AI generation, no Kanban | AI ticket/reply generation |
| **Medallia** | Enterprise-grade | €50,000+/year, 6-month implementation | 100x faster to value |
| **MonkeyLearn** | Flexible ML | DIY, no product context | Purpose-built for app teams |
| **Manual (Excel)** | Free | 4-8 hours/month PM time | Time saved = clear ROI |

**Positioning:** MA Analytics is the first tool that closes the loop from customer feedback to Kanban ticket — in one platform, at a price that doesn't require a VP approval.

---

## 7. Revenue Projections (Conservative)

| Month | Customers | MRR | ARR |
|-------|-----------|-----|-----|
| 3 | 20 | €1,500 | €18,000 |
| 6 | 60 | €6,000 | €72,000 |
| 12 | 180 | €22,000 | €264,000 |
| 18 | 400 | €55,000 | €660,000 |
| 24 | 700 | €100,000 | €1,200,000 |

**Path to €1M ARR:** 18–24 months from launch, requiring no external funding.

---

## 8. Key Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Google changes Play Store API | High | Medium | CSV upload as fallback; AppStore support |
| Large competitor copies features | Medium | High | Speed of innovation; community moat |
| LLM costs rise dramatically | Low | Medium | Local ML inference as primary; LLM as enhancement |
| Low conversion from free trial | Medium | High | Optimize onboarding; guaranteed first-insight in <5 min |
| Regulatory (GDPR on review data) | Low | High | Reviews are public data; no PII stored without consent |

---

*Document Owner: Founder / Business Strategy*
*Last Updated: 2026-07*
*Status: Living Document*
