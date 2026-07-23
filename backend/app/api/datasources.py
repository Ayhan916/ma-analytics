from __future__ import annotations
import uuid
import io
import csv
import structlog
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.datasource import DataSource, DataSourceType
from app.models.pipeline_job import PipelineJob, JobStatus
from app.models.review import Review
from app.models.user import User

router = APIRouter(prefix="/datasources", tags=["datasources"])
log = structlog.get_logger(__name__)


class CreateGPlayRequest(BaseModel):
    name: str
    app_id: str
    count: int = 500
    lang: str = "de"
    country: str = "de"

    @field_validator("count")
    @classmethod
    def cap_count(cls, v: int) -> int:
        return min(v, settings.SCRAPE_MAX_REVIEWS)

    @field_validator("app_id")
    @classmethod
    def validate_app_id(cls, v: str) -> str:
        v = v.strip()
        if not v or " " in v:
            raise ValueError("app_id must be a valid Google Play package name (e.g. com.spotify.music)")
        return v


class DataSourceResponse(BaseModel):
    id: str
    name: str
    type: str
    app_id: Optional[str]
    job_id: Optional[str]
    job_status: Optional[str]
    job_error: Optional[str]
    review_count: int
    last_synced: Optional[str]
    scrape_lang: Optional[str]
    scrape_country: Optional[str]
    scrape_count: Optional[int]


async def _check_scrape_rate_limit(db: AsyncSession, user_id: str) -> None:
    """Enforce SCRAPE_MAX_PER_HOUR jobs per user per rolling hour."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT COUNT(*)
            FROM pipeline_jobs pj
            JOIN datasources ds ON pj.datasource_id = ds.id
            WHERE ds.user_id = :user_id
              AND pj.created_at >= NOW() - INTERVAL '1 hour'
        """),
        {"user_id": user_id},
    )
    count = result.scalar() or 0
    if count >= settings.SCRAPE_MAX_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: max {settings.SCRAPE_MAX_PER_HOUR} scraping jobs per hour. Try again later.",
        )


