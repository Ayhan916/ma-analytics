from __future__ import annotations
import re
import logging
import numpy as np
from typing import Optional

log = logging.getLogger(__name__)

# Lazy-loaded singletons — only loaded when first used in the worker
_sentiment_pipeline = None
_embedding_model = None
_embedding_model_loaded = False   # True after first load attempt (even if None)
_reranker_model = None
_reranker_model_loaded = False    # True after first load attempt (even if None)

MULTILINGUAL_SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
MULTILINGUAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
EMBEDDING_DIM = 384

GERMAN_STOP_WORDS = {
    "aber", "alle", "allem", "allen", "aller", "alles", "als", "also", "am",
    "an", "ander", "andere", "anderem", "anderen", "anderer", "anderes",
    "anderm", "andern", "anderr", "anders", "auch", "auf", "aus", "bei",
    "bin", "bis", "bist", "da", "damit", "dann", "das", "dasselbe", "dazu",
    "daß", "dein", "deine", "deinem", "deinen", "deiner", "deines", "dem",
    "demselben", "den", "denn", "denselben", "der", "derer", "derselbe",
    "derselben", "des", "desselben", "dessen", "dich", "die", "dies",
    "diese", "diesem", "diesen", "dieser", "dieses", "dir", "doch", "dort",
    "du", "durch", "ein", "eine", "einem", "einen", "einer", "eines",
    "einig", "einige", "einigem", "einigen", "einiger", "einiges", "einmal",
    "er", "es", "etwas", "euch", "für", "gegen", "gewesen", "hab", "habe",
    "haben", "hat", "hatte", "hatten", "hier", "hin", "hinter", "ich",
    "ihm", "ihn", "ihnen", "ihr", "ihre", "ihrem", "ihren", "ihrer",
    "ihres", "im", "in", "indem", "ins", "ist", "jede", "jedem", "jeden",
    "jeder", "jedes", "jetzt", "kann", "kein", "keine", "keinem", "keinen",
    "keiner", "keines", "können", "könnte", "machen", "man", "manche",
    "manchem", "manchen", "mancher", "manches", "mein", "meine", "meinem",
    "meinen", "meiner", "meines", "mich", "mir", "mit", "muss", "musste",
    "nach", "nicht", "nichts", "noch", "nun", "nur", "ob", "oder", "ohne",
    "sehr", "sein", "seine", "seinem", "seinen", "seiner", "seines", "selbst",
    "sich", "sie", "sind", "so", "solche", "solchem", "solchen", "solcher",
    "solches", "soll", "sollte", "sondern", "sonst", "über", "um", "und",
    "uns", "unse", "unsem", "unsen", "unser", "unses", "unter", "viel",
    "vom", "von", "vor", "war", "waren", "warst", "was", "weg", "weil",
    "weiter", "welche", "welchem", "welchen", "welcher", "welches", "wenn",
    "wer", "werden", "wie", "wieder", "will", "wir", "wird", "wo", "wollt",
    "wollte", "wollten", "würde", "würden", "zu", "zum", "zur", "zwar",
    "zwischen",
}

ENGLISH_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "get", "got", "had", "has", "have", "having", "he", "her",
    "here", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "just", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
    "out", "own", "re", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "us",
    "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "with", "would", "you", "your",
}

COMBINED_STOP_WORDS = GERMAN_STOP_WORDS | ENGLISH_STOP_WORDS


def detect_language(text: str) -> str:
    """Detect text language. Returns ISO 639-1 code or 'unknown'."""
    try:
        from langdetect import detect, LangDetectException
        return detect(text[:500])
    except Exception:
        return "unknown"


