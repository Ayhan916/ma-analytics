from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.cluster import Cluster, ClusterReview, ClusterType
from app.models.review import Review
from app.models.datasource import DataSource
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ReviewOut(BaseModel):
    id: str
    content: str
    score: Optional[float]
    sentiment: Optional[str]


class ClusterOut(BaseModel):
    id: str
    label: str
    mentions: int
    summary: Optional[str]
    examples: list[ReviewOut]


class SentimentBreakdown(BaseModel):
    positive: int
    negative: int
    neutral: int
    total: int


class DashboardSummary(BaseModel):
    datasource_id: str
    datasource_name: str
    review_count: int
    avg_rating: Optional[float]
    sentiment: SentimentBreakdown
    top_issues: list[ClusterOut]
    top_strengths: list[ClusterOut]


async def _get_datasource_or_404(db: AsyncSession, datasource_id: str, user_id: str) -> DataSource:
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == user_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return ds


async def _sentiment_breakdown(db: AsyncSession, datasource_id: str) -> SentimentBreakdown:
    """Aggregate sentiment counts in the DB — no ORM object loading."""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((Review.sentiment == "positive", 1), else_=0)).label("positive"),
            func.sum(case((Review.sentiment == "negative", 1), else_=0)).label("negative"),
            func.sum(case((Review.sentiment == "neutral", 1), else_=0)).label("neutral"),
        ).where(Review.datasource_id == datasource_id)
    )
    row = result.one()
    return SentimentBreakdown(
        total=row.total or 0,
        positive=row.positive or 0,
        negative=row.negative or 0,
        neutral=row.neutral or 0,
    )


async def _avg_rating(db: AsyncSession, datasource_id: str) -> Optional[float]:
    result = await db.execute(
        select(func.avg(Review.score)).where(
            Review.datasource_id == datasource_id,
            Review.score.isnot(None),
        )
    )
    avg = result.scalar()
    return round(float(avg), 2) if avg is not None else None


async def _load_clusters(db: AsyncSession, datasource_id: str, cluster_type: ClusterType, limit: int = 5) -> list[ClusterOut]:
    result = await db.execute(
        select(Cluster)
        .where(Cluster.datasource_id == datasource_id, Cluster.type == cluster_type)
        .order_by(Cluster.mentions.desc())
        .limit(limit)
    )
    clusters = result.scalars().all()

    out = []
    for c in clusters:
        # Load example reviews via junction table
        examples_result = await db.execute(
            select(Review)
            .join(ClusterReview, ClusterReview.review_id == Review.id)
            .where(ClusterReview.cluster_id == c.id, ClusterReview.is_example.is_(True))
            .limit(5)
        )
        examples = [
            ReviewOut(id=r.id, content=r.content, score=r.score, sentiment=r.sentiment)
            for r in examples_result.scalars().all()
        ]
        out.append(ClusterOut(id=c.id, label=c.label, mentions=c.mentions, summary=c.summary, examples=examples))

    return out


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds = await _get_datasource_or_404(db, datasource_id, current_user.id)

    review_count_result = await db.execute(
        select(func.count()).select_from(Review).where(Review.datasource_id == datasource_id)
    )
    review_count = review_count_result.scalar() or 0

    sentiment = await _sentiment_breakdown(db, datasource_id)
    avg_rating = await _avg_rating(db, datasource_id)
    top_issues = await _load_clusters(db, datasource_id, ClusterType.issue)
    top_strengths = await _load_clusters(db, datasource_id, ClusterType.strength)

    return DashboardSummary(
        datasource_id=ds.id,
        datasource_name=ds.name,
        review_count=review_count,
        avg_rating=avg_rating,
        sentiment=sentiment,
        top_issues=top_issues,
        top_strengths=top_strengths,
    )


