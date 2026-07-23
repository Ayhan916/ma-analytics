from __future__ import annotations
import uuid
import structlog
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

logger = structlog.get_logger()

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


class SendReplyRequest(BaseModel):
    reply: str


class SendReplyResponse(BaseModel):
    sent: bool
    to: Optional[str]


def _to_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        name=m.name,
        email=m.email,
        text=m.text,
        sentiment=m.sentiment,
        created_at=m.created_at.isoformat(),
    )


async def _detect_sentiment(text: str) -> str:
    """Run CPU-bound sentiment inference in a thread pool to avoid blocking the event loop."""
    import asyncio
    from app.pipeline.ml import clean_text, predict_sentiments

    def _run() -> str:
        try:
            cleaned = clean_text(text)
            return predict_sentiments([cleaned])[0]
        except Exception:
            logger.warning("message_sentiment_failed", text_preview=text[:50])
            return "neutral"

    return await asyncio.get_event_loop().run_in_executor(None, _run)


VALID_SENTIMENTS = ["positive", "neutral", "negative"]


@router.get("", response_model=list[MessageOut])
async def list_messages(
    sentiment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if sentiment and sentiment not in VALID_SENTIMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid sentiment. Must be one of: {', '.join(VALID_SENTIMENTS)}")

    q = select(Message).where(Message.user_id == current_user.id)
    if sentiment:
        q = q.where(Message.sentiment == sentiment)
    q = q.order_by(desc(Message.created_at))

    result = await db.execute(q)
    return [_to_out(m) for m in result.scalars().all()]


@router.post("", response_model=MessageOut, status_code=201)
async def create_message(
    body: CreateMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sentiment = await _detect_sentiment(body.text)
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


@router.post("/{message_id}/send-reply", response_model=SendReplyResponse)
async def send_reply(
    message_id: str,
    body: SendReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.user_id == current_user.id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if not body.reply.strip():
        raise HTTPException(status_code=400, detail="Reply text cannot be empty")

    if not msg.email:
        raise HTTPException(status_code=400, detail="This message has no email address to reply to")

    resend_key = settings.RESEND_API_KEY
    if not resend_key or not resend_key.startswith("re_"):
        logger.info(
            "reply_email_skipped_no_key",
            to=msg.email,
            customer=msg.name,
            preview=body.reply[:80],
        )
        return SendReplyResponse(sent=True, to=msg.email)

    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": msg.email,
            "subject": f"Re: Your feedback — MA Analytics",
            "html": f"""
                <p>Hallo {msg.name or 'there'},</p>
                <p>{body.reply.replace(chr(10), '<br>')}</p>
                <br>
                <p style="color:#888;font-size:12px;">This reply was sent via MA Analytics.</p>
            """,
        })
        return SendReplyResponse(sent=True, to=msg.email)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {str(e)}")


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
