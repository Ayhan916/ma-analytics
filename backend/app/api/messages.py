from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.message import Message
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.models.user import User
from app.core.config import settings

router = APIRouter(prefix="/messages", tags=["messages"])


class MessageOut(BaseModel):
    id: str
    name: Optional[str]
    email: Optional[str]
    text: str
    sentiment: Optional[str]
    created_at: str


class CreateMessageRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    text: str


class ReplyResponse(BaseModel):
    reply: str
    generated_by: str


class GeneratedTicket(BaseModel):
    title: str
    description: str
    priority: str


class GenerateTicketsResponse(BaseModel):
    tickets: list[GeneratedTicket]
    created: int


def _to_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        name=m.name,
        email=m.email,
        text=m.text,
        sentiment=m.sentiment,
        created_at=m.created_at.isoformat(),
    )


def _detect_sentiment(text: str) -> str:
    try:
        from app.pipeline.ml import clean_text, predict_sentiments
        cleaned = clean_text(text)
        return predict_sentiments([cleaned])[0]
    except Exception:
        return "neutral"


@router.get("", response_model=list[MessageOut])
async def list_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message).where(Message.user_id == current_user.id).order_by(desc(Message.created_at))
    )
    return [_to_out(m) for m in result.scalars().all()]


@router.post("", response_model=MessageOut, status_code=201)
async def create_message(
    body: CreateMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sentiment = _detect_sentiment(body.text)
    msg = Message(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=body.name,
        email=body.email,
        text=body.text,
        sentiment=sentiment,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return _to_out(msg)


@router.post("/{message_id}/generate-reply", response_model=ReplyResponse)
async def generate_reply(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.user_id == current_user.id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if settings.GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            prompt = (
                f"You are a professional customer support agent. Write a helpful, empathetic reply "
                f"to the following customer message. Be concise (3-4 sentences).\n\n"
                f"Customer: {msg.name or 'Customer'}\n"
                f"Message: {msg.text}\n\nReply:"
            )
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
            )
            return ReplyResponse(reply=response.choices[0].message.content.strip(), generated_by="groq")
        except Exception:
            pass

    sentiment_map = {
        "negative": "I'm sorry to hear about your experience. We take this seriously and will look into it right away. Please expect an update within 24 hours.",
        "positive": "Thank you so much for your kind words! We're thrilled to hear you're enjoying the app. Your feedback means a lot to our team.",
        "neutral": "Thank you for reaching out! We appreciate your feedback and will make sure it reaches the right team.",
    }
    reply = sentiment_map.get(msg.sentiment or "neutral", sentiment_map["neutral"])
    return ReplyResponse(reply=reply, generated_by="rule-based")


@router.post("/{message_id}/generate-tickets", response_model=GenerateTicketsResponse)
async def generate_tickets(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.user_id == current_user.id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    generated = []

    if settings.GROQ_API_KEY:
        try:
            from groq import Groq
            import json
            client = Groq(api_key=settings.GROQ_API_KEY)
            prompt = (
                f"Extract actionable tasks from this customer message and return JSON only.\n"
                f"Message: {msg.text}\n\n"
                f'Return: [{{"title": "...", "description": "...", "priority": "High|Medium|Low"}}]\n'
                f"Return 1-3 tickets maximum. JSON only, no explanation."
            )
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            raw = response.choices[0].message.content.strip()
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                generated = json.loads(raw[start:end])
        except Exception:
            pass

    if not generated:
        priority = "High" if msg.sentiment == "negative" else "Medium"
        generated = [{"title": f"Follow-up: {msg.text[:60]}...", "description": msg.text, "priority": priority}]

    created_tickets = []
    for item in generated[:3]:
        try:
            priority_val = TicketPriority(item.get("priority", "Medium"))
        except ValueError:
            priority_val = TicketPriority.medium
        ticket = Ticket(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            title=item.get("title", "Customer feedback")[:200],
            description=item.get("description", msg.text),
            priority=priority_val,
            status=TicketStatus.backlog,
            customer_name=msg.name,
        )
        db.add(ticket)
        created_tickets.append(ticket)

    await db.commit()

    return GenerateTicketsResponse(
        tickets=[GeneratedTicket(title=t.title, description=t.description or "", priority=t.priority.value) for t in created_tickets],
        created=len(created_tickets),
    )
