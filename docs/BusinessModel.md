# Business Model — MA Analytics

> *"Price is what you pay. Value is what you get. The job of pricing strategy is to make those two numbers as close together as possible — for the customer."*

---

## 1. Business Model Overview

MA Analytics operates on a **SaaS subscription model** with usage-based scaling. Revenue is predictable and recurring. The unit economics are favorable: marginal cost per additional customer is near zero (ML inference runs locally on the server and LLM calls are limited to brief generation), while customer lifetime value scales with team size and app portfolio size.

**Model type:** B2B SaaS  
**Billing:** Monthly and annual (annual at 20% discount)  
**Primary value metric:** Number of data sources (apps/CSV files) analyzed and Innovation Briefs generated

### Key Differentiators (as of July 2026)

1. **Innovation Lab with Hypothesis-Guided RAG** — No competitor offers hypothesis-driven product brief generation grounded in actual review data. The system embeds the user's hypothesis, retrieves the 500 semantically closest reviews, and generates a brief backed by real evidence.

2. **Signal Graph** — Co-occurrence analysis identifies which signals are OEM infrastructure problems (hubs) vs. standalone product opportunities (edge nodes). This prevents wasting brief generation on dead-end signal clusters.

3. **Signal Exclusion** — Automatic or manual exclusion of previously-explored signal clusters forces concept diversity across brief generations. No other tool does this.

4. **Full-stack in one tool** — Review ingestion → ML pipeline → Innovation Brief → Concept Document → PDF Export → Copilot Chat, without leaving the platform.

5. **Local ML inference** — Embedding and ABSA models run on the server. No per-review API costs. Gross margin is ~85–92%.

---

## 2. Ideal Customer Profile (ICP)

### Primary ICP: Product Builder in Automotive/Consumer Tech

| Dimension | Profile |
|-----------|---------|
| **Company size** | 1–200 employees |
| **Industry** | Automotive software, mobile apps, consumer SaaS |
| **Geography** | DACH region (primary), EU (secondary), English-speaking markets (tertiary) |
| **Tech maturity** | Has a PM function; ships mobile apps; has Google Play presence |
| **Review volume** | 500–50,000+ reviews on Google Play |
| **Current pain** | No systematic way to turn review data into product strategy; Innovation Lab fills this gap |
| **Budget** | €200–2,000/month for product intelligence tooling |
| **Decision maker** | Founder, Head of Product, VP Product |

### Secondary ICP: Agency / Consultancy

| Dimension | Profile |
|-----------|---------|
| **Company type** | Digital agency, product consultancy, VC portfolio support |
| **Use case** | Analyze client apps, deliver Innovation Briefs as a service |
| **Value prop** | White-label MA Analytics output under their own brand |
| **Budget** | €200–500/month per client account |

### Secondary ICP: Startup Founder / Pre-PMF Team

| Dimension | Profile |
|-----------|---------|
| **Stage** | Pre-seed to Series A |
| **Use case** | Understand competitive landscape before building; use Innovation Lab to generate evidence-backed product hypotheses |
| **Value prop** | Replaces 40 hours of manual review analysis with a 5-minute brief generation |
| **Budget** | €49–149/month (solo or small team) |

### Negative ICP

- Companies with fewer than 50 reviews/month (not enough signal)
- Companies requiring on-premise deployment with air-gapped LLMs (Phase 3+)
- Companies without a product decision-making function

---

## 3. Pricing Tiers

### Starter — €49/month

**For:** Solo founders, indie developers, single-app teams

| Feature | Included |
|---------|----------|
| Data sources | 1 |
| Reviews analyzed/month | up to 500 |
| Google Play scraping | ✅ |
| CSV upload | ✅ |
| Dashboard (issues + strengths + KPIs) | ✅ |
| Hybrid search | ✅ |
| Inbox + Kanban | ✅ |
| Innovation Lab | 3 briefs/month |
| Brief Copilot chat | ❌ |
| Document Intelligence | ❌ |
| PDF Export | ✅ |
| AI provider | Groq (fallback) only |
| Team seats | 1 |
| Data retention | 3 months |
| Support | Email, 48h response |

---

### Growth — €149/month

**For:** Product teams at growing apps, small-to-medium companies

| Feature | Included |
|---------|----------|
| Data sources | 5 |
| Reviews analyzed/month | up to 5,000 |
| Everything in Starter | ✅ |
| Innovation Lab | Unlimited briefs |
| Hypothesis-guided RAG retrieval | ✅ |
| Signal graph + exclusion | ✅ |
| Brief Copilot chat | ✅ |
| Document Intelligence (CSDDD, CSRD, regulatory) | ✅ (5 documents) |
| AI provider | Claude Haiku primary + Groq fallback |
| AI reply generation | ✅ |
| AI ticket generation | ✅ |
| Team seats | 3 |
| Data retention | 12 months |
| Support | Email, 24h response |

---

### Scale — €399/month

**For:** Multi-app portfolios, product departments, agencies

