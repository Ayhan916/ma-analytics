from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Enum, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import enum


class DataSourceType(str, enum.Enum):
    google_play = "google_play"
    csv = "csv"


class DataSource(Base):
    __tablename__ = "datasources"
    __table_args__ = (
        Index("ix_datasources_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    app_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[DataSourceType] = mapped_column(Enum(DataSourceType), nullable=False)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    industry: Mapped[str] = mapped_column(String, nullable=False, default='automotive')

    # Scraping parameters — persisted so retry uses the same settings
    scrape_lang: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scrape_country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scrape_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="datasources")
    reviews: Mapped[list["Review"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")
    clusters: Mapped[list["Cluster"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")
    jobs: Mapped[list["PipelineJob"]] = relationship(back_populates="datasource", cascade="all, delete-orphan")
