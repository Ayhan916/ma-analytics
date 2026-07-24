from __future__ import annotations
import uuid
import time
import structlog
from datetime import datetime, timezone
from app.pipeline.celery_app import celery_app
from app.pipeline.db import SessionLocal
from app.pipeline.ml import (
    clean_text, detect_language, predict_sentiments, create_embeddings,
    cluster_texts, get_cluster_label, generate_cluster_summary,
)
from app.pipeline.intelligence import (
    extract_aspects_from_reviews,
    normalize_feature,
    classify_signal_type,
    derive_severity,
    extract_version_hint,
    synthesize_feature_narrative,
    _RESOLVED_RE as _RESOLVED_MARKER,
)
from app.models.pipeline_job import PipelineJob, JobStatus
from app.models.review import Review
from app.models.cluster import Cluster, ClusterReview, ClusterType
from app.models.datasource import DataSource
from app.models.intelligence import ReviewAspect, ReviewSentence, ReviewSignal, FeatureNarrative
from app.core.config import settings

log = structlog.get_logger(__name__)

# Minimum reviews per cluster to be meaningful
MIN_CLUSTER_SIZE = 10

# Maximum reviews to pass to LLM summary as context
SUMMARY_EXAMPLE_LIMIT = 15

# Google Play scraping rate: max reviews per request page
GPLAY_PAGE_SIZE = 200


def _update_job(db, job_id: str, status: JobStatus, progress: str = None, error: str = None):
    job = db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    if not job:
        return
    job.status = status
    if progress is not None:
        job.progress = progress
    if error is not None:
        job.error = error
    now = datetime.now(timezone.utc)
    if status == JobStatus.running and job.started_at is None:
        job.started_at = now
    if status in (JobStatus.done, JobStatus.failed):
        job.finished_at = now
    db.commit()


def _score_to_sentiment(score: float) -> str | None:
    if score is None:
        return None
    if score >= 4.0:
        return "positive"
    if score <= 2.0:
        return "negative"
    return None  # 3-star is ambiguous — let ML model decide


def _build_clusters(
    db,
    datasource_id: str,
    all_reviews: list[Review],
    indices: list[int],
    labels,
    cluster_type: ClusterType,
    dominant_language: str,
):
    # Iterate unique non-negative cluster IDs (HDBSCAN assigns -1 to noise points)
    for cid in sorted({int(l) for l in labels if int(l) >= 0}):
        cluster_indices = [indices[i] for i, lbl in enumerate(labels) if lbl == cid]
        if len(cluster_indices) < 2:
            continue

        member_reviews = [all_reviews[i] for i in cluster_indices]
        example_reviews = member_reviews[:SUMMARY_EXAMPLE_LIMIT]
        example_texts = [r.content for r in example_reviews]

        label = get_cluster_label(
            [r.content for r in member_reviews],
            cluster_type.value,
            dominant_language,
            groq_api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
        )

        summary = None
        if settings.GROQ_API_KEY:
            summary = generate_cluster_summary(
                label, example_texts, cluster_type.value,
                settings.GROQ_API_KEY, dominant_language, settings.GROQ_MODEL,
            )
        if not summary:
            summary = f"{len(cluster_indices)} reviews mention this {cluster_type.value}."

        cluster = Cluster(
            id=str(uuid.uuid4()),
            datasource_id=datasource_id,
            type=cluster_type,
            label=label,
            summary=summary,
            mentions=len(cluster_indices),
        )
        db.add(cluster)
        db.flush()  # get cluster.id before adding memberships

        for i, review in enumerate(member_reviews):
            db.add(ClusterReview(
                id=str(uuid.uuid4()),
                cluster_id=cluster.id,
                review_id=review.id,
                is_example=(i < 5),
            ))

    db.commit()


