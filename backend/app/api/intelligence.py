"""Intelligence API — Feature Matrix, Signal Explorer, Narratives."""
from __future__ import annotations
import uuid
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.datasource import DataSource
from app.models.user import User

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class FeatureSignalType(BaseModel):
    signal_type: str
    count: int


class FeatureVersionCell(BaseModel):
    version: str
    mention_count: int
    avg_severity: Optional[float]
    bug_count: int
    resolved_count: int


class FeatureRow(BaseModel):
    feature: str
    total_mentions: int
    avg_severity: Optional[float]
    narrative: Optional[str]
    signal_types: list[FeatureSignalType]
    top_versions: list[FeatureVersionCell]


class FeatureMatrix(BaseModel):
    datasource_id: str
    features: list[FeatureRow]
    total_sentences: int
    total_signals: int
    n_topics: int


class SentenceSignal(BaseModel):
    id: str
    review_id: str
    text: str
    review_content: Optional[str]
    feature: str
    signal_type: str
    severity: Optional[int]
    is_resolved: bool
    version: Optional[str]
    reviewed_at: Optional[str]
    score: Optional[float]


class FeatureDetail(BaseModel):
    feature: str
    datasource_id: str
    narrative: Optional[str]
    mention_count: int
    avg_severity: Optional[float]
    signal_types: list[FeatureSignalType]
    version_trend: list[FeatureVersionCell]
    top_signals: list[SentenceSignal]


