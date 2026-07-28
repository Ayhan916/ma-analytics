"""Lokale Märkte — Google Maps business search, dashboard and Best Practice Lab."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, text
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.datasource import DataSource, DataSourceType
from app.models.pipeline_job import PipelineJob, JobStatus
from app.models.review import Review
from app.models.intelligence import ReviewSignal
from app.pipeline.celery_app import celery_app
from app.core.config import settings
import structlog
import asyncio

router = APIRouter(prefix="/local", tags=["local-markets"])
log = structlog.get_logger(__name__)

RADIUS_OPTIONS = [1, 2, 5, 10, 20]

CATEGORIES = [
    "Restaurant", "Supermarkt", "Friseur", "Autowerkstatt",
    "Apotheke", "Café", "Bäckerei", "Arzt", "Zahnarzt",
    "Fitnessstudio", "Hotel", "Bar", "Pizzeria", "Tankstelle",
]


# ── Schemas ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    postal_code: str = Field(..., min_length=2, max_length=100)
    radius_km: int = Field(5, ge=1, le=50)
    category: str
    keyword: str = Field("", max_length=100)
    max_results: int = Field(20, ge=1, le=50)


class BusinessItem(BaseModel):
    name: str
    maps_url: str
    place_id: str
    address: str
    rating: float
    review_count: int
    category: str


class AnalyzeRequest(BaseModel):
    businesses: List[BusinessItem]
    max_reviews_per_business: int = Field(200, ge=10, le=500)


class AnalyzeResponse(BaseModel):
    datasource_ids: List[str]
    job_ids: List[str]


class LocalDatasourceItem(BaseModel):
    id: str
    name: str
    address: str
    maps_url: str
    created_at: str
    last_synced: Optional[str]


class SignalSummary(BaseModel):
    feature: str
    count: int
    signal_type: str
    businesses_count: int


class BusinessDashboardItem(BaseModel):
    id: str
    name: str
    maps_url: str
    review_count: int
    avg_rating: Optional[float]
    sentiment_positive: int
    sentiment_negative: int
    sentiment_neutral: int
    top_signals: List[SignalSummary]
    job_status: Optional[str]


class LocalDashboardResponse(BaseModel):
    total_businesses: int
    total_reviews: int
    businesses: List[BusinessDashboardItem]
    cross_signals: List[SignalSummary]


class BestPracticeRequest(BaseModel):
    datasource_ids: List[str] = Field(..., min_length=1)
    focus: str = Field("", max_length=200)


class BestPracticeResponse(BaseModel):
    report: str
    generated_at: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_local_datasource_ids(db: AsyncSession, user_id: str) -> List[str]:
    result = await db.execute(
        select(DataSource.id).where(
            DataSource.user_id == user_id,
            DataSource.type == DataSourceType.google_maps,
        )
    )
    return [row[0] for row in result.all()]


async def _top_signals_for(db: AsyncSession, datasource_ids: List[str], limit: int = 8) -> List[dict]:
    if not datasource_ids:
        return []
    result = await db.execute(
        select(
            ReviewSignal.feature,
            ReviewSignal.signal_type,
            func.count(ReviewSignal.id).label("cnt"),
            func.count(ReviewSignal.datasource_id.distinct()).label("biz_cnt"),
        )
        .where(ReviewSignal.datasource_id.in_(datasource_ids))
        .group_by(ReviewSignal.feature, ReviewSignal.signal_type)
        .order_by(func.count(ReviewSignal.id).desc())
        .limit(limit)
    )
    return [
        {"feature": r.feature, "count": r.cnt, "signal_type": r.signal_type, "businesses_count": r.biz_cnt}
        for r in result.all()
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories():
    return {"categories": CATEGORIES, "radius_options": RADIUS_OPTIONS}


@router.post("/search", response_model=List[BusinessItem])
async def search_businesses_endpoint(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    from app.pipeline.google_maps_scraper import search_businesses, CATEGORIES as VALID_CATS

    if body.category not in VALID_CATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown category. Valid: {VALID_CATS}",
        )
    try:
        results = await asyncio.to_thread(
            search_businesses,
            body.postal_code,
            body.radius_km,
            body.category,
            body.max_results,
            body.keyword,
        )
    except Exception as exc:
        log.error("maps_search_endpoint_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Maps search failed. Check if Playwright is installed (`playwright install chromium`).",
        )

    return [
        BusinessItem(
            name=r.name, maps_url=r.maps_url, place_id=r.place_id,
            address=r.address, rating=r.rating,
            review_count=r.review_count, category=r.category,
        )
        for r in results
    ]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_businesses(
    body: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.businesses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No businesses provided.")

    datasource_ids: List[str] = []
    job_ids: List[str] = []

    for biz in body.businesses:
        ds_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        ds = DataSource(
            id=ds_id, user_id=current_user.id, name=biz.name,
            app_id=biz.maps_url, type=DataSourceType.google_maps,
            industry="local", scrape_lang=None, scrape_country=None,
            scrape_count=body.max_reviews_per_business,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ds)

        job = PipelineJob(
            id=job_id, datasource_id=ds_id, status=JobStatus.pending,
            progress="queued", created_at=datetime.now(timezone.utc),
        )
        db.add(job)

        datasource_ids.append(ds_id)
        job_ids.append(job_id)

    await db.commit()

    for biz, ds_id, job_id in zip(body.businesses, datasource_ids, job_ids):
        celery_app.send_task(
            "app.pipeline.tasks.scrape_maps_and_run",
            args=[job_id, ds_id, biz.maps_url, body.max_reviews_per_business],
        )
        log.info("maps_job_queued", ds_id=ds_id, job_id=job_id, business=biz.name)

    return AnalyzeResponse(datasource_ids=datasource_ids, job_ids=job_ids)


@router.get("/datasources", response_model=List[LocalDatasourceItem])
async def list_local_datasources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DataSource)
        .where(DataSource.user_id == current_user.id, DataSource.type == DataSourceType.google_maps)
        .order_by(DataSource.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        LocalDatasourceItem(
            id=ds.id, name=ds.name, address="",
            maps_url=ds.app_id or "",
            created_at=ds.created_at.isoformat(),
            last_synced=ds.last_synced.isoformat() if ds.last_synced else None,
        )
        for ds in rows
    ]


@router.get("/dashboard", response_model=LocalDashboardResponse)
async def local_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate overview across all analyzed local businesses."""
    # All google_maps datasources for this user
    ds_result = await db.execute(
        select(DataSource)
        .where(DataSource.user_id == current_user.id, DataSource.type == DataSourceType.google_maps)
        .order_by(DataSource.created_at.desc())
    )
    datasources = ds_result.scalars().all()

    if not datasources:
        return LocalDashboardResponse(
            total_businesses=0, total_reviews=0,
            businesses=[], cross_signals=[],
        )

    ds_ids = [ds.id for ds in datasources]

    # Review stats per datasource (count + avg score + sentiment)
    stats_result = await db.execute(
        select(
            Review.datasource_id,
            func.count(Review.id).label("cnt"),
            func.avg(Review.score).label("avg_score"),
            func.sum(case((Review.sentiment == "positive", 1), else_=0)).label("pos"),
            func.sum(case((Review.sentiment == "negative", 1), else_=0)).label("neg"),
            func.sum(case((Review.sentiment == "neutral",  1), else_=0)).label("neu"),
        )
        .where(Review.datasource_id.in_(ds_ids))
        .group_by(Review.datasource_id)
    )
    stats_by_ds = {row.datasource_id: row for row in stats_result.all()}

    # Latest job status per datasource
    job_result = await db.execute(
        select(PipelineJob.datasource_id, PipelineJob.status)
        .where(PipelineJob.datasource_id.in_(ds_ids))
        .order_by(PipelineJob.created_at.desc())
    )
    job_by_ds: dict[str, str] = {}
    for row in job_result.all():
        if row.datasource_id not in job_by_ds:
            job_by_ds[row.datasource_id] = row.status.value if hasattr(row.status, "value") else str(row.status)

    # Top signals per datasource (top 5 each)
    sig_result = await db.execute(
        select(
            ReviewSignal.datasource_id,
            ReviewSignal.feature,
            ReviewSignal.signal_type,
            func.count(ReviewSignal.id).label("cnt"),
        )
        .where(ReviewSignal.datasource_id.in_(ds_ids))
        .group_by(ReviewSignal.datasource_id, ReviewSignal.feature, ReviewSignal.signal_type)
        .order_by(ReviewSignal.datasource_id, func.count(ReviewSignal.id).desc())
    )
    signals_by_ds: dict[str, list] = {}
    for row in sig_result.all():
        signals_by_ds.setdefault(row.datasource_id, [])
        if len(signals_by_ds[row.datasource_id]) < 5:
            signals_by_ds[row.datasource_id].append(
                SignalSummary(feature=row.feature, count=row.cnt, signal_type=row.signal_type, businesses_count=1)
            )

    # Build per-business items
    businesses_out: List[BusinessDashboardItem] = []
    total_reviews = 0
    for ds in datasources:
        s = stats_by_ds.get(ds.id)
        cnt = s.cnt if s else 0
        total_reviews += cnt
        businesses_out.append(BusinessDashboardItem(
            id=ds.id,
            name=ds.name,
            maps_url=ds.app_id or "",
            review_count=cnt,
            avg_rating=round(float(s.avg_score), 2) if s and s.avg_score else None,
            sentiment_positive=int(s.pos or 0) if s else 0,
            sentiment_negative=int(s.neg or 0) if s else 0,
            sentiment_neutral=int(s.neu or 0) if s else 0,
            top_signals=signals_by_ds.get(ds.id, []),
            job_status=job_by_ds.get(ds.id),
        ))

    # Cross-business signals (signals that appear in multiple businesses)
    cross = await _top_signals_for(db, ds_ids, limit=15)
    cross_signals = [
        SignalSummary(
            feature=c["feature"], count=c["count"],
            signal_type=c["signal_type"], businesses_count=c["businesses_count"],
        )
        for c in cross
    ]

    return LocalDashboardResponse(
        total_businesses=len(datasources),
        total_reviews=total_reviews,
        businesses=businesses_out,
        cross_signals=cross_signals,
    )


