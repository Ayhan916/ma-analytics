from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import enum


class TicketStatus(str, enum.Enum):
    backlog = "Backlog"
    todo = "Todo"
    in_progress = "In Progress"
    done = "Done"


class TicketPriority(str, enum.Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_user_created", "user_id", "created_at"),
        Index("ix_tickets_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority), default=TicketPriority.medium)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.backlog)
    customer_name: Mapped[str] = mapped_column(String, nullable=True)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    subtasks: Mapped[list] = mapped_column(JSON, default=list)
    comments: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="tickets")
