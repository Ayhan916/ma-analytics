"""Lokale Märkte — Google Maps business search and review analysis."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.datasource import DataSource, DataSourceType
from app.models.pipeline_job import PipelineJob, JobStatus
from app.pipeline.celery_app import celery_app
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


# ── Schemas ──────────────────────────────────────────────────────────────────

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories():
    return {"categories": CATEGORIES, "radius_options": RADIUS_OPTIONS}


@router.post("/search", response_model=List[BusinessItem])
async def search_businesses_endpoint(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search Google Maps for businesses near a postal code. Runs Playwright in a thread."""
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
            name=r.name,
            maps_url=r.maps_url,
            place_id=r.place_id,
            address=r.address,
            rating=r.rating,
            review_count=r.review_count,
            category=r.category,
        )
        for r in results
    ]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_businesses(
    body: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a DataSource + PipelineJob for each selected business."""
    if not body.businesses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No businesses provided.")

    datasource_ids: List[str] = []
    job_ids: List[str] = []

    for biz in body.businesses:
        ds_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        ds = DataSource(
            id=ds_id,
            user_id=current_user.id,
            name=biz.name,
            app_id=biz.maps_url,
            type=DataSourceType.google_maps,
            industry="local",
            scrape_lang=None,
            scrape_country=None,
            scrape_count=body.max_reviews_per_business,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ds)

        job = PipelineJob(
            id=job_id,
            datasource_id=ds_id,
            status=JobStatus.pending,
            progress="queued",
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)

        datasource_ids.append(ds_id)
        job_ids.append(job_id)

    await db.commit()

    # Dispatch Celery tasks after commit
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
    """Return all google_maps datasources for the current user."""
    result = await db.execute(
        select(DataSource)
        .where(
            DataSource.user_id == current_user.id,
            DataSource.type == DataSourceType.google_maps,
        )
        .order_by(DataSource.created_at.desc())
    )
    rows = result.scalars().all()

    return [
        LocalDatasourceItem(
            id=ds.id,
            name=ds.name,
            address="",
            maps_url=ds.app_id or "",
            created_at=ds.created_at.isoformat(),
            last_synced=ds.last_synced.isoformat() if ds.last_synced else None,
        )
        for ds in rows
    ]
