from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.cluster import Cluster, ClusterType
from app.models.review import Review
from app.models.datasource import DataSource
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ClusterOut(BaseModel):
    id: str
    label: str
    mentions: int
    summary: Optional[str]
    examples: list


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


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ds_result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == current_user.id)
    )
    ds = ds_result.scalar_one_or_none()
    if not ds:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="DataSource not found")

    reviews_result = await db.execute(
        select(Review).where(Review.datasource_id == datasource_id)
    )
    reviews = reviews_result.scalars().all()

    pos = sum(1 for r in reviews if r.sentiment == "positive")
    neg = sum(1 for r in reviews if r.sentiment == "negative")
    neu = sum(1 for r in reviews if r.sentiment == "neutral")
    scores = [r.score for r in reviews if r.score is not None]
    avg_rating = round(sum(scores) / len(scores), 2) if scores else None

    clusters_result = await db.execute(
        select(Cluster).where(Cluster.datasource_id == datasource_id).order_by(Cluster.mentions.desc())
    )
    clusters = clusters_result.scalars().all()
    issues = [c for c in clusters if c.type == ClusterType.issue][:5]
    strengths = [c for c in clusters if c.type == ClusterType.strength][:5]

    def to_out(c: Cluster) -> ClusterOut:
        return ClusterOut(id=c.id, label=c.label, mentions=c.mentions, summary=c.summary, examples=c.examples or [])

    return DashboardSummary(
        datasource_id=ds.id,
        datasource_name=ds.name,
        review_count=len(reviews),
        avg_rating=avg_rating,
        sentiment=SentimentBreakdown(positive=pos, negative=neg, neutral=neu, total=len(reviews)),
        top_issues=[to_out(c) for c in issues],
        top_strengths=[to_out(c) for c in strengths],
    )


@router.get("/issues", response_model=list[ClusterOut])
async def get_issues(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Cluster)
        .join(DataSource, Cluster.datasource_id == DataSource.id)
        .where(Cluster.datasource_id == datasource_id, Cluster.type == ClusterType.issue, DataSource.user_id == current_user.id)
        .order_by(Cluster.mentions.desc())
    )
    return [ClusterOut(id=c.id, label=c.label, mentions=c.mentions, summary=c.summary, examples=c.examples or []) for c in result.scalars().all()]


@router.get("/strengths", response_model=list[ClusterOut])
async def get_strengths(
    datasource_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Cluster)
        .join(DataSource, Cluster.datasource_id == DataSource.id)
        .where(Cluster.datasource_id == datasource_id, Cluster.type == ClusterType.strength, DataSource.user_id == current_user.id)
        .order_by(Cluster.mentions.desc())
    )
    return [ClusterOut(id=c.id, label=c.label, mentions=c.mentions, summary=c.summary, examples=c.examples or []) for c in result.scalars().all()]


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

    reviews_result = await db.execute(
        select(Review).where(Review.datasource_id == datasource_id)
    )
    reviews = reviews_result.scalars().all()
    pos = sum(1 for r in reviews if r.sentiment == "positive")
    neg = sum(1 for r in reviews if r.sentiment == "negative")

    clusters_result = await db.execute(
        select(Cluster)
        .join(DataSource, Cluster.datasource_id == DataSource.id)
        .where(Cluster.datasource_id == datasource_id, DataSource.user_id == current_user.id)
        .order_by(Cluster.mentions.desc())
    )
    clusters = clusters_result.scalars().all()
    top_issues = [c for c in clusters if c.type == ClusterType.issue][:3]
    top_strengths = [c for c in clusters if c.type == ClusterType.strength][:3]

    if settings.GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            issues_text = ", ".join(c.label for c in top_issues) or "none found"
            strengths_text = ", ".join(c.label for c in top_strengths) or "none found"
            prompt = (
                f"Based on {len(reviews)} app reviews ({pos} positive, {neg} negative):\n"
                f"Top Issues: {issues_text}\n"
                f"Top Strengths: {strengths_text}\n\n"
                f"Write a concise 3-sentence executive summary with the most important finding and one actionable recommendation."
            )
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            return InsightResponse(insight=response.choices[0].message.content.strip(), generated_by="groq")
        except Exception:
            pass

    pct_pos = round(pos / len(reviews) * 100) if reviews else 0
    top_issue = top_issues[0].label if top_issues else "unknown"
    top_strength = top_strengths[0].label if top_strengths else "unknown"
    insight = (
        f"{len(reviews)} reviews analyzed: {pct_pos}% positive sentiment. "
        f"Main issue: '{top_issue}' ({top_issues[0].mentions if top_issues else 0} mentions). "
        f"Top strength: '{top_strength}' ({top_strengths[0].mentions if top_strengths else 0} mentions)."
    )
    return InsightResponse(insight=insight, generated_by="rule-based")