def _infer_versions(db, datasource_id: str) -> int:
    """Assign versions to reviews that have a date but no reviewCreatedVersion.

    Builds a timeline from versioned reviews (version_source='provided'), then
    date-interpolates unversioned reviews into that timeline.
    Returns the number of reviews updated.
    """
    from sqlalchemy import text

    # Build version → earliest_date timeline from 'provided' reviews
    rows = db.execute(
        text("""
            SELECT version, MIN(reviewed_at) AS first_seen
            FROM reviews
            WHERE datasource_id = :ds_id
              AND version IS NOT NULL
              AND reviewed_at IS NOT NULL
            GROUP BY version
            ORDER BY first_seen
        """),
        {"ds_id": datasource_id},
    ).fetchall()

    if not rows:
        return 0

    # timeline: [(version, start_date, end_date), ...]
    # Each version is active from its first_seen until the next version's first_seen
    timeline = []
    for i, row in enumerate(rows):
        start = row.first_seen
        end = rows[i + 1].first_seen if i + 1 < len(rows) else None
        timeline.append((row.version, start, end))

    # Find reviews with date but no version (version_source still NULL)
    unversioned = db.execute(
        text("""
            SELECT id, reviewed_at FROM reviews
            WHERE datasource_id = :ds_id
              AND version IS NULL
              AND reviewed_at IS NOT NULL
              AND (version_source IS NULL OR version_source != 'unknown')
        """),
        {"ds_id": datasource_id},
    ).fetchall()

    updated = 0
    for review in unversioned:
        dt = review.reviewed_at
        assigned = None
        for version, start, end in timeline:
            if end is None:
                if dt >= start:
                    assigned = version
                    break
            else:
                if start <= dt < end:
                    assigned = version
                    break
        # If before all known versions, assign to earliest
        if assigned is None and dt < timeline[0][1]:
            assigned = timeline[0][0]

        if assigned:
            db.execute(
                text("UPDATE reviews SET version = :v, version_source = 'inferred' WHERE id = :id"),
                {"v": assigned, "id": review.id},
            )
            updated += 1
        else:
            db.execute(
                text("UPDATE reviews SET version_source = 'unknown' WHERE id = :id"),
                {"id": review.id},
            )

    db.commit()
    return updated


def _run_intelligence_pipeline(db, job_id: str, datasource_id: str):
    """ABSA-First Intelligence Pipeline.

    Full review text → pyABSA → feature normalization → rule-based signals → Groq narratives.
    """
    log.info("absa_pipeline_start", datasource_id=datasource_id)

    reviews = db.query(Review).filter(Review.datasource_id == datasource_id).all()
    if not reviews:
        log.warning("intelligence_no_reviews", datasource_id=datasource_id)
        return

    # --- Step 1: Clear old intelligence data ---
    _update_job(db, job_id, JobStatus.running, "intelligence_clearing_old_data")
    db.query(FeatureNarrative).filter(FeatureNarrative.datasource_id == datasource_id).delete()
    db.query(ReviewSignal).filter(ReviewSignal.datasource_id == datasource_id).delete()
    db.query(ReviewAspect).filter(ReviewAspect.datasource_id == datasource_id).delete()
    db.query(ReviewSentence).filter(ReviewSentence.datasource_id == datasource_id).delete()
    db.commit()

    # Snapshot review metadata before any DB ops
    review_meta = {r.id: {"score": r.score, "version": r.version, "content": r.content or ""} for r in reviews}

    # --- Step 2: ABSA aspect extraction ---
    _update_job(db, job_id, JobStatus.running, "intelligence_absa_extracting")
    log.info("absa_start", n_reviews=len(reviews))

    all_review_aspects = extract_aspects_from_reviews(reviews, batch_size=32)

    total_aspects = 0
    for review, aspects in zip(reviews, all_review_aspects):
        meta = review_meta[review.id]
        for asp in aspects:
            feature = asp.get("feature_override") or normalize_feature(asp["aspect_term"] or "")
            sentiment = asp["sentiment"]
            signal_type = classify_signal_type(sentiment, meta["content"])
            severity = derive_severity(sentiment, signal_type, meta["score"], asp["confidence"])
            version_hint = extract_version_hint(meta["content"]) or meta["version"]

            aspect_rec = ReviewAspect(
                id=str(uuid.uuid4()),
                review_id=review.id,
                datasource_id=datasource_id,
                aspect_term=asp["aspect_term"],
                feature=feature,
                sentiment=sentiment.lower(),
                confidence=asp["confidence"],
                span_text=asp["span_text"],
                absa_source=asp["absa_source"],
            )
            db.add(aspect_rec)
            db.flush()  # get aspect_rec.id

            db.add(ReviewSignal(
                id=str(uuid.uuid4()),
                aspect_id=aspect_rec.id,
                sentence_id=None,
                review_id=review.id,
                datasource_id=datasource_id,
                feature=feature,
                signal_type=signal_type,
                severity=severity,
                is_resolved=bool(_RESOLVED_MARKER.search(meta["content"])) and sentiment.lower() == "positive",
                version_hint=version_hint,
            ))
            total_aspects += 1

        # Commit every 200 reviews for incremental persistence
        if total_aspects > 0 and total_aspects % 200 == 0:
            db.commit()
            pct = int(100 * reviews.index(review) / len(reviews))
            _update_job(db, job_id, JobStatus.running, f"intelligence_signals_{pct}pct")
            log.info("absa_progress", aspects=total_aspects, review_idx=reviews.index(review))

    db.commit()
    log.info("absa_done", total_aspects=total_aspects)

    # --- Step 3: Narrative synthesis ---
    _run_narrative_synthesis(db, datasource_id, job_id=job_id)


