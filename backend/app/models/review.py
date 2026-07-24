from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Float, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(384)
except ImportError:
    from sqlalchemy import ARRAY, Float as _Float
    _VECTOR_TYPE = None


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_datasource_external", "datasource_id", "external_id"),
        Index("ix_reviews_datasource_id", "datasource_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id"), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 'provided' | 'inferred' | 'unknown'
    review_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)     # 'substantive' | 'rating_only'
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Persisted embedding for RAG retrieval (pgvector vector(384))
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(384) if _VECTOR_TYPE is not None else Text,
        nullable=True,
    )

    # Full-text search index — populated by DB trigger on insert/update
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    datasource: Mapped["DataSource"] = relationship(back_populates="reviews")
    cluster_memberships: Mapped[list["ClusterReview"]] = relationship(back_populates="review", cascade="all, delete-orphan")