async def _check_datasource(db: AsyncSession, datasource_id: str, user_id: str) -> DataSource:
    result = await db.execute(
        select(DataSource).where(DataSource.id == datasource_id, DataSource.user_id == user_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return ds


@router.get("/matrix", response_model=FeatureMatrix)
async def get_feature_matrix(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the Feature × Version matrix for a datasource."""
    await _check_datasource(db, datasource_id, current_user.id)

    # Count totals
    counts = await db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM review_aspects WHERE datasource_id = :ds_id) AS sentence_count,
                (SELECT COUNT(*) FROM review_signals WHERE datasource_id = :ds_id) AS signal_count,
                (SELECT COUNT(DISTINCT feature) FROM review_aspects WHERE datasource_id = :ds_id) AS n_topics
        """),
        {"ds_id": datasource_id},
    )
    totals = counts.one()

    # Per-feature aggregation
    feat_rows = await db.execute(
        text("""
            SELECT
                rs.feature,
                COUNT(*) AS total_mentions,
                AVG(rs.severity) AS avg_severity
            FROM review_signals rs
            WHERE rs.datasource_id = :ds_id
            GROUP BY rs.feature
            HAVING COUNT(*) >= 3
            ORDER BY COUNT(*) DESC
            LIMIT 50
        """),
        {"ds_id": datasource_id},
    )
    features_raw = feat_rows.fetchall()

    if not features_raw:
        return FeatureMatrix(
            datasource_id=datasource_id,
            features=[],
            total_sentences=totals.sentence_count or 0,
            total_signals=totals.signal_count or 0,
            n_topics=totals.n_topics or 0,
        )

    feature_names = [r.feature for r in features_raw]

    # Signal type breakdown per feature
    st_rows = await db.execute(
        text("""
            SELECT feature, signal_type, COUNT(*) AS cnt
            FROM review_signals
            WHERE datasource_id = :ds_id AND feature = ANY(:features)
            GROUP BY feature, signal_type
        """),
        {"ds_id": datasource_id, "features": feature_names},
    )
    signal_type_map: dict[str, list[FeatureSignalType]] = {}
    for row in st_rows.fetchall():
        signal_type_map.setdefault(row.feature, []).append(
            FeatureSignalType(signal_type=row.signal_type, count=row.cnt)
        )

    # Top-5 versions per feature
    ver_rows = await db.execute(
        text("""
            SELECT
                rs.feature,
                COALESCE(rs.version_hint, rev.version, 'unknown') AS version,
                COUNT(*) AS mention_count,
                AVG(rs.severity) AS avg_severity,
                SUM(CASE WHEN rs.signal_type = 'bug' THEN 1 ELSE 0 END) AS bug_count,
                SUM(CASE WHEN rs.is_resolved THEN 1 ELSE 0 END) AS resolved_count,
                MIN(rev.reviewed_at) AS first_seen
            FROM review_signals rs
            JOIN reviews rev ON rs.review_id = rev.id
            WHERE rs.datasource_id = :ds_id AND rs.feature = ANY(:features)
              AND COALESCE(rs.version_hint, rev.version) IS NOT NULL
            GROUP BY rs.feature, COALESCE(rs.version_hint, rev.version, 'unknown')
            ORDER BY rs.feature, first_seen DESC
        """),
        {"ds_id": datasource_id, "features": feature_names},
    )
    version_map: dict[str, list[FeatureVersionCell]] = {}
    for row in ver_rows.fetchall():
        version_map.setdefault(row.feature, []).append(
            FeatureVersionCell(
                version=row.version,
                mention_count=row.mention_count,
                avg_severity=round(float(row.avg_severity), 2) if row.avg_severity else None,
                bug_count=row.bug_count or 0,
                resolved_count=row.resolved_count or 0,
            )
        )
    # Keep top 5 versions per feature
    version_map = {f: cells[:5] for f, cells in version_map.items()}

    # Load narratives
    narr_rows = await db.execute(
        text("SELECT feature, narrative FROM feature_narratives WHERE datasource_id = :ds_id"),
        {"ds_id": datasource_id},
    )
    narrative_map = {r.feature: r.narrative for r in narr_rows.fetchall()}

    features_out = []
    for row in features_raw:
        features_out.append(FeatureRow(
            feature=row.feature,
            total_mentions=row.total_mentions,
            avg_severity=round(float(row.avg_severity), 2) if row.avg_severity else None,
            narrative=narrative_map.get(row.feature),
            signal_types=signal_type_map.get(row.feature, []),
            top_versions=version_map.get(row.feature, []),
        ))

    return FeatureMatrix(
        datasource_id=datasource_id,
        features=features_out,
        total_sentences=totals.sentence_count or 0,
        total_signals=totals.signal_count or 0,
        n_topics=totals.n_topics or 0,
    )


@router.get("/feature", response_model=FeatureDetail)
async def get_feature_detail(
    datasource_id: str,
    feature: str,
    signal_type_filter: Optional[str] = None,
    version_filter: Optional[str] = None,
    sort_by: Optional[str] = None,  # datum_neu | datum_alt | version | bewertung | severity
    date_from: Optional[str] = None,    # YYYY-MM-DD
    date_to: Optional[str] = None,      # YYYY-MM-DD
    version_from: Optional[str] = None, # version string range start
    version_to: Optional[str] = None,   # version string range end
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return detailed view for one feature: version trend + top sentences."""
    await _check_datasource(db, datasource_id, current_user.id)

    # Narrative
    narr = await db.execute(
        text("SELECT narrative, feature_request_narrative, mention_count, avg_severity FROM feature_narratives WHERE datasource_id = :ds_id AND feature = :feat"),
        {"ds_id": datasource_id, "feat": feature},
    )
    narr_row = narr.one_or_none()

    # Signal types
    st = await db.execute(
        text("""
            SELECT signal_type, COUNT(*) AS cnt
            FROM review_signals
            WHERE datasource_id = :ds_id AND feature = :feat
            GROUP BY signal_type ORDER BY cnt DESC
        """),
        {"ds_id": datasource_id, "feat": feature},
    )
    signal_types = [FeatureSignalType(signal_type=r.signal_type, count=r.cnt) for r in st.fetchall()]

    # Version trend
    vt = await db.execute(
        text("""
            SELECT
                COALESCE(rs.version_hint, rev.version, 'unknown') AS version,
                COUNT(*) AS mention_count,
                AVG(rs.severity) AS avg_severity,
                SUM(CASE WHEN rs.signal_type = 'bug' THEN 1 ELSE 0 END) AS bug_count,
                SUM(CASE WHEN rs.is_resolved THEN 1 ELSE 0 END) AS resolved_count,
                MIN(rev.reviewed_at) AS first_seen
            FROM review_signals rs
            JOIN reviews rev ON rs.review_id = rev.id
            WHERE rs.datasource_id = :ds_id AND rs.feature = :feat
              AND COALESCE(rs.version_hint, rev.version) IS NOT NULL
            GROUP BY COALESCE(rs.version_hint, rev.version, 'unknown')
            ORDER BY first_seen DESC
            LIMIT 20
        """),
        {"ds_id": datasource_id, "feat": feature},
    )
    version_trend = [
        FeatureVersionCell(
            version=r.version,
            mention_count=r.mention_count,
            avg_severity=round(float(r.avg_severity), 2) if r.avg_severity else None,
            bug_count=r.bug_count or 0,
            resolved_count=r.resolved_count or 0,
        )
        for r in vt.fetchall()
    ]

    # Top signals — with optional signal_type, version, date filters and sort
    is_filtered = bool(signal_type_filter or version_filter or sort_by or date_from or date_to or version_from or version_to)
    row_limit = 100 if is_filtered else 30
    extra_where = ""
    params: dict = {"ds_id": datasource_id, "feat": feature}
    if signal_type_filter:
        extra_where += " AND rs.signal_type = :sig_type"
        params["sig_type"] = signal_type_filter
    if version_filter:
        extra_where += " AND COALESCE(rs.version_hint, rev.version) = :ver"
        params["ver"] = version_filter
    if date_from:
        extra_where += " AND rev.reviewed_at >= :date_from"
        params["date_from"] = date_type.fromisoformat(date_from)
    if date_to:
        extra_where += " AND rev.reviewed_at <= :date_to"
        params["date_to"] = date_type.fromisoformat(date_to)
    if version_from or version_to:
        # Fetch versions ordered chronologically by first appearance
        ver_order_res = await db.execute(
            text("""
                SELECT COALESCE(rs2.version_hint, rev2.version) AS ver
                FROM review_signals rs2
                JOIN reviews rev2 ON rs2.review_id = rev2.id
                WHERE rs2.datasource_id = :ds_id AND rs2.feature = :feat
                  AND COALESCE(rs2.version_hint, rev2.version) IS NOT NULL
                GROUP BY 1
                ORDER BY MIN(rev2.reviewed_at) ASC
            """),
            {"ds_id": datasource_id, "feat": feature},
        )
        ordered_versions = [r.ver for r in ver_order_res.fetchall()]
        from_idx = ordered_versions.index(version_from) if version_from and version_from in ordered_versions else 0
        to_idx = ordered_versions.index(version_to) if version_to and version_to in ordered_versions else len(ordered_versions) - 1
        lo, hi = min(from_idx, to_idx), max(from_idx, to_idx)
        selected_versions = ordered_versions[lo : hi + 1]
        if selected_versions:
            placeholders = ", ".join(f":vr_{i}" for i in range(len(selected_versions)))
            extra_where += f" AND COALESCE(rs.version_hint, rev.version) IN ({placeholders})"
            for i, v in enumerate(selected_versions):
                params[f"vr_{i}"] = v

    order_clause = {
        "datum_neu":  "rev.reviewed_at DESC NULLS LAST",
        "datum_alt":  "rev.reviewed_at ASC NULLS LAST",
        "version":    "COALESCE(rs.version_hint, rev.version) DESC NULLS LAST, rev.reviewed_at DESC NULLS LAST",
        "bewertung":  "rev.score DESC NULLS LAST, rev.reviewed_at DESC NULLS LAST",
        "severity":   "rs.severity DESC NULLS LAST, rev.reviewed_at DESC NULLS LAST",
    }.get(sort_by or "", (
        "CASE rs.signal_type WHEN 'bug' THEN 1 WHEN 'resolution' THEN 2 ELSE 3 END, "
        "rs.severity DESC NULLS LAST, rev.reviewed_at DESC NULLS LAST"
    ))

    sigs = await db.execute(
        text(f"""
            SELECT rs.id,
                   rev.id AS review_id,
                   COALESCE(NULLIF(asp.span_text, ''), rs.feature) AS text,
                   rev.content AS review_content,
                   rs.signal_type, rs.severity, rs.is_resolved,
                   COALESCE(rs.version_hint, rev.version) AS version,
                   rev.reviewed_at, rev.score
            FROM review_signals rs
            LEFT JOIN review_aspects asp ON rs.aspect_id = asp.id
            JOIN reviews rev ON rs.review_id = rev.id
            WHERE rs.datasource_id = :ds_id AND rs.feature = :feat
            {extra_where}
            ORDER BY {order_clause}
            LIMIT {row_limit}
        """),
        params,
    )
    top_signals = [
        SentenceSignal(
            id=r.id,
            review_id=r.review_id,
            text=r.text,
            review_content=r.review_content,
            feature=feature,
            signal_type=r.signal_type,
            severity=r.severity,
            is_resolved=r.is_resolved,
            version=r.version,
            reviewed_at=str(r.reviewed_at)[:10] if r.reviewed_at else None,
            score=float(r.score) if r.score else None,
        )
        for r in sigs.fetchall()
    ]

    total = sum(st.count for st in signal_types)
    avg_sev = narr_row.avg_severity if narr_row else None

    chosen_narrative = None
    if narr_row:
        if signal_type_filter == "feature_request" and narr_row.feature_request_narrative:
            chosen_narrative = narr_row.feature_request_narrative
        else:
            chosen_narrative = narr_row.narrative

    return FeatureDetail(
        feature=feature,
        datasource_id=datasource_id,
        narrative=chosen_narrative,
        mention_count=narr_row.mention_count if narr_row else total,
        avg_severity=round(float(avg_sev), 2) if avg_sev else None,
        signal_types=signal_types,
        version_trend=version_trend,
        top_signals=top_signals,
    )


# ─── Review Aspects ──────────────────────────────────────────────────────────

class ReviewAspectOut(BaseModel):
    aspect_term: Optional[str]
    feature: str
    sentiment: str
    confidence: Optional[float]


@router.get("/review/{review_id}/aspects", response_model=list[ReviewAspectOut])
async def get_review_aspects(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return ABSA aspects extracted from one review."""
    rows = await db.execute(
        text("""
            SELECT asp.aspect_term, asp.feature, asp.sentiment, asp.confidence
            FROM review_aspects asp
            JOIN reviews rev ON asp.review_id = rev.id
            JOIN datasources ds ON rev.datasource_id = ds.id
            WHERE asp.review_id = :rid AND ds.user_id = :uid
            ORDER BY asp.confidence DESC NULLS LAST
        """),
        {"rid": review_id, "uid": current_user.id},
    )
    return [
        ReviewAspectOut(
            aspect_term=r.aspect_term,
            feature=r.feature,
            sentiment=r.sentiment,
            confidence=round(float(r.confidence), 3) if r.confidence else None,
        )
        for r in rows.fetchall()
    ]


# ─── Version Feature Breakdown ───────────────────────────────────────────────

class VersionFeatureRow(BaseModel):
    feature: str
    total: int
    bug_count: int
    resolved_count: int
    avg_severity: Optional[float]
    neg_pct: int


class VersionBreakdown(BaseModel):
    version: str
    datasource_id: str
    features: list[VersionFeatureRow]


@router.get("/version-breakdown", response_model=VersionBreakdown)
async def get_version_breakdown(
    datasource_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return ABSA feature breakdown for a specific app version."""
    await _check_datasource(db, datasource_id, current_user.id)

    rows = await db.execute(
        text("""
            SELECT
                rs.feature,
                COUNT(*) AS total,
                SUM(CASE WHEN rs.signal_type = 'bug' THEN 1 ELSE 0 END) AS bug_count,
                SUM(CASE WHEN rs.is_resolved THEN 1 ELSE 0 END) AS resolved_count,
                AVG(rs.severity) AS avg_severity,
                SUM(CASE WHEN asp.sentiment = 'negative' THEN 1 ELSE 0 END) AS neg_count
            FROM review_signals rs
            LEFT JOIN review_aspects asp ON rs.aspect_id = asp.id
            JOIN reviews rev ON rs.review_id = rev.id
            WHERE rs.datasource_id = :ds_id
              AND COALESCE(rs.version_hint, rev.version) = :ver
              AND rs.feature != 'General'
            GROUP BY rs.feature
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
        """),
        {"ds_id": datasource_id, "ver": version},
    )
    features = [
        VersionFeatureRow(
            feature=r.feature,
            total=r.total,
            bug_count=r.bug_count or 0,
            resolved_count=r.resolved_count or 0,
            avg_severity=round(float(r.avg_severity), 1) if r.avg_severity else None,
            neg_pct=int(100 * (r.neg_count or 0) / r.total) if r.total else 0,
        )
        for r in rows.fetchall()
    ]
    return VersionBreakdown(version=version, datasource_id=datasource_id, features=features)


# ─── Backfill Developer Replies ──────────────────────────────────────────────

class BackfillJob(BaseModel):
    job_id: str
    message: str


@router.post("/backfill-replies", response_model=BackfillJob)
async def trigger_backfill_replies(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-scrape Google Play to backfill developer reply_content for existing reviews."""
    ds = await _check_datasource(db, datasource_id, current_user.id)

    if not ds.app_id or not ds.scrape_lang or not ds.scrape_country:
        raise HTTPException(status_code=400, detail="DataSource has no Google Play config (app_id/lang/country missing)")

    from app.models.pipeline_job import PipelineJob, JobStatus
    from app.pipeline.tasks import backfill_replies

    job_id = str(uuid.uuid4())
    job = PipelineJob(
        id=job_id,
        datasource_id=datasource_id,
        status=JobStatus.queued,
        progress="queued",
    )
    db.add(job)
    await db.commit()

    backfill_replies.delay(job_id, datasource_id, ds.app_id, ds.scrape_lang, ds.scrape_country)

    return BackfillJob(job_id=job_id, message=f"Backfill gestartet — Job {job_id}")


@router.post("/resynthesize", response_model=BackfillJob)
async def trigger_resynthesize(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-generate all Groq narratives without re-running ABSA."""
    await _check_datasource(db, datasource_id, current_user.id)

    from app.models.pipeline_job import PipelineJob, JobStatus
    from app.pipeline.tasks import resynthesize_narratives

    job_id = str(uuid.uuid4())
    job = PipelineJob(
        id=job_id,
        datasource_id=datasource_id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(job)
    await db.commit()

    resynthesize_narratives.delay(job_id, datasource_id)

    return BackfillJob(job_id=job_id, message=f"Narrative-Synthese gestartet — Job {job_id}")


@router.post("/reclassify-general", response_model=BackfillJob)
async def trigger_reclassify_general(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-classify existing 'General' aspects using the updated keyword taxonomy.
    Does NOT re-run pyABSA or scraping — just keyword matching on stored data.
    Completes in seconds. Re-synthesizes narratives for affected features afterwards.
    """
    await _check_datasource(db, datasource_id, current_user.id)

    from app.models.pipeline_job import PipelineJob, JobStatus
    from app.pipeline.tasks import reclassify_general

    job_id = str(uuid.uuid4())
    job = PipelineJob(
        id=job_id,
        datasource_id=datasource_id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(job)
    await db.commit()

    reclassify_general.delay(job_id, datasource_id)

    return BackfillJob(job_id=job_id, message=f"Reklassifizierung gestartet — Job {job_id}")


@router.post("/reclassify-signals", response_model=BackfillJob)
async def trigger_reclassify_signals(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run signal type classification on all existing signals using updated keyword patterns."""
    await _check_datasource(db, datasource_id, current_user.id)

    from app.models.pipeline_job import PipelineJob, JobStatus
    from app.pipeline.tasks import reclassify_signals

    job_id = str(uuid.uuid4())
    job = PipelineJob(
        id=job_id,
        datasource_id=datasource_id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(job)
    await db.commit()

    reclassify_signals.delay(job_id, datasource_id)

    return BackfillJob(job_id=job_id, message=f"Signal-Reklassifizierung gestartet — Job {job_id}")


@router.post("/cluster-general", response_model=BackfillJob)
async def trigger_cluster_general(
    datasource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cluster remaining 'General' aspects by semantic similarity using stored embeddings.
    No re-scraping or re-embedding needed. Groq labels each discovered cluster.
    HDBSCAN noise points stay as 'General'.
    """
    await _check_datasource(db, datasource_id, current_user.id)

    from app.models.pipeline_job import PipelineJob, JobStatus
    from app.pipeline.tasks import cluster_general_reviews

    job_id = str(uuid.uuid4())
    job = PipelineJob(
        id=job_id,
        datasource_id=datasource_id,
        status=JobStatus.pending,
        progress="queued",
    )
    db.add(job)
    await db.commit()

    cluster_general_reviews.delay(job_id, datasource_id)

    return BackfillJob(job_id=job_id, message=f"Clustering gestartet — Job {job_id}")


# ─── Resolution Check ─────────────────────────────────────────────────────────

class ResolutionCheck(BaseModel):
    review_id: str
    feature: Optional[str]
    verdict: str          # behoben | wahrscheinlich_behoben | offen | keine_daten
    confidence: str       # hoch | mittel | niedrig
    developer_reply: Optional[str]
    developer_reply_at: Optional[str]
    resolution_signals_after: int
    bug_count_same_version: int
    bug_count_newer_versions: int
    last_bug_version: Optional[str]
    synthesis: str


def _groq_resolution_synthesis(
    review_content: str,
    feature: Optional[str],
    developer_reply: Optional[str],
    resolution_signals_after: int,
    bug_count_same_version: int,
    bug_count_newer_versions: int,
    last_bug_version: Optional[str],
    groq_api_key: str,
) -> str:
    evidence_parts = []
    if developer_reply:
        evidence_parts.append(f"Hersteller-Antwort: \"{developer_reply[:300]}\"")
    if resolution_signals_after > 0:
        evidence_parts.append(f"{resolution_signals_after} Nutzer meldeten danach eine Lösung für dieses Feature")
    if bug_count_newer_versions == 0 and bug_count_same_version > 0:
        evidence_parts.append("In neueren Versionen wurden keine ähnlichen Fehler mehr gemeldet")
    elif bug_count_newer_versions > 0:
        evidence_parts.append(f"In neueren Versionen wurden noch {bug_count_newer_versions} ähnliche Fehler gemeldet")
    if last_bug_version:
        evidence_parts.append(f"Letzter bekannter Fehlerbericht: Version {last_bug_version}")

    evidence_text = "\n".join(f"- {e}" for e in evidence_parts) if evidence_parts else "- Keine direkten Hinweise vorhanden"

    prompt = (
        f"Du analysierst einen App-Store-Review und prüfst, ob das gemeldete Problem behoben wurde.\n\n"
        f"Review: \"{review_content[:400]}\"\n"
        f"Feature-Bereich: {feature or 'unbekannt'}\n\n"
        f"Verfügbare Evidenz:\n{evidence_text}\n\n"
        "Beantworte kurz und präzise auf Deutsch (2–3 Sätze): Wurde dieses Problem behoben? "
        "Nenne konkrete Hinweise oder erkläre warum keine Aussage möglich ist."
    )
    try:
        from groq import Groq
        resp = Groq(api_key=groq_api_key).chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # Rule-based fallback
        if developer_reply:
            return f"Der Hersteller hat auf diesen Review geantwortet: \"{developer_reply[:200]}\""
        if resolution_signals_after > 0 and bug_count_newer_versions == 0:
            return "Indirekte Hinweise deuten auf eine Behebung hin: In neueren Versionen wurden keine ähnlichen Fehler mehr gemeldet."
        if bug_count_newer_versions > 0:
            return f"Das Problem scheint weiterhin offen zu sein — in neueren Versionen wurden noch {bug_count_newer_versions} ähnliche Fehler gemeldet."
        return "Es liegen keine ausreichenden Hinweise vor, um eine Aussage über die Behebung zu machen."


@router.get("/review/{review_id}/resolution-check", response_model=ResolutionCheck)
async def get_resolution_check(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if the issue reported in a review has been resolved."""
    # Fetch review — verify ownership via datasource
    rev_row = await db.execute(
        text("""
            SELECT rev.id, rev.content, rev.reply_content, rev.reply_at,
                   rev.reviewed_at, rev.version, rev.score, ds.user_id
            FROM reviews rev
            JOIN datasources ds ON rev.datasource_id = ds.id
            WHERE rev.id = :rid AND ds.user_id = :uid
        """),
        {"rid": review_id, "uid": current_user.id},
    )
    rev = rev_row.one_or_none()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found")

    # Get dominant feature for this review
    feat_row = await db.execute(
        text("""
            SELECT feature, COUNT(*) AS cnt
            FROM review_signals
            WHERE review_id = :rid AND feature != 'General'
            GROUP BY feature ORDER BY cnt DESC LIMIT 1
        """),
        {"rid": review_id},
    )
    feat_result = feat_row.one_or_none()
    feature = feat_result.feature if feat_result else None

    resolution_signals_after = 0
    bug_count_same_version = 0
    bug_count_newer_versions = 0
    last_bug_version = None

    if feature and rev.reviewed_at:
        # Resolution signals for same feature AFTER this review's date
        rs_after = await db.execute(
            text("""
                SELECT COUNT(*) AS cnt FROM review_signals rs
                JOIN reviews r ON rs.review_id = r.id
                WHERE rs.feature = :feat
                  AND rs.signal_type = 'resolution'
                  AND r.reviewed_at > :dt
                  AND r.datasource_id = (SELECT datasource_id FROM reviews WHERE id = :rid)
            """),
            {"feat": feature, "dt": rev.reviewed_at, "rid": review_id},
        )
        resolution_signals_after = rs_after.scalar() or 0

        # Bug counts by version relative to this review's version
        if rev.version:
            bugs_row = await db.execute(
                text("""
                    SELECT
                        COALESCE(rs.version_hint, r.version) AS ver,
                        COUNT(*) AS cnt
                    FROM review_signals rs
                    JOIN reviews r ON rs.review_id = r.id
                    WHERE rs.feature = :feat
                      AND rs.signal_type = 'bug'
                      AND r.datasource_id = (SELECT datasource_id FROM reviews WHERE id = :rid)
                      AND COALESCE(rs.version_hint, r.version) IS NOT NULL
                    GROUP BY COALESCE(rs.version_hint, r.version)
                    ORDER BY MIN(r.reviewed_at) DESC
                """),
                {"feat": feature, "rid": review_id},
            )
            bug_rows = bugs_row.fetchall()

            # Split into same/older vs newer based on reviewed_at of this review
            newer_bugs = await db.execute(
                text("""
                    SELECT COUNT(*) FROM review_signals rs
                    JOIN reviews r ON rs.review_id = r.id
                    WHERE rs.feature = :feat AND rs.signal_type = 'bug'
                      AND r.reviewed_at > :dt
                      AND r.datasource_id = (SELECT datasource_id FROM reviews WHERE id = :rid)
                """),
                {"feat": feature, "dt": rev.reviewed_at, "rid": review_id},
            )
            bug_count_newer_versions = newer_bugs.scalar() or 0

            older_bugs = await db.execute(
                text("""
                    SELECT COUNT(*) FROM review_signals rs
                    JOIN reviews r ON rs.review_id = r.id
                    WHERE rs.feature = :feat AND rs.signal_type = 'bug'
                      AND r.reviewed_at <= :dt
                      AND r.datasource_id = (SELECT datasource_id FROM reviews WHERE id = :rid)
                """),
                {"feat": feature, "dt": rev.reviewed_at, "rid": review_id},
            )
            bug_count_same_version = older_bugs.scalar() or 0

            if bug_rows:
                last_bug_version = bug_rows[0].ver

    # Determine verdict
    has_reply = bool(rev.reply_content)
    if has_reply and bug_count_newer_versions == 0:
        verdict, confidence = "behoben", "hoch"
    elif has_reply:
        verdict, confidence = "wahrscheinlich_behoben", "mittel"
    elif resolution_signals_after > 2 and bug_count_newer_versions == 0:
        verdict, confidence = "wahrscheinlich_behoben", "mittel"
    elif bug_count_newer_versions > bug_count_same_version * 0.5:
        verdict, confidence = "offen", "mittel"
    elif bug_count_newer_versions == 0 and resolution_signals_after > 0:
        verdict, confidence = "wahrscheinlich_behoben", "niedrig"
    else:
        verdict, confidence = "keine_daten", "niedrig"

    # Groq synthesis (run in thread to not block async loop)
    from app.core.config import settings
    import asyncio
    synthesis = await asyncio.to_thread(
        _groq_resolution_synthesis,
        rev.content,
        feature,
        rev.reply_content,
        resolution_signals_after,
        bug_count_same_version,
        bug_count_newer_versions,
        last_bug_version,
        settings.GROQ_API_KEY,
    )

    return ResolutionCheck(
        review_id=review_id,
        feature=feature,
        verdict=verdict,
        confidence=confidence,
        developer_reply=rev.reply_content,
        developer_reply_at=str(rev.reply_at)[:10] if rev.reply_at else None,
        resolution_signals_after=resolution_signals_after,
        bug_count_same_version=bug_count_same_version,
        bug_count_newer_versions=bug_count_newer_versions,
        last_bug_version=last_bug_version,
        synthesis=synthesis,
    )


# ─── Similar History ──────────────────────────────────────────────────────────

class SimilarOccurrence(BaseModel):
    version: Optional[str]
    date: Optional[str]
    count: int
    has_reply: bool
    example_content: str
    reply_content: Optional[str]
    reply_at: Optional[str]


class SimilarHistoryResult(BaseModel):
    review_id: str
    feature: Optional[str]
    signal_type: Optional[str]
    total_similar: int
    occurrences: list[SimilarOccurrence]
    has_any_reply: bool
    synthesis: str


def _groq_similar_synthesis(
    feature: Optional[str],
    signal_type: Optional[str],
    total: int,
    occurrences: list[dict],
    groq_api_key: str,
) -> str:
    if not total:
        return "Dieses Problem wurde in der Vergangenheit nicht gemeldet — es handelt sich um einen erstmaligen Bericht."

    with_reply = [o for o in occurrences if o["has_reply"]]
    versions = [o["version"] for o in occurrences if o["version"]]

    occ_lines = "\n".join(
        f'- v{o["version"] or "?"} ({o["date"] or "?"}) — {o["count"]}× gemeldet'
        + (f', Hersteller hat geantwortet: "{o["reply_content"][:150]}"' if o["reply_content"] else "")
        for o in occurrences[:8]
    )

    prompt = (
        f"Du analysierst die Verlaufshistorie eines App-Problems.\n\n"
        f"Feature: {feature or 'unbekannt'} | Signal-Typ: {signal_type or 'unbekannt'}\n"
        f"Gesamtanzahl ähnlicher Berichte: {total}\n"
        f"Vorkommen nach Version:\n{occ_lines}\n\n"
        "Beantworte auf Deutsch in 2–3 Sätzen:\n"
        "1. Wie oft und in welchen Versionen trat das Problem auf?\n"
        "2. Hat der Hersteller jemals darauf geantwortet?\n"
        "3. Zeigt der Trend Besserung oder Verschlechterung?"
    )
    try:
        from groq import Groq
        resp = Groq(api_key=groq_api_key).chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        if not with_reply:
            return f"Ähnliche Probleme wurden {total}× in {len(occurrences)} Versionen gemeldet. Der Hersteller hat auf keinen dieser Berichte geantwortet."
        return (
            f"Ähnliche Probleme wurden {total}× gemeldet. "
            f"In {len(with_reply)} Version(en) antwortete der Hersteller, zuletzt: \"{with_reply[0]['reply_content'][:120]}\""
        )


@router.get("/review/{review_id}/similar-history", response_model=SimilarHistoryResult)
async def get_similar_history(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find past occurrences of similar issues for the same feature."""
    # Verify ownership + get review metadata
    rev_row = await db.execute(
        text("""
            SELECT rev.id, rev.datasource_id, rev.reviewed_at, rev.embedding::text AS emb_raw
            FROM reviews rev
            JOIN datasources ds ON rev.datasource_id = ds.id
            WHERE rev.id = :rid AND ds.user_id = :uid
        """),
        {"rid": review_id, "uid": current_user.id},
    )
    rev = rev_row.one_or_none()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found")

    datasource_id = rev.datasource_id

    # Get dominant feature + signal_type for this review
    sig_row = await db.execute(
        text("""
            SELECT feature, signal_type, COUNT(*) AS cnt
            FROM review_signals
            WHERE review_id = :rid AND feature != 'General'
            GROUP BY feature, signal_type
            ORDER BY cnt DESC LIMIT 1
        """),
        {"rid": review_id},
    )
    sig = sig_row.one_or_none()
    feature = sig.feature if sig else None
    signal_type = sig.signal_type if sig else None

    if not feature:
        return SimilarHistoryResult(
            review_id=review_id, feature=None, signal_type=None,
            total_similar=0, occurrences=[], has_any_reply=False,
            synthesis="Kein Feature-Kontext gefunden — Verlaufsanalyse nicht möglich.",
        )

    # Count total similar signals (same feature + signal_type, excluding this review)
    total_row = await db.execute(
        text("""
            SELECT COUNT(*) FROM review_signals rs
            WHERE rs.datasource_id = :ds AND rs.feature = :feat
              AND rs.signal_type = :stype AND rs.review_id != :rid
        """),
        {"ds": datasource_id, "feat": feature, "stype": signal_type, "rid": review_id},
    )
    total_similar = total_row.scalar() or 0

    # Group by version — count, date, reply info
    groups = await db.execute(
        text("""
            SELECT
                COALESCE(rs.version_hint, rev.version, 'unbekannt') AS version,
                MIN(rev.reviewed_at)::date::text                     AS first_date,
                COUNT(*)                                             AS cnt,
                BOOL_OR(rev.reply_content IS NOT NULL)               AS has_reply,
                (ARRAY_AGG(rev.content ORDER BY rev.reviewed_at DESC))[1] AS example_content,
                (ARRAY_AGG(rev.reply_content ORDER BY rev.reviewed_at DESC)
                    FILTER (WHERE rev.reply_content IS NOT NULL))[1]  AS reply_content,
                (ARRAY_AGG(rev.reply_at::date::text ORDER BY rev.reviewed_at DESC)
                    FILTER (WHERE rev.reply_at IS NOT NULL))[1]        AS reply_at,
                MIN(rev.reviewed_at)                                  AS sort_date
            FROM review_signals rs
            JOIN reviews rev ON rs.review_id = rev.id
            WHERE rs.datasource_id = :ds AND rs.feature = :feat
              AND rs.signal_type = :stype AND rs.review_id != :rid
            GROUP BY COALESCE(rs.version_hint, rev.version, 'unbekannt')
            ORDER BY sort_date DESC
            LIMIT 20
        """),
        {"ds": datasource_id, "feat": feature, "stype": signal_type, "rid": review_id},
    )
    occurrences = [
        SimilarOccurrence(
            version=r.version,
            date=r.first_date,
            count=r.cnt,
            has_reply=r.has_reply or False,
            example_content=r.example_content or "",
            reply_content=r.reply_content,
            reply_at=r.reply_at,
        )
        for r in groups.fetchall()
    ]

    has_any_reply = any(o.has_reply for o in occurrences)

    from app.core.config import settings
    import asyncio
    synthesis = await asyncio.to_thread(
        _groq_similar_synthesis,
        feature,
        signal_type,
        total_similar,
        [o.model_dump() for o in occurrences],
        settings.GROQ_API_KEY,
    )

    return SimilarHistoryResult(
        review_id=review_id,
        feature=feature,
        signal_type=signal_type,
        total_similar=total_similar,
        occurrences=occurrences,
        has_any_reply=has_any_reply,
        synthesis=synthesis,
    )