def _run_narrative_synthesis(db, datasource_id: str, job_id: str | None = None):
    """Re-generate Groq narratives for all features of a datasource."""
    from sqlalchemy import text as sql_text

    if not settings.GROQ_API_KEY:
        log.warning("intelligence_no_groq_key_skipping_narratives")
        return

    if job_id:
        _update_job(db, job_id, JobStatus.running, "intelligence_synthesizing_narratives")

    feature_rows = db.execute(
        sql_text("""
            SELECT feature, COUNT(*) AS mention_count, AVG(severity) AS avg_severity
            FROM review_signals
            WHERE datasource_id = :ds_id
            GROUP BY feature
            HAVING COUNT(*) >= 5
            ORDER BY COUNT(*) DESC
        """),
        {"ds_id": datasource_id},
    ).fetchall()

    for feat_row in feature_rows:
        feature = feat_row.feature

        signal_data = db.execute(
            sql_text("""
                SELECT rs.signal_type, rs.severity, rs.is_resolved, rs.version_hint,
                       asp.span_text AS text, rev.version, rev.reviewed_at,
                       (rev.reply_content IS NOT NULL AND rev.reply_content <> '') AS has_reply
                FROM review_signals rs
                LEFT JOIN review_aspects asp ON rs.aspect_id = asp.id
                JOIN reviews rev ON rs.review_id = rev.id
                WHERE rs.datasource_id = :ds_id AND rs.feature = :feature
                ORDER BY rev.reviewed_at DESC NULLS LAST
                LIMIT 200
            """),
            {"ds_id": datasource_id, "feature": feature},
        ).fetchall()

        rows_for_llm = [
            {
                "text": r.text or feature,
                "signal_type": r.signal_type,
                "severity": r.severity,
                "is_resolved": r.is_resolved,
                "version": r.version_hint or r.version,
                "reviewed_at": str(r.reviewed_at)[:10] if r.reviewed_at else None,
                "has_reply": bool(r.has_reply),
            }
            for r in signal_data
        ]

        narrative = synthesize_feature_narrative(
            feature=feature,
            signal_rows=rows_for_llm,
            groq_api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
        )
        if not narrative:
            narrative = f"{feat_row.mention_count} Nutzermeldungen zu {feature}."

        existing = db.query(FeatureNarrative).filter(
            FeatureNarrative.datasource_id == datasource_id,
            FeatureNarrative.feature == feature,
        ).first()
        if existing:
            existing.narrative = narrative
            existing.mention_count = feat_row.mention_count
            existing.avg_severity = float(feat_row.avg_severity) if feat_row.avg_severity else None
            existing.generated_at = datetime.now(timezone.utc)
        else:
            db.add(FeatureNarrative(
                id=str(uuid.uuid4()),
                datasource_id=datasource_id,
                feature=feature,
                narrative=narrative,
                mention_count=feat_row.mention_count,
                avg_severity=float(feat_row.avg_severity) if feat_row.avg_severity else None,
                signal_counts=None,
            ))

    db.commit()
    log.info("intelligence_synthesis_done", features=len(feature_rows), datasource_id=datasource_id)


