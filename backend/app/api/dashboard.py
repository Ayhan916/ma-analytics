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