def clean_text(text: str) -> str:
    """
    Clean text for ML input while preserving semantic signals:
    - URLs removed (noise)
    - Emojis converted to text tags (sentiment signal)
    - Apostrophes preserved (don't → don't, not don t)
    - Excessive whitespace normalized
    - Lowercased
    """
    # Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # Normalize unicode apostrophes to ASCII
    text = text.replace("’", "'").replace("‘", "'")

    # Convert common emojis to text tags that the model can process
    emoji_map = {
        "😊": " positive ", "😀": " positive ", "😃": " positive ",
        "😍": " love ", "👍": " good ", "❤": " love ",
        "😠": " negative ", "😡": " angry ", "😤": " frustrated ",
        "😢": " sad ", "😞": " disappointed ", "👎": " bad ",
        "💥": " crash ", "❌": " error ", "⚠": " warning ",
        "🔥": " fire ", "✅": " ok ", "⭐": " star ",
    }
    for emoji, tag in emoji_map.items():
        text = text.replace(emoji, tag)

    # Remove remaining non-word characters EXCEPT apostrophes (preserve contractions)
    text = re.sub(r"[^\w\s']", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text.lower()


def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline
        log.info("loading_sentiment_model", model=MULTILINGUAL_SENTIMENT_MODEL)
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model=MULTILINGUAL_SENTIMENT_MODEL,
            truncation=True,
            max_length=512,
            top_k=1,
        )
        log.info("sentiment_model_loaded")
    return _sentiment_pipeline


def get_embedding_model():
    """Return the embedding model, or None if sentence_transformers is not installed."""
    global _embedding_model, _embedding_model_loaded
    if _embedding_model is not None:
        return _embedding_model
    if not _embedding_model_loaded:
        _embedding_model_loaded = True
        try:
            from sentence_transformers import SentenceTransformer
            log.info("loading_embedding_model %s", MULTILINGUAL_EMBEDDING_MODEL)
            _embedding_model = SentenceTransformer(MULTILINGUAL_EMBEDDING_MODEL)
            log.info("embedding_model_loaded")
        except ImportError:
            log.warning("sentence_transformers_not_installed — embedding model unavailable")
    return _embedding_model


def get_reranker_model():
    """Return the cross-encoder reranker, or None if sentence_transformers is not installed."""
    global _reranker_model, _reranker_model_loaded
    if _reranker_model is not None:
        return _reranker_model
    if not _reranker_model_loaded:
        _reranker_model_loaded = True
        try:
            from sentence_transformers import CrossEncoder
            log.info("loading_reranker_model %s", RERANKER_MODEL)
            _reranker_model = CrossEncoder(RERANKER_MODEL, max_length=512)
            log.info("reranker_model_loaded")
        except ImportError:
            log.warning("sentence_transformers_not_installed — reranker model unavailable")
    return _reranker_model


def rerank(query: str, texts: list[str]) -> list[float]:
    """Score each (query, text) pair with the cross-encoder and return raw scores.

    Returns empty list if the reranker model is not available (API-only image).
    Higher score = more relevant. Scores are not normalised — use them only
    for sorting, not for display as probabilities.
    """
    if not texts:
        return []
    model = get_reranker_model()
    if model is None:
        return []
    pairs = [[query, t] for t in texts]
    scores = model.predict(pairs)
    return scores.tolist()


def predict_sentiments(texts: list[str], batch_size: int = 32) -> list[str]:
    """
    Batch sentiment prediction. Processes `batch_size` texts at once
    instead of one-by-one — 10-20x faster for large datasets.
    """
    if not texts:
        return []

    pipe = get_sentiment_pipeline()
    results = []

    try:
        outputs = pipe(texts, batch_size=batch_size, truncation=True)
        for out in outputs:
            label = out[0]["label"].lower() if isinstance(out, list) else out["label"].lower()
            if "positive" in label:
                results.append("positive")
            elif "negative" in label:
                results.append("negative")
            else:
                results.append("neutral")
    except Exception:
        log.exception("sentiment_batch_failed", count=len(texts))
        # Per-text fallback so partial failures don't kill the whole batch
        results = []
        for text in texts:
            try:
                out = pipe([text], truncation=True)[0]
                label = out[0]["label"].lower() if isinstance(out, list) else out["label"].lower()
                if "positive" in label:
                    results.append("positive")
                elif "negative" in label:
                    results.append("negative")
                else:
                    results.append("neutral")
            except Exception:
                log.warning("sentiment_single_failed", text_preview=text[:50])
                results.append("neutral")

    return results


