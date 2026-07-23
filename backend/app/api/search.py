"""Search API: semantic (vector), full-text (BM25), and hybrid (RRF) search over reviews.

Hybrid search uses Reciprocal Rank Fusion to combine pgvector cosine similarity
with PostgreSQL tsvector full-text search. RRF score = 1/(k + rank_vector) + 1/(k + rank_fulltext),
where k=60 is the standard constant that down-weights low-ranked results.
"""
from __future__ import annotations

import structlog
from typing import Optional, Literal
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

# RRF constant — 60 is the standard value from the original RRF paper
_RRF_K = 60
# How many candidates to pull from each retriever before fusing
_RETRIEVER_LIMIT_MULTIPLIER = 5


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
    search_type: str


class AskRequest(BaseModel):
    query: str
    datasource_id: str
    limit: int = 10
    sentiment_filter: Optional[str] = None
    search_type: Literal["hybrid", "vector", "fulltext"] = "hybrid"


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult]
    generated_by: str


def _embed_query(query: str) -> list[float]:
    from app.pipeline.ml import get_embedding_model
    model = get_embedding_model()
    return model.encode([query], normalize_embeddings=True)[0].tolist()


def _sentiment_clause(sentiment: Optional[str], alias: str = "r") -> str:
    if sentiment in ("positive", "neutral", "negative"):
        return f"AND {alias}.sentiment = '{sentiment}'"
    return ""


