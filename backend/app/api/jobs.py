from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.pipeline_job import PipelineJob
from app.models.datasource import DataSource
from app.models.user import User

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    id: str
    datasource_id: str
    status: str
    progress: Optional[str]
    review_count: int
    error: Optional[str]


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PipelineJob)
        .join(DataSource, PipelineJob.datasource_id == DataSource.id)
        .where(PipelineJob.id == job_id, DataSource.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        id=job.id,
        datasource_id=job.datasource_id,
        status=job.status.value,
        progress=job.progress,
        review_count=job.review_count or 0,
        error=job.error,
    )
