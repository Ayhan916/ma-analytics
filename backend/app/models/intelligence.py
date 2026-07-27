from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Float, Boolean, Text, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class ReviewAspect(Base):
    """One aspect extracted by pyABSA from a review — the atomic unit of ABSA analysis."""
    __tablename__ = "review_aspects"
    __table_args__ = (
        Index("ix_review_aspects_review_id", "review_id"),
        Index("ix_review_aspects_datasource_id", "datasource_id"),
        Index("ix_review_aspects_feature", "feature"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id: Mapped[str] = mapped_column(String, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False)
    aspect_term: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    span_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    absa_source: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    signals: Mapped[list["ReviewSignal"]] = relationship(back_populates="aspect", cascade="all, delete-orphan", foreign_keys="ReviewSignal.aspect_id")


class ReviewSentence(Base):
    """One sentence extracted from a review — the atomic unit of analysis."""
    __tablename__ = "review_sentences"
    __table_args__ = (
        Index("ix_review_sentences_review_id", "review_id"),
        Index("ix_review_sentences_datasource_id", "datasource_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id: Mapped[str] = mapped_column(String, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    signals: Mapped[list["ReviewSignal"]] = relationship(back_populates="sentence", cascade="all, delete-orphan", foreign_keys="ReviewSignal.sentence_id")


class ReviewSignal(Base):
    """Structured signal extracted by LLM from a single sentence."""
    __tablename__ = "review_signals"
    __table_args__ = (
        Index("ix_review_signals_datasource_id", "datasource_id"),
        Index("ix_review_signals_feature", "feature"),
        Index("ix_review_signals_sentence_id", "sentence_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sentence_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("review_sentences.id", ondelete="SET NULL"), nullable=True)
    aspect_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("review_aspects.id", ondelete="SET NULL"), nullable=True)
    review_id: Mapped[str] = mapped_column(String, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    version_hint: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sentence: Mapped[Optional["ReviewSentence"]] = relationship(back_populates="signals", foreign_keys=[sentence_id])
    aspect: Mapped[Optional["ReviewAspect"]] = relationship(back_populates="signals", foreign_keys=[aspect_id])


class FeatureNarrative(Base):
    """LLM-generated summary for one feature, cached after synthesis."""
    __tablename__ = "feature_narratives"
    __table_args__ = (
        Index("ix_feature_narratives_datasource_feature", "datasource_id", "feature", unique=True),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    feature_request_narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_severity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    signal_counts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