async def _vector_search(
    db: AsyncSession,
    datasource_id: str,
    query_embedding: list[float],
    limit: int,
    sentiment: Optional[str] = None,
) -> list[SearchResult]:
    """Pure semantic search via pgvector cosine distance."""
    sent = _sentiment_clause(sentiment)
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
          {sent}
        ORDER BY r.embedding <=> :query_vec::vector
        LIMIT :limit
    """)
    rows = (await db.execute(sql, {
        "query_vec": str(query_embedding),
        "datasource_id": datasource_id,
        "limit": limit,
    })).fetchall()

    return [
        SearchResult(
            review_id=row.id, content=row.content, score=row.score,
            sentiment=row.sentiment, language=row.language,
            reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]


async def _fulltext_search(
    db: AsyncSession,
    datasource_id: str,
    query: str,
    limit: int,
    sentiment: Optional[str] = None,
) -> list[SearchResult]:
    """BM25-style full-text search via PostgreSQL tsvector."""
    sent = _sentiment_clause(sentiment)
    sql = text(f"""
        SELECT
            r.id,
            r.content,
            r.score,
            r.sentiment,
            r.language,
            r.reviewed_at,
            ts_rank_cd(r.search_vector, websearch_to_tsquery('simple', :query)) AS similarity
        FROM reviews r
        WHERE r.datasource_id = :datasource_id
          AND r.search_vector IS NOT NULL
          AND r.search_vector @@ websearch_to_tsquery('simple', :query)
          {sent}
        ORDER BY similarity DESC
        LIMIT :limit
    """)
    rows = (await db.execute(sql, {
        "query": query,
        "datasource_id": datasource_id,
        "limit": limit,
    })).fetchall()

    return [
        SearchResult(
            review_id=row.id, content=row.content, score=row.score,
            sentiment=row.sentiment, language=row.language,
            reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]


async def _hybrid_search(
    db: AsyncSession,
    datasource_id: str,
    query: str,
    query_embedding: list[float],
    limit: int,
    sentiment: Optional[str] = None,
) -> list[SearchResult]:
    """Reciprocal Rank Fusion of vector + full-text search.

    Both retrievers fetch limit * 5 candidates so the fusion has enough
    overlap to produce high-quality top-K results.
    """
    candidate_limit = limit * _RETRIEVER_LIMIT_MULTIPLIER
    sent = _sentiment_clause(sentiment)

    sql = text(f"""
        WITH vector_ranked AS (
            SELECT
                r.id,
                ROW_NUMBER() OVER (ORDER BY r.embedding <=> :query_vec::vector) AS rn
            FROM reviews r
            WHERE r.datasource_id = :datasource_id
              AND r.embedding IS NOT NULL
              {sent}
            ORDER BY r.embedding <=> :query_vec::vector
            LIMIT :candidate_limit
        ),
        text_ranked AS (
            SELECT
                r.id,
                ROW_NUMBER() OVER (
                    ORDER BY ts_rank_cd(r.search_vector, websearch_to_tsquery('simple', :query)) DESC
                ) AS rn
            FROM reviews r
            WHERE r.datasource_id = :datasource_id
              AND r.search_vector IS NOT NULL
              AND r.search_vector @@ websearch_to_tsquery('simple', :query)
              {sent}
            ORDER BY ts_rank_cd(r.search_vector, websearch_to_tsquery('simple', :query)) DESC
            LIMIT :candidate_limit
        ),
        fused AS (
            SELECT
                COALESCE(v.id, t.id) AS id,
                COALESCE(1.0 / (:rrf_k + v.rn), 0.0)
                    + COALESCE(1.0 / (:rrf_k + t.rn), 0.0) AS rrf_score
            FROM vector_ranked v
            FULL OUTER JOIN text_ranked t ON v.id = t.id
        )
        SELECT
            r.id,
            r.content,
            r.score,
            r.sentiment,
            r.language,
            r.reviewed_at,
            f.rrf_score AS similarity
        FROM fused f
        JOIN reviews r ON r.id = f.id
        ORDER BY f.rrf_score DESC
        LIMIT :limit
    """)

    rows = (await db.execute(sql, {
        "query_vec": str(query_embedding),
        "query": query,
        "datasource_id": datasource_id,
        "candidate_limit": candidate_limit,
        "rrf_k": _RRF_K,
        "limit": limit,
    })).fetchall()

    return [
        SearchResult(
            review_id=row.id, content=row.content, score=row.score,
            sentiment=row.sentiment, language=row.language,
            reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
            similarity=round(float(row.similarity), 6),
        )
        for row in rows
    ]


async def _verify_datasource(db: AsyncSession, datasource_id: str, user_id: str) -> None:
    ds_result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == user_id)
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="DataSource not found")


@router.get("", response_model=SearchResponse)
async def semantic_search(
    datasource_id: str = Query(...),
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, le=50),
    sentiment: Optional[str] = Query(default=None),
    search_type: Literal["hybrid", "vector", "fulltext"] = Query(default="hybrid"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search over reviews.

    search_type:
      - hybrid   (default) — RRF fusion of vector + full-text
      - vector   — semantic search only (pgvector cosine)
      - fulltext — BM25 keyword search only (tsvector)
    """
    await _verify_datasource(db, datasource_id, current_user.id)

    # Vector search needs embeddings
    if search_type in ("hybrid", "vector"):
        count_result = await db.execute(
            select(func.count()).select_from(Review).where(
                Review.datasource_id == datasource_id,
                Review.embedding.isnot(None),
            )
        )
        if (count_result.scalar() or 0) == 0:
            if search_type == "vector":
                raise HTTPException(
                    status_code=422,
                    detail="No embeddings found. Run the ML pipeline first.",
                )
            # hybrid falls back to fulltext if no embeddings
            log.warning("hybrid_no_embeddings_fallback", datasource_id=datasource_id)
            search_type = "fulltext"

    try:
        if search_type == "vector":
            query_embedding = _embed_query(q)
            results = await _vector_search(db, datasource_id, query_embedding, limit, sentiment)

        elif search_type == "fulltext":
            results = await _fulltext_search(db, datasource_id, q, limit, sentiment)

        else:  # hybrid
            query_embedding = _embed_query(q)
            results = await _hybrid_search(db, datasource_id, q, query_embedding, limit, sentiment)

    except HTTPException:
        raise
    except Exception:
        log.exception("search_failed", query=q, search_type=search_type)
        raise HTTPException(status_code=500, detail="Search failed.")

    log.info("search_done", query=q, type=search_type, results=len(results))

    return SearchResponse(
        query=q,
        datasource_id=datasource_id,
        results=results,
        total=len(results),
        search_type=search_type,
    )


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RAG endpoint: retrieve relevant reviews, then generate a grounded LLM answer."""
    await _verify_datasource(db, body.datasource_id, current_user.id)

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=422, detail="GROQ_API_KEY not configured.")

    search_resp = await semantic_search(
        datasource_id=body.datasource_id,
        q=body.query,
        limit=body.limit,
        sentiment=body.sentiment_filter,
        search_type=body.search_type,
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

    context_lines = []
    for i, r in enumerate(search_resp.results, 1):
        stars = f"{r.score:.0f}★" if r.score else "no rating"
        context_lines.append(f"[{i}] ({stars}, {r.sentiment or 'unknown'}) {r.content}")
    context = "\n".join(context_lines)

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
        answer = (
            f"Found {len(search_resp.results)} relevant reviews but LLM generation failed. "
            f"Top result: {search_resp.results[0].content[:200]}"
        )
        generated_by = "retrieval-only"

    log.info("ask_done", query=body.query, sources=len(search_resp.results), generated_by=generated_by)

    return AskResponse(
        query=body.query,
        answer=answer,
        sources=search_resp.results,
        generated_by=generated_by,
    )