def create_embeddings(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """
    Create sentence embeddings in batches to control memory usage.
    Returns float32 array of shape (len(texts), EMBEDDING_DIM).
    """
    model = get_embedding_model()
    return model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )


def cluster_texts(embeddings: np.ndarray, min_cluster_size: int = 10) -> np.ndarray:
    """Cluster embeddings with HDBSCAN. Noise points receive label -1.

    Automatically determines the number of clusters — no k required.
    Falls back to KMeans(k=2) when HDBSCAN finds fewer than 2 clusters on
    datasets large enough to contain at least two clusters (≥ 2 * min_cluster_size).
    """
    from sklearn.cluster import HDBSCAN

    hdb = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=max(1, min_cluster_size // 2),
        metric="euclidean",
        cluster_selection_method="eom",
    )
    labels = hdb.fit_predict(embeddings)

    n_found = len({l for l in labels if l >= 0})
    if n_found < 2 and len(embeddings) >= min_cluster_size * 2:
        log.warning("hdbscan_no_clusters_fallback_kmeans n_samples=%d", len(embeddings))
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=2, random_state=42, n_init=10)
        labels = km.fit_predict(embeddings)

    return labels


def optimal_cluster_count(embeddings: np.ndarray, min_k: int = 2, max_k: int = 15) -> int:
    """
    Use silhouette score to find the best number of clusters.
    Falls back to a simple heuristic if fewer than 2*min_k samples.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n = len(embeddings)
    if n < min_k * 2:
        return min(min_k, n)

    actual_max = min(max_k, n // 2)
    if actual_max < min_k:
        return min_k

    best_k = min_k
    best_score = -1.0

    for k in range(min_k, actual_max + 1):
        try:
            km = KMeans(n_clusters=k, random_state=42, n_init=5)
            labels = km.fit_predict(embeddings)
            score = silhouette_score(embeddings, labels, sample_size=min(500, n))
            if score > best_score:
                best_score = score
                best_k = k
        except Exception:
            break

    return best_k


# Words that are too generic to be meaningful cluster labels on their own.
# These complement COMBINED_STOP_WORDS for the label-quality check.
GENERIC_APP_TERMS = {
    "app", "application", "apps", "update", "updates", "version", "versions",
    "good", "great", "bad", "nice", "ok", "okay", "fine", "best", "worst",
    "use", "used", "using", "user", "users", "like", "love", "hate", "need",
    "work", "works", "working", "make", "makes", "get", "gets", "go", "goes",
    "time", "times", "day", "days", "week", "month", "year", "ago",
    "please", "thank", "thanks", "help", "please", "fix", "fixed",
    "problem", "issue", "issues", "error", "errors", "bug", "bugs",
    "star", "stars", "rating", "review", "reviews", "feedback",
    "gut", "schlecht", "toll", "super", "prima", "leider", "bitte",
    "danke", "hilfe", "fehler", "problem", "probleme", "version", "update",
    "app", "nutzer", "nutzen", "benutzen", "funktioniert", "funktionieren",
}


def is_label_meaningful(label: str) -> bool:
    """Return True if the label carries specific, non-generic information.

    A label is rejected when:
    - It is the fallback string (ends with "Cluster")
    - All unique terms are in GENERIC_APP_TERMS
    - All terms are identical (e.g. TF-IDF picked the same word 3 times)
    """
    if label.endswith("Cluster"):
        return False

    # Split on separator and strip whitespace
    terms = [t.strip().lower() for t in label.split("/") if t.strip()]
    if not terms:
        return False

    # Reject if we have multiple terms but they are all identical (e.g. "app / app / app")
    if len(terms) > 1 and len(set(terms)) == 1:
        return False

    # Reject if every individual word in every term is generic
    all_generic = all(
        all(word in GENERIC_APP_TERMS or word in COMBINED_STOP_WORDS for word in term.split())
        for term in terms
    )
    return not all_generic


def _generate_label_with_llm(
    example_texts: list[str],
    cluster_type: str,
    language: str,
    groq_api_key: str,
    model: str = "llama3-70b-8192",
) -> Optional[str]:
    """Ask the LLM for a concise 2-4 word label when TF-IDF fails."""
    lang_instruction = (
        "Antworte auf Deutsch." if language == "de"
        else "Respond in English." if language == "en"
        else "Respond in the same language as the reviews."
    )
    sample = "\n".join(f"- {t[:150]}" for t in example_texts[:6])
    prompt = (
        f"You are labeling a cluster of app reviews (type: {cluster_type}).\n"
        f"Reviews:\n{sample}\n\n"
        f"Give a concise 2-4 word label that captures the SPECIFIC topic "
        f"(not just 'app issue' or 'good feature'). "
        f"Reply with ONLY the label, no explanation. {lang_instruction}"
    )
    try:
        from groq import Groq
        client = Groq(api_key=groq_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        # Truncate to 60 chars max to avoid runaway responses
        return raw[:60] if raw else None
    except Exception:
        log.warning("llm_label_fallback_failed", cluster_type=cluster_type)
        return None


def get_cluster_label(
    texts: list[str],
    cluster_type: str,
    language: str = "unknown",
    groq_api_key: str = "",
    model: str = "llama3-70b-8192",
) -> str:
    """Extract a meaningful label from cluster texts using TF-IDF.

    If the TF-IDF result is too generic (only stopwords or common app terms),
    falls back to a short LLM-generated label when groq_api_key is provided.
    """
    fallback = f"{cluster_type.title()} Cluster"

    if not texts:
        return fallback

    tfidf_label: Optional[str] = None
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        stop_words = list(COMBINED_STOP_WORDS)
        vectorizer = TfidfVectorizer(
            max_features=50,
            stop_words=stop_words,
            min_df=1,
            ngram_range=(1, 2),
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()

        scores = np.asarray(tfidf_matrix.sum(axis=0)).flatten()
        top_indices = scores.argsort()[::-1][:3]
        terms = [feature_names[i] for i in top_indices if scores[i] > 0]

        if terms:
            tfidf_label = " / ".join(terms)

    except Exception:
        log.warning("cluster_label_tfidf_failed", texts_count=len(texts))

    # Quality check: if TF-IDF produced something useful, use it
    if tfidf_label and is_label_meaningful(tfidf_label):
        return tfidf_label

    # Label is generic or missing — try LLM
    if groq_api_key:
        log.info(
            "cluster_label_llm_fallback",
            tfidf_label=tfidf_label,
            cluster_type=cluster_type,
        )
        llm_label = _generate_label_with_llm(texts, cluster_type, language, groq_api_key, model)
        if llm_label and llm_label.strip():
            return llm_label

    # Final fallback: use TF-IDF result even if generic, or the default string
    return tfidf_label or fallback


def generate_cluster_summary(
    label: str,
    example_texts: list[str],
    cluster_type: str,
    groq_api_key: str,
    language: str = "unknown",
    model: str = "llama3-70b-8192",
) -> Optional[str]:
    """
    Generate an LLM summary for a cluster. Prompt is written in the detected
    language so the response matches the review language.
    """
    if not groq_api_key or not example_texts:
        return None

    # Determine response language from detected language
    lang_instruction = (
        "Antworte auf Deutsch." if language == "de"
        else "Respond in English." if language == "en"
        else "Respond in the same language as the reviews."
    )

    example_block = "\n".join(f"- {t[:200]}" for t in example_texts[:10])

    prompt = (
        f"You are analyzing user app reviews. "
        f"The cluster label is '{label}' (type: {cluster_type}).\n\n"
        f"Example reviews from this cluster:\n{example_block}\n\n"
        f"Write a 2-sentence summary of what users are saying in this cluster. "
        f"Be specific and actionable. {lang_instruction}"
    )

    for attempt in range(3):
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            if attempt == 2:
                log.exception("groq_summary_failed", label=label, attempt=attempt)
            else:
                log.warning("groq_summary_retry", label=label, attempt=attempt)

    return None
