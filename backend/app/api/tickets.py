from __future__ import annotations
import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    priority: str
    status: str
    customer_name: Optional[str]
    labels: list
    subtasks: list
    comments: list
    created_at: str
    updated_at: str


class CreateTicketRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "Medium"
    status: str = "Backlog"
    customer_name: Optional[str] = None
    labels: list = []
    subtasks: list = []


class UpdateTicketRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    customer_name: Optional[str] = None
    labels: Optional[list] = None
    subtasks: Optional[list] = None
    comments: Optional[list] = None


def _to_out(t: Ticket) -> TicketOut:
    return TicketOut(
        id=t.id,
        title=t.title,
        description=t.description,
        priority=t.priority.value,
        status=t.status.value,
        customer_name=t.customer_name,
        labels=t.labels or [],
        subtasks=t.subtasks or [],
        comments=t.comments or [],
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


@router.get("", response_model=list[TicketOut])
async def list_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Ticket).where(Ticket.user_id == current_user.id).order_by(desc(Ticket.created_at))
    if status:
        q = q.where(Ticket.status == status)
    if priority:
        q = q.where(Ticket.priority == priority)
    result = await db.execute(q)
    return [_to_out(t) for t in result.scalars().all()]


@router.post("", response_model=TicketOut, status_code=201)
async def create_ticket(
    body: CreateTicketRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = Ticket(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=body.title,
        description=body.description,
        priority=TicketPriority(body.priority),
        status=TicketStatus(body.status),
        customer_name=body.customer_name,
        labels=body.labels,
        subtasks=body.subtasks,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return _to_out(ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: str,
    body: UpdateTicketRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.user_id == current_user.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if body.title is not None:
        ticket.title = body.title
    if body.description is not None:
        ticket.description = body.description
    if body.priority is not None:
        ticket.priority = TicketPriority(body.priority)
    if body.status is not None:
        ticket.status = TicketStatus(body.status)
    if body.customer_name is not None:
        ticket.customer_name = body.customer_name
    if body.labels is not None:
        ticket.labels = body.labels
    if body.subtasks is not None:
        ticket.subtasks = body.subtasks
    if body.comments is not None:
        ticket.comments = body.comments

    ticket.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ticket)
    return _to_out(ticket)


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.user_id == current_user.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await db.delete(ticket)
    await db.commit()