def _run_ml_pipeline(db, job_id: str, datasource_id: str):
    reviews = db.query(Review).filter(Review.datasource_id == datasource_id).all()
    if not reviews:
        _update_job(db, job_id, JobStatus.failed, error="No reviews found for this datasource.")
        return

    log.info("pipeline_start", datasource_id=datasource_id, review_count=len(reviews))
    texts = [r.content for r in reviews]

    # --- Step 1: Language Detection ---
    _update_job(db, job_id, JobStatus.running, "detecting_language")
    sample_text = " ".join(texts[:20])
    dominant_language = detect_language(sample_text)
    log.info("language_detected", language=dominant_language)

    # Detect per-review language for reviews without one
    for review in reviews:
        if not review.language:
            review.language = detect_language(review.content)
    db.commit()

    # --- Step 2: Sentiment ---
    _update_job(db, job_id, JobStatus.running, "analyzing_sentiment")
    cleaned = [clean_text(t) for t in texts]

    # Score-based mapping where available, ML for the rest (including ambiguous 3-star)
    score_sentiments = [_score_to_sentiment(r.score) for r in reviews]
    ml_indices = [i for i, s in enumerate(score_sentiments) if s is None]

    sentiments = list(score_sentiments)
    if ml_indices:
        ml_texts = [cleaned[i] for i in ml_indices]
        ml_results = predict_sentiments(ml_texts)
        for idx, ml_sent in zip(ml_indices, ml_results):
            sentiments[idx] = ml_sent

    for review, sentiment in zip(reviews, sentiments):
        review.sentiment = sentiment or "neutral"
    db.commit()
    log.info("sentiment_done", pos=sentiments.count("positive"), neg=sentiments.count("negative"), neu=sentiments.count("neutral"))

    # --- Step 3: Embeddings ---
    _update_job(db, job_id, JobStatus.running, "creating_embeddings")

    # Only recompute embeddings for reviews that don't have one yet
    needs_embedding = [i for i, r in enumerate(reviews) if r.embedding is None]
    if needs_embedding:
        texts_to_embed = [cleaned[i] for i in needs_embedding]
        new_embeddings = create_embeddings(texts_to_embed)
        for list_pos, review_idx in enumerate(needs_embedding):
            reviews[review_idx].embedding = new_embeddings[list_pos].tolist()
        db.commit()
        log.info("embeddings_created", count=len(needs_embedding))
    else:
        log.info("embeddings_cached", count=len(reviews))

    # Build full embedding array for clustering
    import numpy as np
    all_embeddings = np.array([r.embedding for r in reviews], dtype=np.float32)

    # --- Step 4: Clustering ---
    _update_job(db, job_id, JobStatus.running, "clustering")

    # Remove existing clusters (fresh analysis)
    existing = db.query(Cluster).filter(Cluster.datasource_id == datasource_id).all()
    for c in existing:
        db.delete(c)
    db.commit()

    neg_indices = [i for i, s in enumerate(sentiments) if s == "negative"]
    if len(neg_indices) >= MIN_CLUSTER_SIZE:
        neg_emb = all_embeddings[neg_indices]
        labels = cluster_texts(neg_emb, min_cluster_size=MIN_CLUSTER_SIZE)
        n = len({int(l) for l in labels if int(l) >= 0})
        _build_clusters(db, datasource_id, reviews, neg_indices, labels, ClusterType.issue, dominant_language)
        log.info("issue_clusters_built", n_clusters=n, reviews=len(neg_indices))

    pos_indices = [i for i, s in enumerate(sentiments) if s == "positive"]
    if len(pos_indices) >= MIN_CLUSTER_SIZE:
        pos_emb = all_embeddings[pos_indices]
        labels = cluster_texts(pos_emb, min_cluster_size=MIN_CLUSTER_SIZE)
        n = len({int(l) for l in labels if int(l) >= 0})
        _build_clusters(db, datasource_id, reviews, pos_indices, labels, ClusterType.strength, dominant_language)
        log.info("strength_clusters_built", n_clusters=n, reviews=len(pos_indices))

    # --- Step 5: Zero-Loss Intelligence Pipeline ---
    _run_intelligence_pipeline(db, job_id, datasource_id)

    # --- Finalize ---
    job = db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
    if job:
        job.status = JobStatus.done
        job.progress = "done"
        job.review_count = len(reviews)
        job.finished_at = datetime.now(timezone.utc)

    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if ds:
        ds.last_synced = datetime.now(timezone.utc)

    db.commit()
    log.info("pipeline_done", datasource_id=datasource_id, review_count=len(reviews))