@router.get("/issues", response_model=list[ClusterOut])
async def get_issues(
    datasource_id: str = Query(...),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_datasource_or_404(db, datasource_id, current_user.id)
    return await _load_clusters(db, datasource_id, ClusterType.issue, limit=limit)


@router.get("/strengths", response_model=list[ClusterOut])
async def get_strengths(
    datasource_id: str = Query(...),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_datasource_or_404(db, datasource_id, current_user.id)
    return await _load_clusters(db, datasource_id, ClusterType.strength, limit=limit)


import math


class AppCompetitiveData(BaseModel):
    id: str
    name: str
    country: str
    review_count: int
    avg_rating: Optional[float]
    sentiment: SentimentBreakdown
    negative_pct: float
    opportunity_score: float
    top_issue: Optional[str]
    top_issue_mentions: int


class MarketPainPoint(BaseModel):
    label: str
    affected_apps: list[str]
    app_count: int
    total_mentions: int
    opportunity_score: float
    is_market_issue: bool


INDUSTRY_LABELS: dict[str, str] = {
    'automotive':    'Automobil',
    'banking':       'Banking & Finanzen',
    'retail':        'Handel & E-Commerce',
    'healthcare':    'Gesundheit',
    'travel':        'Reise & Transport',
    'entertainment': 'Entertainment',
    'other':         'Sonstige',
}


class IndustryGroup(BaseModel):
    industry: str
    industry_label: str
    apps: list[AppCompetitiveData]
    market_pain_points: list[MarketPainPoint]


class CompetitiveReport(BaseModel):
    groups: list[IndustryGroup]


def _opportunity_score(negative_pct: float, mentions: int, avg_rating: Optional[float]) -> float:
    """Higher = bigger market gap to exploit.
    Combines: how unhappy users are × how many mention it × how bad the rating is.
    """
    rating_gap = 5.0 - (avg_rating or 3.0)
    return round(negative_pct * math.log1p(mentions) * rating_gap, 1)


@router.get("/competitive", response_model=CompetitiveReport)
async def get_competitive(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate competitive intelligence across all user datasources."""
    from sqlalchemy import text

    ds_result = await db.execute(
        select(DataSource).where(DataSource.user_id == current_user.id)
    )
    datasources = ds_result.scalars().all()

    from collections import defaultdict

    # Group datasources by industry
    by_industry: dict[str, list] = defaultdict(list)
    for ds in datasources:
        by_industry[ds.industry].append(ds)

    groups: list[IndustryGroup] = []

    for industry, industry_ds in by_industry.items():
        apps: list[AppCompetitiveData] = []
        raw_issues: list[tuple[str, str, int, float]] = []

        for ds in industry_ds:
            review_count_result = await db.execute(
                select(func.count()).select_from(Review).where(Review.datasource_id == ds.id)
            )
            review_count = review_count_result.scalar() or 0
            if review_count == 0:
                continue

            sentiment = await _sentiment_breakdown(db, ds.id)
            avg_rating = await _avg_rating(db, ds.id)
            negative_pct = round(sentiment.negative / sentiment.total * 100, 1) if sentiment.total else 0.0
            app_opp_score = _opportunity_score(negative_pct, sentiment.negative, avg_rating)

            top_signal_result = await db.execute(
                text("""
                    SELECT rs.feature, COUNT(*) AS mentions
                    FROM review_signals rs
                    WHERE rs.datasource_id = :ds_id
                      AND rs.signal_type IN ('bug', 'performance', 'ux')
                      AND rs.feature != 'General'
                    GROUP BY rs.feature
                    ORDER BY mentions DESC
                    LIMIT 1
                """),
                {"ds_id": ds.id},
            )
            top_signal = top_signal_result.one_or_none()

            apps.append(AppCompetitiveData(
                id=ds.id,
                name=ds.name,
                country=ds.scrape_country or '',
                review_count=review_count,
                avg_rating=avg_rating,
                sentiment=sentiment,
                negative_pct=negative_pct,
                opportunity_score=app_opp_score,
                top_issue=top_signal.feature if top_signal else None,
                top_issue_mentions=top_signal.mentions if top_signal else 0,
            ))

            issues_result = await db.execute(
                text("""
                    SELECT rs.feature, COUNT(*) AS mentions
                    FROM review_signals rs
                    WHERE rs.datasource_id = :ds_id
                      AND rs.signal_type IN ('bug', 'performance', 'ux')
                      AND rs.feature != 'General'
                    GROUP BY rs.feature
                    ORDER BY mentions DESC
                    LIMIT 10
                """),
                {"ds_id": ds.id},
            )
            for row in issues_result.fetchall():
                issue_opp = _opportunity_score(negative_pct, row.mentions, avg_rating)
                raw_issues.append((row.feature, ds.name, row.mentions, issue_opp))

        if not apps:
            continue

        # Aggregate pain points within this industry
        agg: dict[str, dict] = defaultdict(lambda: {"mentions": 0, "apps": [], "scores": []})
        for feature, app_name, mentions, score in raw_issues:
            agg[feature]["mentions"] += mentions
            agg[feature]["apps"].append(app_name)
            agg[feature]["scores"].append(score)

        pain_points: list[MarketPainPoint] = []
        for feature, data in agg.items():
            app_count = len(data["apps"])
            pain_points.append(MarketPainPoint(
                label=feature,
                affected_apps=data["apps"],
                app_count=app_count,
                total_mentions=data["mentions"],
                opportunity_score=round(sum(data["scores"]) / len(data["scores"]), 1),
                is_market_issue=app_count >= 2,
            ))

        apps.sort(key=lambda a: a.opportunity_score, reverse=True)
        pain_points.sort(key=lambda p: (-p.app_count, -p.total_mentions))

        groups.append(IndustryGroup(
            industry=industry,
            industry_label=INDUSTRY_LABELS.get(industry, industry.capitalize()),
            apps=apps,
            market_pain_points=pain_points[:25],
        ))

    # Automotive first, then alphabetical
    groups.sort(key=lambda g: (0 if g.industry == 'automotive' else 1, g.industry_label))

    return CompetitiveReport(groups=groups)


class SentimentTrendPoint(BaseModel):
    month: str
    positive: int
    negative: int
    neutral: int
    total: int
    avg_rating: Optional[float] = None


class VersionMarker(BaseModel):
    month: str
    version: str


class SentimentTrend(BaseModel):
    datasource_id: str
    points: list[SentimentTrendPoint]
    version_markers: list[VersionMarker] = []


@router.get("/sentiment-trend", response_model=SentimentTrend)
async def get_sentiment_trend(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_datasource_or_404(db, datasource_id, current_user.id)

    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT
                to_char(date_trunc('month', COALESCE(reviewed_at, created_at)), 'YYYY-MM') AS month,
                COUNT(*) FILTER (WHERE sentiment = 'positive') AS positive,
                COUNT(*) FILTER (WHERE sentiment = 'negative') AS negative,
                COUNT(*) FILTER (WHERE sentiment = 'neutral')  AS neutral,
                COUNT(*) AS total,
                ROUND(AVG(score) FILTER (WHERE score IS NOT NULL)::numeric, 2) AS avg_rating
            FROM reviews
            WHERE datasource_id = :ds_id
              AND COALESCE(reviewed_at, created_at) IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """),
        {"ds_id": datasource_id},
    )
    rows = result.fetchall()
    points = [
        SentimentTrendPoint(
            month=row.month,
            positive=row.positive or 0,
            negative=row.negative or 0,
            neutral=row.neutral or 0,
            total=row.total or 0,
            avg_rating=float(row.avg_rating) if row.avg_rating is not None else None,
        )
        for row in rows
    ]

    # Version markers: first month each version appeared in reviews
    ver_result = await db.execute(
        text("""
            SELECT
                to_char(date_trunc('month', MIN(COALESCE(reviewed_at, created_at))), 'YYYY-MM') AS month,
                version
            FROM reviews
            WHERE datasource_id = :ds_id
              AND version IS NOT NULL AND version != ''
              AND COALESCE(reviewed_at, created_at) IS NOT NULL
            GROUP BY version
            ORDER BY MIN(COALESCE(reviewed_at, created_at))
        """),
        {"ds_id": datasource_id},
    )
    version_markers = [
        VersionMarker(month=row.month, version=row.version)
        for row in ver_result.fetchall()
    ]

    return SentimentTrend(
        datasource_id=datasource_id,
        points=points,
        version_markers=version_markers,
    )


# ─── Version Analysis ────────────────────────────────────────────────────────

class VersionClusterItem(BaseModel):
    cluster_id: str
    label: str
    cluster_type: str
    mentions_in_version: int
    total_cluster_mentions: int
    pct_of_version: float      # mentions_in_version / version_review_count * 100


class VersionStat(BaseModel):
    version: str
    version_source_mix: str    # e.g. "provided" | "inferred" | "mixed"
    review_count: int
    negative_pct: float
    first_seen: str
    last_seen: str
    clusters: list[VersionClusterItem]


class VersionAnalysis(BaseModel):
    datasource_id: str
    versions: list[VersionStat]


@router.get("/version-analysis", response_model=VersionAnalysis)
async def get_version_analysis(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_datasource_or_404(db, datasource_id, current_user.id)

    from sqlalchemy import text

    # All versions with review stats
    version_rows = await db.execute(text("""
        SELECT
            version,
            COUNT(*)                                                        AS review_count,
            COUNT(*) FILTER (WHERE sentiment = 'negative')                  AS negative_count,
            MIN(reviewed_at)                                                AS first_seen,
            MAX(reviewed_at)                                                AS last_seen,
            CASE
                WHEN COUNT(*) FILTER (WHERE version_source = 'provided') = COUNT(*) THEN 'provided'
                WHEN COUNT(*) FILTER (WHERE version_source = 'inferred') = COUNT(*) THEN 'inferred'
                ELSE 'mixed'
            END                                                             AS version_source_mix
        FROM reviews
        WHERE datasource_id = :ds_id
          AND version IS NOT NULL
        GROUP BY version
        ORDER BY MIN(reviewed_at)
    """), {"ds_id": datasource_id})
    version_rows = version_rows.fetchall()

    if not version_rows:
        return VersionAnalysis(datasource_id=datasource_id, versions=[])

    # All clusters for this datasource with their review-version mapping
    cluster_rows = await db.execute(text("""
        SELECT
            c.id            AS cluster_id,
            c.label,
            c.type          AS cluster_type,
            c.mentions      AS total_mentions,
            r.version
        FROM clusters c
        JOIN cluster_reviews cr ON cr.cluster_id = c.id
        JOIN reviews r           ON r.id = cr.review_id
        WHERE c.datasource_id = :ds_id
          AND r.version IS NOT NULL
    """), {"ds_id": datasource_id})
    cluster_rows = cluster_rows.fetchall()

    # Index: version → cluster_id → count
    from collections import defaultdict
    version_cluster_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cluster_meta: dict[str, dict] = {}
    for row in cluster_rows:
        version_cluster_counts[row.version][row.cluster_id] += 1
        if row.cluster_id not in cluster_meta:
            cluster_meta[row.cluster_id] = {
                "label": row.label,
                "cluster_type": row.cluster_type,
                "total_mentions": row.total_mentions,
            }

    versions = []
    for vr in version_rows:
        v_count = vr.review_count or 1
        neg_pct = round((vr.negative_count or 0) / v_count * 100, 1)

        clusters = []
        for cid, cnt in sorted(
            version_cluster_counts.get(vr.version, {}).items(),
            key=lambda x: x[1], reverse=True
        ):
            meta = cluster_meta[cid]
            clusters.append(VersionClusterItem(
                cluster_id=cid,
                label=meta["label"],
                cluster_type=str(meta["cluster_type"]),
                mentions_in_version=cnt,
                total_cluster_mentions=meta["total_mentions"],
                pct_of_version=round(cnt / v_count * 100, 1),
            ))

        versions.append(VersionStat(
            version=vr.version,
            version_source_mix=vr.version_source_mix,
            review_count=vr.review_count,
            negative_pct=neg_pct,
            first_seen=vr.first_seen.strftime("%Y-%m-%d") if vr.first_seen else "",
            last_seen=vr.last_seen.strftime("%Y-%m-%d") if vr.last_seen else "",
            clusters=clusters,
        ))

    return VersionAnalysis(datasource_id=datasource_id, versions=versions)


# ─── Version Compare ─────────────────────────────────────────────────────────

class VersionCompareResult(BaseModel):
    cluster_id: str
    cluster_label: str
    cluster_type: str
    v1: str
    v2: str
    v1_mentions: int
    v2_mentions: int
    v1_review_count: int
    v2_review_count: int
    trend: str                  # 'new' | 'resolved' | 'declining' | 'persistent' | 'worsening' | 'unknown'
    verdict: str                # 'resolved' | 'persistent' | 'no_evidence'
    analysis: str
    v1_examples: list[str]
    v2_examples: list[str]


@router.get("/version-compare", response_model=VersionCompareResult)
async def get_version_compare(
    datasource_id: str = Query(...),
    cluster_id: str = Query(...),
    v1: str = Query(...),
    v2: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_datasource_or_404(db, datasource_id, current_user.id)
    from sqlalchemy import text
    from app.core.config import settings

    # Load cluster meta
    cluster_result = await db.execute(
        select(Cluster).where(Cluster.id == cluster_id, Cluster.datasource_id == datasource_id)
    )
    cluster = cluster_result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Reviews per version for this cluster
    async def get_version_reviews(version: str) -> list[str]:
        rows = await db.execute(text("""
            SELECT r.content
            FROM reviews r
            JOIN cluster_reviews cr ON cr.review_id = r.id
            WHERE cr.cluster_id = :cid AND r.version = :version
            ORDER BY r.reviewed_at DESC
            LIMIT 8
        """), {"cid": cluster_id, "version": version})
        return [row.content for row in rows.fetchall()]

    async def get_version_review_count(version: str) -> int:
        row = await db.execute(text("""
            SELECT COUNT(*) FROM reviews
            WHERE datasource_id = :ds_id AND version = :version
        """), {"ds_id": datasource_id, "version": version})
        return row.scalar() or 0

    v1_examples = await get_version_reviews(v1)
    v2_examples = await get_version_reviews(v2)
    v1_total = await get_version_review_count(v1)
    v2_total = await get_version_review_count(v2)

    v1_mentions = len(v1_examples)  # up to 8 — get exact count separately
    v2_mentions = len(v2_examples)

    # Exact mention counts
    async def get_mention_count(version: str) -> int:
        row = await db.execute(text("""
            SELECT COUNT(*) FROM reviews r
            JOIN cluster_reviews cr ON cr.review_id = r.id
            WHERE cr.cluster_id = :cid AND r.version = :version
        """), {"cid": cluster_id, "version": version})
        return row.scalar() or 0

    v1_mentions = await get_mention_count(v1)
    v2_mentions = await get_mention_count(v2)

    # Trend berechnen (normalisiert auf Review-Volumen)
    v1_rate = (v1_mentions / v1_total * 100) if v1_total else 0
    v2_rate = (v2_mentions / v2_total * 100) if v2_total else 0

    if v1_mentions == 0 and v2_mentions > 0:
        trend = "new"
    elif v1_mentions > 0 and v2_mentions == 0:
        trend = "resolved"
    elif v2_rate < v1_rate * 0.5:
        trend = "declining"
    elif v2_rate > v1_rate * 1.5:
        trend = "worsening"
    else:
        trend = "persistent"

    # LLM-Analyse
    analysis = ""
    verdict = "no_evidence"

    if settings.GROQ_API_KEY and (v1_examples or v2_examples):
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)

            v1_text = "\n".join(f"- {t[:200]}" for t in v1_examples[:5]) or "Keine Reviews vorhanden."
            v2_text = "\n".join(f"- {t[:200]}" for t in v2_examples[:5]) or "Keine Reviews vorhanden."

            prompt = f"""Du analysierst App-Store-Reviews für das Problem: "{cluster.label}"

VERSION {v1} ({v1_mentions} Erwähnungen von {v1_total} Reviews):
{v1_text}

VERSION {v2} ({v2_mentions} Erwähnungen von {v2_total} Reviews):
{v2_text}

Beantworte folgende Fragen in 3–4 Sätzen auf Deutsch:
1. Liegt das Problem aus {v1} auch in {v2} noch vor?
2. Gibt es konkrete Hinweise in den Reviews, dass es behoben wurde?
3. Wenn keine Hinweise: Schreibe "Es gibt keine Hinweise auf eine Behebung."

Antworte NUR mit der Analyse, ohne Einleitung."""

            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.2,
            )
            analysis = resp.choices[0].message.content.strip()

            # Verdict aus Trend + LLM-Antwort ableiten
            analysis_lower = analysis.lower()
            if trend == "resolved" or "behoben" in analysis_lower or "gelöst" in analysis_lower:
                verdict = "resolved"
            elif "keine hinweise" in analysis_lower or trend == "unknown":
                verdict = "no_evidence"
            else:
                verdict = "persistent"

        except Exception:
            analysis = "LLM-Analyse nicht verfügbar."

    if not analysis:
        if trend == "resolved":
            analysis = f"Das Problem '{cluster.label}' trat in {v1} in {v1_mentions} Reviews auf, in {v2} gibt es keine Erwähnungen mehr. Es gibt Hinweise auf eine Behebung."
            verdict = "resolved"
        elif trend == "new":
            analysis = f"Das Problem '{cluster.label}' trat in {v1} nicht auf, erschien aber in {v2} mit {v2_mentions} Erwähnungen erstmals."
            verdict = "persistent"
        elif v1_mentions == 0 and v2_mentions == 0:
            analysis = f"Es gibt keine Hinweise auf dieses Problem in beiden Versionen."
            verdict = "no_evidence"
        else:
            analysis = f"Es gibt keine Hinweise auf eine Behebung zwischen {v1} und {v2}."
            verdict = "no_evidence"

    return VersionCompareResult(
        cluster_id=cluster_id,
        cluster_label=cluster.label,
        cluster_type=cluster.type.value,
        v1=v1, v2=v2,
        v1_mentions=v1_mentions,
        v2_mentions=v2_mentions,
        v1_review_count=v1_total,
        v2_review_count=v2_total,
        trend=trend,
        verdict=verdict,
        analysis=analysis,
        v1_examples=v1_examples[:3],
        v2_examples=v2_examples[:3],
    )


class InsightResponse(BaseModel):
    insight: str
    generated_by: str


@router.get("/insight", response_model=InsightResponse)
async def get_insight(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings

    await _get_datasource_or_404(db, datasource_id, current_user.id)

    sentiment = await _sentiment_breakdown(db, datasource_id)
    top_issues = await _load_clusters(db, datasource_id, ClusterType.issue, limit=3)
    top_strengths = await _load_clusters(db, datasource_id, ClusterType.strength, limit=3)

    if settings.GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            issues_text = ", ".join(c.label for c in top_issues) or "none found"
            strengths_text = ", ".join(c.label for c in top_strengths) or "none found"
            prompt = (
                f"Based on {sentiment.total} app reviews "
                f"({sentiment.positive} positive, {sentiment.negative} negative, {sentiment.neutral} neutral):\n"
                f"Top Issues: {issues_text}\n"
                f"Top Strengths: {strengths_text}\n\n"
                f"Write a concise 3-sentence executive summary with the most important finding "
                f"and one concrete, actionable recommendation for the product team."
            )
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
                temperature=0.3,
            )
            return InsightResponse(
                insight=response.choices[0].message.content.strip(),
                generated_by="groq",
            )
        except Exception:
            pass

    pct_pos = round(sentiment.positive / sentiment.total * 100) if sentiment.total else 0
    top_issue_label = top_issues[0].label if top_issues else "unknown"
    top_strength_label = top_strengths[0].label if top_strengths else "unknown"
    insight = (
        f"{sentiment.total} reviews analyzed: {pct_pos}% positive sentiment. "
        f"Main issue: '{top_issue_label}' ({top_issues[0].mentions if top_issues else 0} mentions). "
        f"Top strength: '{top_strength_label}' ({top_strengths[0].mentions if top_strengths else 0} mentions)."
    )
    return InsightResponse(insight=insight, generated_by="rule-based")