| Feature | Included |
|---------|----------|
| Data sources | 20 |
| Reviews analyzed/month | up to 25,000 |
| Everything in Growth | ✅ |
| Competitor analysis (any public app) | ✅ |
| Document Intelligence (unlimited documents) | ✅ |
| Slack integration | ✅ |
| Jira/Linear integration | ✅ |
| Team seats | 10 |
| Data retention | 24 months |
| Priority support | 4h response, dedicated Slack channel |

---

### Agency / White-Label — €299/month per client workspace

**For:** Agencies, consultancies, VC portfolio teams

| Feature | Included |
|---------|----------|
| Unlimited workspaces | ✅ (billed per workspace) |
| White-label branding | ✅ |
| Client-facing PDF export | ✅ |
| API access | ✅ |
| Custom onboarding | ✅ |
| Revenue share option | Negotiable |

---

## 4. Unit Economics

### Customer Acquisition Cost (CAC) Target

| Channel | Est. CAC |
|---------|----------|
| Content marketing (SEO) | €80–150 |
| Product Hunt launch | €20–60 |
| LinkedIn outreach (PM community) | €150–300 |
| Automotive industry events / communities | €100–250 |

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
- Server (Hetzner VPS, 8 vCPU / 32GB RAM): ~€60 fixed, amortized across customers
- ML inference: runs on same server, no per-API-call cost
- PostgreSQL + pgvector: negligible per customer
- Claude Haiku API (brief generation): ~€0.05–0.20/brief depending on token count
- Groq API (fallback + chat): ~€0.01–0.05/request

**Estimated gross margin: 85–92%**

The defining cost advantage: ML pipeline inference (embeddings, ABSA, clustering) runs locally. The only variable AI cost is brief generation, which is bounded and low.

---

## 5. Go-to-Market Strategy

### Phase 1: Community-Led Growth (Months 1–6)

**Target:** Product managers and founders in DACH automotive/consumer tech

**Channels:**
- **Product Hunt launch** — Single biggest early spike. Target: #1 Product of the Day with Innovation Lab as the hook.
- **Indie Hackers** — Document the build-in-public story. "I turned 33,000 BMW app reviews into product strategy with AI."
- **LinkedIn content** — Post weekly Innovation Brief examples from real app review data. Show the signal graph, show the concept output. Let the product demonstrate itself.
- **r/androiddev, r/ProductManagement** — Genuine value contributions + soft product mentions
- **Direct outreach** — 50 PM/founder LinkedIn messages/week; use a real generated brief from their app as the hook ("I ran your app's reviews through our system, here's what I found")

**Goal:** 50 paying customers, €5,000 MRR

### Phase 2: SEO + Content Moat (Months 6–18)

**Content strategy:**
- "How to analyze Google Play reviews for product strategy" — high-intent
- "What 33,000 automotive app reviews reveal about UX failures" — data-driven thought leadership
- Free Innovation Brief for first 3 apps (lead magnet)
- Case studies: "How [Company] used MA Analytics to find a €2M product opportunity in their review data"

**Goal:** 200 paying customers, €25,000 MRR

### Phase 3: Integration Partnerships (Months 12–24)

- Jira Marketplace listing
- Slack App Directory
- Automotive industry analyst coverage (Gartner, IDC)

**Goal:** 500 customers, €75,000 MRR

---

## 6. Competitive Landscape

| Competitor | Strength | Weakness | MA Analytics Advantage |
|------------|----------|----------|------------------------|
| **AppFollow** | Established brand, multi-store | Expensive (€299+/mo), no ML clustering, no brief generation | 2x cheaper, Innovation Lab unique |
| **Appbot** | Good UI, App Store + Play | No AI generation, no signal graph, no hypothesis RAG | AI-native end-to-end workflow |
| **Medallia** | Enterprise-grade | €50,000+/year, 6-month implementation | 100x faster to value |
| **MonkeyLearn** | Flexible ML | DIY, no product context, no LLM generation | Purpose-built from signal to brief |
| **ChatGPT (manual)** | Flexible | No structured data pipeline; user must manually copy reviews | Automated pipeline + hypothesis grounding |
| **Manual (Excel)** | Free | 40-80 hours/month PM time | Time saved = clear ROI |

**Positioning:** MA Analytics is the first tool that goes from "customer reviews" to "investor-ready product brief" automatically — grounded in real data, not hallucination.

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
| Google changes Play Store API | High | Medium | CSV upload as fallback; Apple App Store support planned |
| Anthropic rate limits / pricing increase | Medium | Medium | Groq cascade fallback; local model option |
| Large competitor copies features | Medium | High | Signal graph + hypothesis RAG are defensible innovations; speed moat |
| LLM costs rise dramatically | Low | Medium | Local ML inference as primary; LLM only for brief generation |
| Low conversion from free trial | Medium | High | Optimize onboarding; guaranteed first brief in <5 min |
| Regulatory (GDPR on review data) | Low | High | Reviews are public data; no PII stored without consent |
| Signal exclusion limits concept diversity | Low | Low | Manual override via Signal-Steuerung panel; fallback without exclusion |

---

*Document Owner: Founder / Business Strategy*  
*Last Updated: 2026-07*  
*Status: Living Document — v1.0 system complete*
