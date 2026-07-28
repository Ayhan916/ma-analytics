# Vision — MA Analytics

## The Problem

Every product team is flying blind.

Features get shipped based on stakeholder pressure, gut feel, and whoever talks loudest in the sprint planning meeting. The voice of the customer — the most valuable signal in product development — is buried in tens of thousands of unread reviews, support tickets, and feedback threads that nobody has time to process systematically.

The result: product roadmaps that don't reflect what users actually need. Wasted engineering cycles. User churn that was predictable but undetected.

This is not a data problem. Companies have more customer data than ever. This is an **intelligence problem** — the gap between "we have reviews" and "we know what to build next."

---

## The Core Insight

When you read 10,000 customer reviews, you are reading a distributed product specification. Users are telling you, in plain language, what is broken, what they wish existed, and what they would pay to have.

Every 1-star review is an unsubmitted bug report.  
Every "I wish this app could..." is an unwritten feature request.  
The patterns across thousands of reviews are the roadmap that no product manager has time to write.

MA Analytics extracts that specification and makes it queryable, explorable, and generatable.

---

## Current State (July 2026)

The system is production-capable with the following modules fully implemented:

**Data pipeline:** Google Play scraper + CSV import → ABSA sentiment extraction → multilingual sentence embeddings → signal classification → KMeans clustering. Processing 33,649 reviews from 5 automotive apps (BMW, Mercedes-Benz, Audi, Volkswagen) with 41,620 extracted signals across 25 feature categories.

**Innovation Lab:** The primary intelligence output module. Takes structured signals and generates data-backed product briefs through:
- Hypothesis-guided RAG retrieval: semantic search over 32,300 embedded reviews to find evidence for a user-supplied hypothesis before signal aggregation
- Signal graph analysis: identifies hub signals (systemic OEM infrastructure problems) vs. edge signals (standalone product opportunities)
- Signal exclusion: automatic or manual exclusion of previously-explored signal clusters to force exploration of new product territory
- Multi-provider AI generation: Claude Haiku primary, Groq cascade fallback
- Long-form concept documentation: 1200+ word strategic product documents
- PDF export, Copilot chat, brief history

**Hybrid search:** Semantic vector search + BM25 full-text search fused via Reciprocal Rank Fusion over all review content.

**Document intelligence:** PDF ingestion (CSDDD, CSRD, regulatory documents), chunk embedding, RAG Q&A, structured metric extraction.

**Inbox + Kanban:** Customer message management with AI reply generation and ticket tracking.

---

## What the System Is Good At

- Finding the strongest recurring pain patterns across large review datasets
- Differentiating between signals that are OEM infrastructure problems (hard to productise for third parties) vs. standalone product opportunities
- Generating structured, evidence-backed product briefs faster than a human researcher
- Exploring different product territories by steering signal selection
- Answering semantic questions over regulatory documents

---

## What the System Is Not Good At (Known Limitations)

**Signal resolution is coarse.** 25 feature labels for 33,649 reviews means each label covers a wide range of user problems. "Updates" includes OTA failures, data loss on update, UI changes after update, and slow update download times — all different product opportunities.

**Reviews are a biased sample.** App store reviewers skew toward extreme experiences (very happy or very angry). The silent majority — users who find the app adequate — leave no reviews. Signal extraction reflects the complaining 5%, not the full user base.

**No go-to-market validation.** Generated briefs describe what users want; they don't validate whether the market will pay, whether OEMs are already building it internally, or whether a startup can realistically compete. The LLM generates plausible-sounding market sizing that has no empirical basis.

**Scope is narrow.** Five German premium OEM apps are a highly correlated dataset. The signals cluster around shared platform problems rather than diverse product opportunities. Cross-industry, cross-geography comparisons would surface genuinely novel patterns.

**No feedback loop.** The system doesn't learn from which briefs the user found valuable, which hypotheses led to better outputs, or which signal combinations produced actionable insights.

---

## Where This Is Going

**Near-term (next capabilities that would materially increase intelligence quality):**

1. **Finer signal taxonomy** — Sub-classify each of the 25 current labels into 5–10 sub-signals. "Updates" becomes "OTA failure," "data loss on update," "update notification spam," etc. This increases concept diversity without changing the data layer.

2. **Cross-source intelligence** — Link review signals to regulatory documents. "Users complain about data deletion after updates" + "GDPR Article 17 right to erasure obligation" = a compliance-driven product opportunity. The data layers exist; the cross-referencing doesn't.

3. **Competitive intelligence layer** — Index OEM job postings, patent filings, app changelog notes. A signal that has an active OEM hiring effort behind it is not a product opportunity for a third party. A signal with no internal OEM investment is.

**Medium-term (platform direction):**

4. **Multi-source ingestion** — Apple App Store, Twitter/X mentions, Reddit threads, support ticket exports. Reviews are one input; the full customer voice is distributed across multiple channels.

5. **Real-time monitoring** — Weekly re-scrape + delta analysis. Alert when a new signal cluster emerges or a known signal suddenly spikes in severity.

6. **Validation loop** — Track which generated briefs led to user action (saved, exported, shared, built). Use that signal to improve generation quality over time.

---

## The Long-Term Opportunity

The automotive software market is converging on a common problem: manufacturers built mechanical products for 100 years and are now expected to ship competitive software products. Their software teams are small relative to their hardware teams. Their app store ratings reflect this gap.

MA Analytics sits at the intersection of this gap: large volumes of explicit user frustration, structured into signal categories, queryable by semantic search, exploitable through AI-generated product concepts.

The opportunity is not to build the product for the OEMs. The opportunity is to be the intelligence layer that tells founders, investors, and product teams: here is what users of the largest automotive apps in the world actually need, here is the evidence, and here is a product concept that could address it.