@celery_app.task(
    bind=True,
    name="app.pipeline.tasks.scrape_and_run",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
)
def scrape_and_run(self, job_id: str, datasource_id: str, app_id: str, count: int, lang: str, country: str):
    db = SessionLocal()
    try:
        _update_job(db, job_id, JobStatus.running, "scraping")

        ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
        if not ds:
            _update_job(db, job_id, JobStatus.failed, error="DataSource not found.")
            return

        cutoff = ds.last_synced

        # Load existing external_ids for dedup
        existing_ids: set[str] = {
            row.external_id
            for row in db.query(Review.external_id)
            .filter(Review.datasource_id == datasource_id, Review.external_id.isnot(None))
            .all()
        }

        from google_play_scraper import reviews as gplay_reviews, Sort

        new_reviews: list[Review] = []
        continuation_token = None
        fetched = 0
        stop_early = False

        log.info("scraping_start", app_id=app_id, target=count, lang=lang, country=country)

        while fetched < count and not stop_early:
            batch_size = min(GPLAY_PAGE_SIZE, count - fetched)

            kwargs = dict(
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=batch_size,
            )
            if continuation_token:
                kwargs["continuation_token"] = continuation_token

            result, continuation_token = gplay_reviews(app_id, **kwargs)

            if not result:
                log.info("scraping_no_more_results", fetched=fetched)
                break

            for r in result:
                ext_id = r.get("reviewId")
                review_date = r.get("at")
                reply_text = (r.get("replyContent") or "").strip() or None
                reply_date = r.get("repliedAt")

                if ext_id and ext_id in existing_ids:
                    # Update developer reply for already-scraped reviews
                    if reply_text:
                        db.execute(
                            __import__("sqlalchemy").text(
                                "UPDATE reviews SET reply_content = :rc, reply_at = :ra "
                                "WHERE datasource_id = :ds AND external_id = :eid "
                                "AND (reply_content IS DISTINCT FROM :rc)"
                            ),
                            {"rc": reply_text, "ra": reply_date, "ds": datasource_id, "eid": ext_id},
                        )
                    continue

                # Cutoff: stop when we reach reviews older than last sync
                if cutoff and review_date and review_date <= cutoff:
                    stop_early = True
                    break

                content = (r.get("content") or "").strip()
                if not content:
                    continue

                raw_version = r.get("reviewCreatedVersion")
                new_reviews.append(Review(
                    id=str(uuid.uuid4()),
                    datasource_id=datasource_id,
                    external_id=ext_id,
                    content=content,
                    score=r.get("score"),
                    version=raw_version or None,
                    version_source="provided" if raw_version else None,
                    reviewed_at=review_date,
                    reply_content=reply_text,
                    reply_at=reply_date,
                ))
                if ext_id:
                    existing_ids.add(ext_id)

            fetched += len(result)

            if not continuation_token:
                break

            # Respect Google Play rate limits — pause between pages
            time.sleep(1.5)

        if not new_reviews and not existing_ids:
            _update_job(db, job_id, JobStatus.failed, error=f"No reviews found for app '{app_id}'. Check the app ID.")
            return

        _update_job(db, job_id, JobStatus.running, f"saving_{len(new_reviews)}_reviews")
        for review in new_reviews:
            db.add(review)
        db.commit()
        log.info("scraping_done", new=len(new_reviews), total_existing=len(existing_ids))

        # Infer versions for reviews that have a date but no reviewCreatedVersion
        _update_job(db, job_id, JobStatus.running, "inferring_versions")
        inferred = _infer_versions(db, datasource_id)
        log.info("version_inference_done", inferred=inferred)

        _run_ml_pipeline(db, job_id, datasource_id)

    except Exception as exc:
        db.rollback()
        log.exception("scrape_task_failed", job_id=job_id, error=str(exc))
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise


