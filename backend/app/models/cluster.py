from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import enum


class ClusterType(str, enum.Enum):
    issue = "issue"
    strength = "strength"


class Cluster(Base):
    __tablename__ = "clusters"
    __table_args__ = (
        Index("ix_clusters_datasource_id", "datasource_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    datasource_id: Mapped[str] = mapped_column(String, ForeignKey("datasources.id"), nullable=False)
    type: Mapped[ClusterType] = mapped_column(Enum(ClusterType), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    solution: Mapped[str] = mapped_column(Text, nullable=True)
    mentions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    datasource: Mapped["DataSource"] = relationship(back_populates="clusters")
    review_memberships: Mapped[list["ClusterReview"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")


class ClusterReview(Base):
    """Junction table linking clusters to the reviews they contain."""
    __tablename__ = "cluster_reviews"
    __table_args__ = (
        Index("ix_cluster_reviews_cluster_id", "cluster_id"),
        Index("ix_cluster_reviews_review_id", "review_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cluster_id: Mapped[str] = mapped_column(String, ForeignKey("clusters.id"), nullable=False)
    review_id: Mapped[str] = mapped_column(String, ForeignKey("reviews.id"), nullable=False)
    is_example: Mapped[bool] = mapped_column(default=False)

    cluster: Mapped["Cluster"] = relationship(back_populates="review_memberships")
    review: Mapped["Review"] = relationship(back_populates="cluster_memberships")
