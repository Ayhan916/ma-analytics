"""Search API: semantic (vector), full-text (BM25), and hybrid (RRF) search over reviews.

Hybrid search uses Reciprocal Rank Fusion to combine pgvector cosine similarity
with PostgreSQL tsvector full-text search. RRF score = 1/(k + rank_vector) + 1/(k + rank_fulltext),
where k=60 is the standard constant that down-weights low-ranked results.

Supported filters (combinable):
  sentiment  — positive | neutral | negative
  date_from  — ISO date string, e.g. "2024-01-01"
  date_to    — ISO date string, e.g. "2024-12-31"
  version    — exact app version string, e.g. "4.2.1"
"""
from __future__ import annotations

import json
import structlog
from datetime import date
from typing import Optional, Literal, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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

_RRF_K = 60
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
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    version: Optional[str] = None
    search_type: Literal["hybrid", "vector", "fulltext"] = "hybrid"
    rerank: bool = False


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult]
    generated_by: str


def _embed_query(query: str) -> Optional[list[float]]:
    """Embed query with the sentence-transformer model.

    Returns None when the ML model is not installed (API-only image without ML libs).
    """
    from app.pipeline.ml import get_embedding_model
    model = get_embedding_model()
    if model is None:
        return None
    return model.encode([query], normalize_embeddings=True)[0].tolist()


def _build_filter_clauses(
    sentiment: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    version: Optional[str],
    alias: str = "r",
) -> tuple[str, dict]:
    """Build WHERE clause fragments and bind params for metadata filters.

    Returns (sql_fragment, params_dict) — sql_fragment starts with AND or is empty.
    """
    clauses: list[str] = []
    params: dict = {}

    if sentiment in ("positive", "neutral", "negative"):
        clauses.append(f"{alias}.sentiment = :sentiment")
        params["sentiment"] = sentiment

    if date_from is not None:
        clauses.append(f"{alias}.reviewed_at >= :date_from")
        params["date_from"] = date_from.isoformat()

    if date_to is not None:
        clauses.append(f"{alias}.reviewed_at < :date_to_exclusive")
        # +1 day so date_to is inclusive
        from datetime import timedelta
        params["date_to_exclusive"] = (date_to + timedelta(days=1)).isoformat()

    if version:
        clauses.append(f"{alias}.version = :version")
        params["version"] = version

    fragment = ("AND " + " AND ".join(clauses)) if clauses else ""
    return fragment, params


async def _vector_search(
    db: AsyncSession,
    datasource_id: str,
    query_embedding: list[float],
    limit: int,
    sentiment: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    version: Optional[str] = None,
) -> list[SearchResult]:
    filter_sql, filter_params = _build_filter_clauses(sentiment, date_from, date_to, version)
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
          {filter_sql}
        ORDER BY r.embedding <=> :query_vec::vector
        LIMIT :limit
    """)
    rows = (await db.execute(sql, {
        "query_vec": str(query_embedding),
        "datasource_id": datasource_id,
        "limit": limit,
        **filter_params,
    })).fetchall()

    return _rows_to_results(rows)


async def _fulltext_search(
    db: AsyncSession,
    datasource_id: str,
    query: str,
    limit: int,
    sentiment: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    version: Optional[str] = None,
) -> list[SearchResult]:
    filter_sql, filter_params = _build_filter_clauses(sentiment, date_from, date_to, version)
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
          {filter_sql}
        ORDER BY similarity DESC
        LIMIT :limit
    """)
    rows = (await db.execute(sql, {
        "query": query,
        "datasource_id": datasource_id,
        "limit": limit,
        **filter_params,
    })).fetchall()

    return _rows_to_results(rows)


