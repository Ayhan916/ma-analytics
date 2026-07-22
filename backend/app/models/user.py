from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    datasources: Mapped[list["DataSource"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="user", cascade="all, delete-orphan")
