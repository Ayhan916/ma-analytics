from __future__ import annotations
import structlog
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.review import Review
from app.models.datasource import DataSource
from app.models.user import User
from app.core.config import settings

router = APIRouter(prefix="/search", tags=["search"])
log = structlog.get_logger(__name__)


class SearchResult(BaseModel):
    review_id: str
    content: str
    score: Optional[float]
    sentiment: Optional[str]
    language: Optional[str]
    reviewed_at: Optional[str]
    similarity: float


class SearchResponse(BaseModel):
    query: str
    datasource_id: str
    results: list[SearchResult]
    total: int


class AskRequest(BaseModel):
    query: str
    datasource_id: str
    limit: int = 10
    sentiment_filter: Optional[str] = None


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult]
    generated_by: str


def _embed_query(query: str) -> list[float]:
    """Encode user query using the same model as review embeddings."""
    from app.pipeline.ml import get_embedding_model
    model = get_embedding_model()
    return model.encode([query], normalize_embeddings=True)[0].tolist()


@router.get("", response_model=SearchResponse)
async def semantic_search(
    datasource_id: str = Query(...),
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, le=50),
    sentiment: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic search over reviews using pgvector cosine similarity.
    Optionally filter by sentiment (positive/neutral/negative).
    """
    # Verify datasource belongs to user
    ds_result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == current_user.id)
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="DataSource not found")

    # Check that embeddings exist
    count_result = await db.execute(
        select(func.count()).select_from(Review).where(
            Review.datasource_id == datasource_id,
            Review.embedding.isnot(None),
        )
    )
    if (count_result.scalar() or 0) == 0:
        raise HTTPException(
            status_code=422,
            detail="No embeddings found for this datasource. Run the ML pipeline first.",
        )

    try:
        query_embedding = _embed_query(q)
    except Exception:
        log.exception("query_embedding_failed", query=q)
        raise HTTPException(status_code=500, detail="Failed to encode query.")

    # Build sentiment filter clause
    sentiment_clause = ""
    if sentiment in ("positive", "neutral", "negative"):
        sentiment_clause = f"AND r.sentiment = '{sentiment}'"

    # pgvector cosine distance: 1 - cosine_similarity
    # We use <=> operator (cosine distance) and convert to similarity
    sql = text(f"""
        SELECT
            r.id,
            r.content,
            r.score,
            r.sentiment,
            r.language,
            r.reviewed_at,
            1 - (r.embedding <=> :query_vec::vector) AS similarity
        FROM reviews r
        WHERE r.datasource_id = :datasource_id
          AND r.embedding IS NOT NULL
          {sentiment_clause}
        ORDER BY r.embedding <=> :query_vec::vector
        LIMIT :limit
    """)

    result = await db.execute(sql, {
        "query_vec": str(query_embedding),
        "datasource_id": datasource_id,
        "limit": limit,
    })
    rows = result.fetchall()

    results = [
        SearchResult(
            review_id=row.id,
            content=row.content,
            score=row.score,
            sentiment=row.sentiment,
            language=row.language,
            reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]

    log.info("semantic_search", query=q, datasource_id=datasource_id, results=len(results))

    return SearchResponse(
        query=q,
        datasource_id=datasource_id,
        results=results,
        total=len(results),
    )


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    RAG endpoint: retrieve relevant reviews semantically, then generate
    a grounded LLM answer with source citations.
    """
    ds_result = await db.execute(
        select(DataSource).where(DataSource.id == body.datasource_id, DataSource.user_id == current_user.id)
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="DataSource not found")

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=422, detail="GROQ_API_KEY not configured.")

    # Step 1: Retrieve top-K semantically relevant reviews
    search_resp = await semantic_search(
        datasource_id=body.datasource_id,
        q=body.query,
        limit=body.limit,
        sentiment=body.sentiment_filter,
        db=db,
        current_user=current_user,
    )

    if not search_resp.results:
        return AskResponse(
            query=body.query,
            answer="No relevant reviews found for this question.",
            sources=[],
            generated_by="none",
        )

    # Step 2: Build context from retrieved reviews
    context_lines = []
    for i, r in enumerate(search_resp.results, 1):
        stars = f"{r.score:.0f}★" if r.score else "no rating"
        context_lines.append(f"[{i}] ({stars}, {r.sentiment or 'unknown'}) {r.content}")
    context = "\n".join(context_lines)

    # Step 3: Generate grounded answer
    prompt = (
        f"You are analyzing user reviews for a mobile app. "
        f"Answer the following question based ONLY on the provided reviews. "
        f"Cite specific reviews using [N] notation. "
        f"If the reviews don't contain relevant information, say so.\n\n"
        f"Question: {body.query}\n\n"
        f"Reviews:\n{context}\n\n"
        f"Answer:"
    )

    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()
        generated_by = "groq"
    except Exception:
        log.exception("ask_llm_failed", query=body.query)
        answer = f"Found {len(search_resp.results)} relevant reviews but LLM generation failed. Top result: {search_resp.results[0].content[:200]}"
        generated_by = "retrieval-only"

    log.info("ask_done", query=body.query, sources=len(search_resp.results), generated_by=generated_by)

    return AskResponse(
        query=body.query,
        answer=answer,
        sources=search_resp.results,
        generated_by=generated_by,
    )