@celery_app.task(
    bind=True,
    name="app.pipeline.tasks.backfill_replies",
    max_retries=2,
    default_retry_delay=60,
)
def backfill_replies(self, job_id: str, datasource_id: str, app_id: str, lang: str, country: str):
    """Re-scrape Google Play to fill reply_content/reply_at for existing reviews."""
    db = SessionLocal()
    try:
        _update_job(db, job_id, JobStatus.running, "backfill_replies_start")

        existing: dict[str, str] = {
            row.external_id: row.id
            for row in db.query(Review.external_id, Review.id)
            .filter(Review.datasource_id == datasource_id, Review.external_id.isnot(None))
            .all()
        }
        target_ids = set(existing.keys())
        processed = 0
        updated = 0
        continuation_token = None

        from google_play_scraper import reviews as gplay_reviews, Sort
        import sqlalchemy

        log.info("backfill_replies_start", datasource_id=datasource_id, total=len(target_ids))

        while target_ids:
            result, continuation_token = gplay_reviews(
                app_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=200,
                **({'continuation_token': continuation_token} if continuation_token else {}),
            )
            if not result:
                break

            for r in result:
                ext_id = r.get("reviewId")
                if not ext_id:
                    continue
                processed += 1
                reply_text = (r.get("replyContent") or "").strip() or None
                reply_date = r.get("repliedAt")
                if ext_id in target_ids:
                    target_ids.discard(ext_id)
                    if reply_text:
                        db.execute(
                            sqlalchemy.text(
                                "UPDATE reviews SET reply_content = :rc, reply_at = :ra "
                                "WHERE datasource_id = :ds AND external_id = :eid "
                                "AND (reply_content IS DISTINCT FROM :rc)"
                            ),
                            {"rc": reply_text, "ra": reply_date, "ds": datasource_id, "eid": ext_id},
                        )
                        updated += 1

            db.commit()
            log.info("backfill_progress", processed=processed, updated=updated, remaining=len(target_ids))
            _update_job(db, job_id, JobStatus.running, f"processed_{processed}_updated_{updated}")

            if not continuation_token:
                break
            time.sleep(1.0)

        _update_job(db, job_id, JobStatus.done, f"backfill_done_updated_{updated}")
        log.info("backfill_replies_done", processed=processed, updated=updated)

    except Exception as exc:
        db.rollback()
        log.exception("backfill_replies_failed", job_id=job_id, error=str(exc))
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.pipeline.tasks.resynthesize_narratives",
    max_retries=2,
    default_retry_delay=30,
)
def resynthesize_narratives(self, job_id: str, datasource_id: str):
    """Re-generate all Groq narratives without re-running ABSA."""
    db = SessionLocal()
    try:
        _update_job(db, job_id, JobStatus.running, "synthesizing_narratives")
        _run_narrative_synthesis(db, datasource_id, job_id=job_id)
        _update_job(db, job_id, JobStatus.done, "narratives_done")
    except Exception as exc:
        db.rollback()
        log.exception("resynthesize_failed", job_id=job_id, error=str(exc))
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.pipeline.tasks.run_pipeline",
    max_retries=2,
    default_retry_delay=30,
)
def run_pipeline(self, job_id: str, datasource_id: str):
    db = SessionLocal()
    try:
        _update_job(db, job_id, JobStatus.running, "loading_reviews")
        _run_ml_pipeline(db, job_id, datasource_id)
    except Exception as exc:
        db.rollback()
        log.exception("pipeline_task_failed", job_id=job_id, error=str(exc))
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise
    finally:
        db.close()