@router.post("/google-play", response_model=DataSourceResponse, status_code=201)
async def create_google_play_source(
    body: CreateGPlayRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _check_scrape_rate_limit(db, current_user.id)

    ds = DataSource(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=body.name,
        app_id=body.app_id,
        type=DataSourceType.google_play,
        scrape_lang=body.lang,
        scrape_country=body.country,
        scrape_count=body.count,
    )
    db.add(ds)

    job = PipelineJob(
        id=str(uuid.uuid4()),
        datasource_id=ds.id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(job)
    await db.commit()

    log.info("scrape_job_queued", app_id=body.app_id, count=body.count, lang=body.lang)

    from app.pipeline.tasks import scrape_and_run
    scrape_and_run.delay(job.id, ds.id, body.app_id, body.count, body.lang, body.country)

    return DataSourceResponse(
        id=ds.id, name=ds.name, type=ds.type.value, app_id=ds.app_id,
        job_id=job.id, job_status=job.status.value, job_error=None,
        review_count=0, last_synced=None,
        scrape_lang=ds.scrape_lang, scrape_country=ds.scrape_country, scrape_count=ds.scrape_count,
    )


@router.post("/upload-csv", response_model=DataSourceResponse, status_code=201)
async def upload_csv(
    name: str = Form(...),
    text_col: str = Form("content"),
    score_col: str = Form("score"),
    date_col: str = Form("at"),
    version_col: str = Form("reviewCreatedVersion"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {exc}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no data rows.")

    ds = DataSource(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=name,
        type=DataSourceType.csv,
    )
    db.add(ds)

    job = PipelineJob(
        id=str(uuid.uuid4()),
        datasource_id=ds.id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(job)

    count = 0
    for row in rows:
        text = row.get(text_col, "").strip()
        if not text:
            continue
        try:
            score = float(row.get(score_col) or 0) or None
        except (ValueError, TypeError):
            score = None
        review = Review(
            id=str(uuid.uuid4()),
            datasource_id=ds.id,
            content=text,
            score=score,
            version=row.get(version_col),
        )
        db.add(review)
        count += 1

    if count == 0:
        raise HTTPException(status_code=400, detail=f"No valid reviews found in column '{text_col}'.")

    await db.commit()

    from app.pipeline.tasks import run_pipeline
    run_pipeline.delay(job.id, ds.id)

    return DataSourceResponse(
        id=ds.id, name=ds.name, type=ds.type.value, app_id=None,
        job_id=job.id, job_status=job.status.value, job_error=None,
        review_count=count, last_synced=None,
        scrape_lang=None, scrape_country=None, scrape_count=None,
    )


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DataSource)
        .where(DataSource.user_id == current_user.id)
        .order_by(desc(DataSource.created_at))
    )
    datasources = result.scalars().all()

    out = []
    for ds in datasources:
        job_result = await db.execute(
            select(PipelineJob)
            .where(PipelineJob.datasource_id == ds.id)
            .order_by(desc(PipelineJob.created_at))
            .limit(1)
        )
        job = job_result.scalar_one_or_none()

        count_result = await db.execute(
            select(func.count()).select_from(Review).where(Review.datasource_id == ds.id)
        )
        review_count = count_result.scalar() or 0

        out.append(DataSourceResponse(
            id=ds.id, name=ds.name, type=ds.type.value, app_id=ds.app_id,
            job_id=job.id if job else None,
            job_status=job.status.value if job else None,
            job_error=job.error if job else None,
            review_count=review_count,
            last_synced=ds.last_synced.isoformat() if ds.last_synced else None,
            scrape_lang=ds.scrape_lang, scrape_country=ds.scrape_country, scrape_count=ds.scrape_count,
        ))

    return out


@router.delete("/{datasource_id}", status_code=204)
async def delete_datasource(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    # Warn if a job is currently running (worker will fail gracefully on FK violation)
    job_result = await db.execute(
        select(PipelineJob)
        .where(PipelineJob.datasource_id == datasource_id, PipelineJob.status.in_([JobStatus.pending, JobStatus.running]))
        .limit(1)
    )
    if job_result.scalar_one_or_none():
        log.warning("delete_while_job_running", datasource_id=datasource_id)

    await db.delete(ds)
    await db.commit()


@router.post("/{datasource_id}/retry", response_model=DataSourceResponse)
async def retry_pipeline(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    job_result = await db.execute(
        select(PipelineJob)
        .where(PipelineJob.datasource_id == ds.id)
        .order_by(desc(PipelineJob.created_at))
        .limit(1)
    )
    latest_job = job_result.scalar_one_or_none()
    if latest_job and latest_job.status in (JobStatus.pending, JobStatus.running):
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    count_result = await db.execute(
        select(func.count()).select_from(Review).where(Review.datasource_id == ds.id)
    )
    review_count = count_result.scalar() or 0

    if review_count == 0 and not ds.app_id:
        raise HTTPException(status_code=400, detail="Cannot retry CSV source without existing reviews")

    await _check_scrape_rate_limit(db, current_user.id)

    new_job = PipelineJob(
        id=str(uuid.uuid4()),
        datasource_id=ds.id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(new_job)
    await db.commit()

    if review_count > 0:
        from app.pipeline.tasks import run_pipeline
        run_pipeline.delay(new_job.id, ds.id)
    else:
        # Use stored scraping parameters
        lang = ds.scrape_lang or "de"
        country = ds.scrape_country or "de"
        count = ds.scrape_count or 500
        from app.pipeline.tasks import scrape_and_run
        scrape_and_run.delay(new_job.id, ds.id, ds.app_id, count, lang, country)
        log.info("retry_scrape", app_id=ds.app_id, lang=lang, country=country, count=count)

    return DataSourceResponse(
        id=ds.id, name=ds.name, type=ds.type.value, app_id=ds.app_id,
        job_id=new_job.id, job_status=new_job.status.value, job_error=None,
        review_count=review_count,
        last_synced=ds.last_synced.isoformat() if ds.last_synced else None,
        scrape_lang=ds.scrape_lang, scrape_country=ds.scrape_country, scrape_count=ds.scrape_count,
    )
