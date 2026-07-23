from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import enum


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        Index("ix_pipeline_jobs_datasource_created", "datasource_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.pending)
    progress: Mapped[str] = mapped_column(String, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    datasource: Mapped["DataSource"] = relationship(back_populates="jobs")