async def _hybrid_search(
    db: AsyncSession,
    datasource_id: str,
    query: str,
    query_embedding: list[float],
    limit: int,
    sentiment: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    version: Optional[str] = None,
) -> list[SearchResult]:
    candidate_limit = limit * _RETRIEVER_LIMIT_MULTIPLIER
    filter_sql, filter_params = _build_filter_clauses(sentiment, date_from, date_to, version)

    sql = text(f"""
        WITH vector_ranked AS (
            SELECT
                r.id,
                ROW_NUMBER() OVER (ORDER BY r.embedding <=> :query_vec::vector) AS rn
            FROM reviews r
            WHERE r.datasource_id = :datasource_id
              AND r.embedding IS NOT NULL
              {filter_sql}
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
              {filter_sql}
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
        **filter_params,
    })).fetchall()

    return _rows_to_results(rows)


async def _apply_reranker(query: str, results: list[SearchResult], limit: int) -> list[SearchResult]:
    """Rerank results with a cross-encoder and return the top `limit` by relevance.

    Runs in a thread-pool executor because the cross-encoder is CPU-bound and
    would otherwise block the asyncio event loop.
    Falls back to original ordering when the reranker model is not available (API-only image).
    """
    import asyncio
    from app.pipeline.ml import rerank as _rerank

    texts = [r.content for r in results]

    def _run() -> list[float]:
        return _rerank(query, texts)

    scores = await asyncio.get_event_loop().run_in_executor(None, _run)

    if not scores:
        # Reranker not available — return original results up to limit
        return results[:limit]

    # Attach reranker score as the new similarity and sort descending
    scored = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
    reranked = []
    for score, result in scored[:limit]:
        reranked.append(result.model_copy(update={"similarity": round(float(score), 6)}))
    return reranked


def _rows_to_results(rows) -> list[SearchResult]:
    return [
        SearchResult(
            review_id=row.id,
            content=row.content,
            score=row.score,
            sentiment=row.sentiment,
            language=row.language,
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
    date_from: Optional[date] = Query(default=None, description="Include reviews from this date (inclusive), e.g. 2024-01-01"),
    date_to: Optional[date] = Query(default=None, description="Include reviews up to this date (inclusive), e.g. 2024-12-31"),
    version: Optional[str] = Query(default=None, description="Filter by exact app version, e.g. 4.2.1"),
    search_type: Literal["hybrid", "vector", "fulltext"] = Query(default="hybrid"),
    rerank: bool = Query(default=False, description="Re-score results with a cross-encoder for higher precision"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search over reviews with optional metadata filters.

    Filters (all combinable):
    - sentiment: positive | neutral | negative
    - date_from / date_to: ISO date (YYYY-MM-DD), both inclusive
    - version: exact app version string

    search_type:
    - hybrid (default): RRF fusion of vector + full-text
    - vector: semantic search only
    - fulltext: BM25 keyword search only
    """
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be before or equal to date_to")

    await _verify_datasource(db, datasource_id, current_user.id)

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
            log.warning("hybrid_no_embeddings_fallback", datasource_id=datasource_id)
            search_type = "fulltext"

    # When reranking, pull more candidates so the cross-encoder has enough to choose from
    retrieval_limit = limit * 3 if rerank else limit

    try:
        if search_type == "vector":
            query_embedding = _embed_query(q)
            if query_embedding is None:
                raise HTTPException(status_code=422, detail="Vector search requires ML libs (not installed in this deployment).")
            results = await _vector_search(db, datasource_id, query_embedding, retrieval_limit, sentiment, date_from, date_to, version)

        elif search_type == "fulltext":
            results = await _fulltext_search(db, datasource_id, q, retrieval_limit, sentiment, date_from, date_to, version)

        else:  # hybrid
            query_embedding = _embed_query(q)
            if query_embedding is None:
                log.warning("ml_unavailable_hybrid_fallback", datasource_id=datasource_id)
                results = await _fulltext_search(db, datasource_id, q, retrieval_limit, sentiment, date_from, date_to, version)
                search_type = "fulltext"
            else:
                results = await _hybrid_search(db, datasource_id, q, query_embedding, retrieval_limit, sentiment, date_from, date_to, version)

        if rerank and results:
            results = await _apply_reranker(q, results, limit)

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


def _build_ask_prompt(query: str, results: list[SearchResult]) -> str:
    context_lines = []
    for i, r in enumerate(results, 1):
        stars = f"{r.score:.0f}★" if r.score else "no rating"
        context_lines.append(f"[{i}] ({stars}, {r.sentiment or 'unknown'}) {r.content}")
    context = "\n".join(context_lines)
    return (
        f"You are analyzing user reviews for a mobile app. "
        f"Answer the following question based ONLY on the provided reviews. "
        f"Cite specific reviews using [N] notation. "
        f"If the reviews don't contain relevant information, say so.\n\n"
        f"Question: {query}\n\n"
        f"Reviews:\n{context}\n\n"
        f"Answer:"
    )


async def _ask_event_generator(
    query: str,
    results: list[SearchResult],
    api_key: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """Yield SSE events: sources → token chunks → done (or error)."""
    sources_payload = [r.model_dump() for r in results]
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload})}\n\n"

    if not results:
        yield f"data: {json.dumps({'type': 'done', 'generated_by': 'none'})}\n\n"
        return

    prompt = _build_ask_prompt(query, results)

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'generated_by': 'groq'})}\n\n"
    except Exception:
        log.exception("ask_stream_llm_failed", query=query)
        yield f"data: {json.dumps({'type': 'error', 'message': 'LLM streaming failed'})}\n\n"


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
        date_from=body.date_from,
        date_to=body.date_to,
        version=body.version,
        search_type=body.search_type,
        rerank=body.rerank,
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

    prompt = _build_ask_prompt(body.query, search_resp.results)

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


@router.post("/ask/stream")
async def ask_stream(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming RAG endpoint: retrieves reviews then streams the LLM answer as SSE.

    SSE event types (all JSON-encoded in the `data` field):
    - {"type": "sources", "sources": [...]}   — search results, sent first before LLM starts
    - {"type": "token",   "content": "..."}  — one LLM token chunk
    - {"type": "done",    "generated_by": "groq" | "none"}  — stream complete
    - {"type": "error",   "message": "..."}  — LLM call failed
    """
    await _verify_datasource(db, body.datasource_id, current_user.id)

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=422, detail="GROQ_API_KEY not configured.")

    search_resp = await semantic_search(
        datasource_id=body.datasource_id,
        q=body.query,
        limit=body.limit,
        sentiment=body.sentiment_filter,
        date_from=body.date_from,
        date_to=body.date_to,
        version=body.version,
        search_type=body.search_type,
        rerank=body.rerank,
        db=db,
        current_user=current_user,
    )

    return StreamingResponse(
        _ask_event_generator(body.query, search_resp.results, settings.GROQ_API_KEY, settings.GROQ_MODEL),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
