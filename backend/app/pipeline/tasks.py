from __future__ import annotations
import uuid
import time
import logging
from datetime import datetime, timezone
from app.pipeline.celery_app import celery_app
from app.pipeline.db import SessionLocal
from app.pipeline.ml import (
    clean_text, detect_language, predict_sentiments, create_embeddings,
    cluster_texts, get_cluster_label, generate_cluster_summary,
)
from app.models.pipeline_job import PipelineJob, JobStatus
from app.models.review import Review
from app.models.cluster import Cluster, ClusterReview, ClusterType
from app.models.datasource import DataSource
from app.core.config import settings

log = logging.getLogger(__name__)

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
    if status in (JobStatus.done, JobStatus.failed):
        job.finished_at = datetime.now(timezone.utc)
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

                if ext_id and ext_id in existing_ids:
                    continue

                # Cutoff: stop when we reach reviews older than last sync
                if cutoff and review_date and review_date <= cutoff:
                    stop_early = True
                    break

                content = (r.get("content") or "").strip()
                if not content:
                    continue

                new_reviews.append(Review(
                    id=str(uuid.uuid4()),
                    datasource_id=datasource_id,
                    external_id=ext_id,
                    content=content,
                    score=r.get("score"),
                    version=r.get("reviewCreatedVersion"),
                    reviewed_at=review_date,
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

        _run_ml_pipeline(db, job_id, datasource_id)

    except Exception as exc:
        db.rollback()
        log.exception("scrape_task_failed", job_id=job_id, error=str(exc))
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise


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
