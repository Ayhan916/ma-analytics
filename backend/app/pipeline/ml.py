from __future__ import annotations
import re
import numpy as np
from typing import Optional

_sentiment_pipeline = None
_embedding_model = None


def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True,
            max_length=512,
        )
    return _sentiment_pipeline


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def predict_sentiments(texts: list) -> list:
    pipe = get_sentiment_pipeline()
    results = []
    for text in texts:
        try:
            out = pipe(text[:512])[0]
            label = out["label"].lower()
            if "positive" in label:
                results.append("positive")
            elif "negative" in label:
                results.append("negative")
            else:
                results.append("neutral")
        except Exception:
            results.append("neutral")
    return results


def create_embeddings(texts: list) -> np.ndarray:
    model = get_embedding_model()
    return model.encode(texts, show_progress_bar=False)


def cluster_texts(embeddings: np.ndarray, n_clusters: int) -> np.ndarray:
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    return km.fit_predict(embeddings)


def get_cluster_label(texts: list, cluster_type: str) -> str:
    if not texts:
        return f"{cluster_type.title()} Cluster"
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vectorizer = TfidfVectorizer(max_features=3, stop_words="english", min_df=1)
        vectorizer.fit_transform(texts)
        terms = vectorizer.get_feature_names_out()
        return " / ".join(terms) if len(terms) > 0 else f"{cluster_type.title()} Cluster"
    except Exception:
        return f"{cluster_type.title()} Cluster"


def generate_cluster_summary_groq(label: str, examples: list, cluster_type: str, groq_api_key: str) -> Optional[str]:
    try:
        from groq import Groq
        client = Groq(api_key=groq_api_key)
        example_text = "\n".join(f"- {e}" for e in examples[:5])
        prompt = (
            f"You are analyzing app reviews. Based on these example reviews from the '{label}' cluster "
            f"(type: {cluster_type}), write a 1-2 sentence summary of what users are saying:\n\n"
            f"{example_text}\n\nSummary:"
        )
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None
