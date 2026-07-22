from __future__ import annotations
import uuid
from datetime import datetime, timezone
from app.pipeline.celery_app import celery_app
from app.pipeline.db import SessionLocal
from app.pipeline.ml import (
    clean_text, predict_sentiments, create_embeddings,
    cluster_texts, get_cluster_label, generate_cluster_summary_groq,
)
from app.models.pipeline_job import PipelineJob, JobStatus
from app.models.review import Review
from app.models.cluster import Cluster, ClusterType
from app.models.datasource import DataSource
from app.core.config import settings


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


def _build_clusters(db, datasource_id: str, all_texts: list, indices: list, labels, cluster_type: ClusterType, n_clusters: int):
    for cid in range(n_clusters):
        cluster_indices = [indices[i] for i, lbl in enumerate(labels) if lbl == cid]
        if not cluster_indices:
            continue
        examples = [all_texts[i] for i in cluster_indices[:5]]
        label = get_cluster_label(examples, cluster_type.value)

        summary = None
        if settings.GROQ_API_KEY:
            summary = generate_cluster_summary_groq(label, examples, cluster_type.value, settings.GROQ_API_KEY)
        if not summary:
            summary = f"{len(cluster_indices)} reviews mention this {cluster_type.value}."

        cluster = Cluster(
            id=str(uuid.uuid4()),
            datasource_id=datasource_id,
            type=cluster_type,
            label=label,
            summary=summary,
            mentions=len(cluster_indices),
            examples=examples,
        )
        db.add(cluster)
    db.commit()


def _score_to_sentiment(score) -> str:
    if score is None:
        return None
    if score >= 4.0:
        return "positive"
    if score <= 2.0:
        return "negative"
    return "neutral"


def _run_ml_pipeline(db, job_id: str, datasource_id: str):
    reviews = db.query(Review).filter(Review.datasource_id == datasource_id).all()
    if not reviews:
        _update_job(db, job_id, JobStatus.failed, error="No reviews found for this datasource.")
        return

    texts = [r.content for r in reviews]

    # Step 1: Sentiment — use star rating if available, else ML model
    _update_job(db, job_id, JobStatus.running, "analyzing_sentiment")
    cleaned = [clean_text(t) for t in texts]

    score_based = [_score_to_sentiment(r.score) for r in reviews]
    has_scores = sum(1 for s in score_based if s is not None) > len(reviews) * 0.5

    if has_scores:
        sentiments = [s if s is not None else "neutral" for s in score_based]
    else:
        sentiments = predict_sentiments(cleaned)

    for review, sentiment in zip(reviews, sentiments):
        review.sentiment = sentiment
    db.commit()

    # Step 2: Embeddings
    _update_job(db, job_id, JobStatus.running, "creating_embeddings")
    embeddings = create_embeddings(cleaned)

    # Step 3: Clustering
    _update_job(db, job_id, JobStatus.running, "clustering")
    db.query(Cluster).filter(Cluster.datasource_id == datasource_id).delete()
    db.commit()

    neg_indices = [i for i, s in enumerate(sentiments) if s == "negative"]
    if len(neg_indices) >= 3:
        n = max(3, min(10, len(neg_indices) // 10))
        neg_emb = embeddings[neg_indices]
        labels = cluster_texts(neg_emb, n)
        _build_clusters(db, datasource_id, texts, neg_indices, labels, ClusterType.issue, n)

    pos_indices = [i for i, s in enumerate(sentiments) if s == "positive"]
    if len(pos_indices) >= 3:
        n = max(3, min(10, len(pos_indices) // 10))
        pos_emb = embeddings[pos_indices]
        labels = cluster_texts(pos_emb, n)
        _build_clusters(db, datasource_id, texts, pos_indices, labels, ClusterType.strength, n)

    # Finalize job
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


@celery_app.task(bind=True, name="app.pipeline.tasks.scrape_and_run")
def scrape_and_run(self, job_id: str, datasource_id: str, app_id: str, count: int, lang: str, country: str):
    db = SessionLocal()
    try:
        _update_job(db, job_id, JobStatus.running, "scraping")

        ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
        cutoff = ds.last_synced if ds else None

        # Load existing external_ids for dedup
        existing_ids: set[str] = {
            row.external_id
            for row in db.query(Review.external_id)
            .filter(Review.datasource_id == datasource_id, Review.external_id.isnot(None))
            .all()
        }

        from google_play_scraper import reviews as gplay_reviews, Sort
        result, _ = gplay_reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=count,
        )

        _update_job(db, job_id, JobStatus.running, "saving_reviews")
        for r in result:
            ext_id = r.get("reviewId")

            # Skip reviews already in DB
            if ext_id and ext_id in existing_ids:
                continue

            # Skip reviews older than last_synced (incremental cutoff)
            review_date = r.get("at")
            if cutoff and review_date and review_date <= cutoff:
                continue

            content = (r.get("content") or "").strip()
            if not content:
                continue

            review = Review(
                id=str(uuid.uuid4()),
                datasource_id=datasource_id,
                external_id=ext_id,
                content=content,
                score=r.get("score"),
                version=r.get("reviewCreatedVersion"),
                reviewed_at=review_date,
            )
            db.add(review)

        db.commit()
        _run_ml_pipeline(db, job_id, datasource_id)

    except Exception as exc:
        db.rollback()
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.pipeline.tasks.run_pipeline")
def run_pipeline(self, job_id: str, datasource_id: str):
    db = SessionLocal()
    try:
        _update_job(db, job_id, JobStatus.running, "loading_reviews")
        _run_ml_pipeline(db, job_id, datasource_id)
    except Exception as exc:
        db.rollback()
        _update_job(db, job_id, JobStatus.failed, error=str(exc))
        raise
    finally:
        db.close()