@router.post("/best-practice/generate", response_model=BestPracticeResponse)
async def generate_best_practice(
    body: BestPracticeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Use Claude to generate a best practice report from selected businesses."""
    # Verify ownership
    ds_result = await db.execute(
        select(DataSource)
        .where(
            DataSource.id.in_(body.datasource_ids),
            DataSource.user_id == current_user.id,
            DataSource.type == DataSourceType.google_maps,
        )
    )
    datasources = ds_result.scalars().all()
    if not datasources:
        raise HTTPException(status_code=404, detail="No local datasources found.")

    ds_ids = [ds.id for ds in datasources]
    ds_by_id = {ds.id: ds for ds in datasources}

    # Stats per business
    stats_result = await db.execute(
        select(
            Review.datasource_id,
            func.count(Review.id).label("cnt"),
            func.avg(Review.score).label("avg_score"),
        )
        .where(Review.datasource_id.in_(ds_ids))
        .group_by(Review.datasource_id)
    )
    stats = {row.datasource_id: row for row in stats_result.all()}

    # Top signals per business
    sig_result = await db.execute(
        select(
            ReviewSignal.datasource_id,
            ReviewSignal.feature,
            ReviewSignal.signal_type,
            func.count(ReviewSignal.id).label("cnt"),
        )
        .where(ReviewSignal.datasource_id.in_(ds_ids))
        .group_by(ReviewSignal.datasource_id, ReviewSignal.feature, ReviewSignal.signal_type)
        .order_by(ReviewSignal.datasource_id, func.count(ReviewSignal.id).desc())
    )
    sigs_by_ds: dict[str, list] = {}
    for row in sig_result.all():
        sigs_by_ds.setdefault(row.datasource_id, [])
        if len(sigs_by_ds[row.datasource_id]) < 8:
            sigs_by_ds[row.datasource_id].append(
                f"{row.feature} ({row.signal_type}, {row.cnt}x)"
            )

    # Sample reviews per business (3 positive + 3 negative)
    reviews_by_ds: dict[str, list] = {}
    for ds_id in ds_ids:
        pos_result = await db.execute(
            select(Review.content)
            .where(Review.datasource_id == ds_id, Review.sentiment == "positive")
            .order_by(func.random())
            .limit(3)
        )
        neg_result = await db.execute(
            select(Review.content)
            .where(Review.datasource_id == ds_id, Review.sentiment == "negative")
            .order_by(func.random())
            .limit(3)
        )
        reviews_by_ds[ds_id] = (
            [f"(+) {r[0][:200]}" for r in pos_result.all()] +
            [f"(-) {r[0][:200]}" for r in neg_result.all()]
        )

    # Build context for Claude
    business_blocks = []
    for ds in sorted(datasources, key=lambda d: float(stats[d.id].avg_score or 0) if d.id in stats else 0, reverse=True):
        s = stats.get(ds.id)
        avg = round(float(s.avg_score), 1) if s and s.avg_score else "?"
        cnt = s.cnt if s else 0
        signals_str = ", ".join(sigs_by_ds.get(ds.id, [])[:6]) or "keine Signale"
        reviews_str = "\n  ".join(reviews_by_ds.get(ds.id, [])[:4]) or "keine Reviews"
        business_blocks.append(
            f"### {ds.name} — ⭐ {avg} ({cnt} Reviews)\n"
            f"Top Signale: {signals_str}\n"
            f"Beispiel-Reviews:\n  {reviews_str}"
        )

    focus_line = f"\nFokus-Thema: **{body.focus}**\n" if body.focus else ""
    prompt = f"""Du analysierst Google Maps Reviews von lokalen Betrieben in Deutschland.
{focus_line}
Hier sind die Betriebe mit ihren Daten (sortiert nach Bewertung, beste zuerst):

{"".join(chr(10) + b + chr(10) for b in business_blocks)}

Erstelle eine strukturierte Best Practice Analyse auf Deutsch mit folgenden Abschnitten:

## Was machen die TOP-Betriebe (4★+) besser?
Konkrete Muster aus den Daten — was loben Kunden bei gut bewerteten Betrieben?

## Häufige Schwächen bei schlechter bewerteten Betrieben
Was sind die wiederkehrenden Kritikpunkte? Welche Signale dominieren?

## 5 konkrete Handlungsempfehlungen
Nummerierte Liste. Praxisnah, direkt umsetzbar.

## Signal-Vergleich
Kurze Tabelle: welche Signale bei guten vs. schlechten Betrieben dominieren.

Schreib klar, präzise und datenbasiert. Vermeide allgemeine Floskeln."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        report = response.content[0].text
    except Exception as exc:
        log.error("best_practice_claude_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")

    return BestPracticeResponse(
        report=report,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
