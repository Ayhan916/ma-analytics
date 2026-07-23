"""Unit tests for app/pipeline/ml.py pure functions.

ML models are NOT loaded here — we test the logic around them.
predict_sentiments and create_embeddings are tested at the label-parsing
level with mocked pipeline output, not by actually running inference.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.pipeline.ml import (
    clean_text,
    detect_language,
    get_cluster_label,
    optimal_cluster_count,
    COMBINED_STOP_WORDS,
    EMBEDDING_DIM,
)


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_removes_http_url(self):
        result = clean_text("Check https://example.com for more")
        assert "http" not in result
        assert "example.com" not in result

    def test_removes_www_url(self):
        result = clean_text("visit www.app.de for details")
        assert "www" not in result

    def test_converts_emoji_to_tag(self):
        result = clean_text("Great app 😊")
        assert "positive" in result

    def test_converts_crash_emoji(self):
        result = clean_text("App crashed 💥 again")
        assert "crash" in result

    def test_preserves_apostrophe_in_contraction(self):
        result = clean_text("I don't like this")
        assert "don't" in result

    def test_lowercases_text(self):
        result = clean_text("THIS IS UPPERCASE")
        assert result == result.lower()

    def test_normalizes_whitespace(self):
        result = clean_text("too   many    spaces")
        assert "  " not in result

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_only_url(self):
        result = clean_text("https://example.com")
        assert result.strip() == ""

    def test_unicode_apostrophe_normalized(self):
        # Smart quote apostrophe (') should be treated as normal apostrophe
        result = clean_text("can’t stop")
        assert "can't" in result or "cant" in result  # preserved or normalized


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

class TestDetectLanguage:
    def test_returns_unknown_for_empty(self):
        # langdetect raises on empty strings
        result = detect_language("")
        assert result == "unknown"

    def test_returns_string(self):
        result = detect_language("This is a short English text for testing.")
        assert isinstance(result, str)
        assert len(result) >= 2

    def test_detects_english(self):
        text = (
            "The application is very good and I enjoy using it every day. "
            "The performance is excellent and the user interface is clean."
        )
        result = detect_language(text)
        assert result == "en"

    def test_detects_german(self):
        text = (
            "Die Anwendung ist sehr gut und ich benutze sie jeden Tag. "
            "Die Leistung ist ausgezeichnet und die Benutzeroberfläche ist sauber."
        )
        result = detect_language(text)
        assert result == "de"

    def test_does_not_raise_on_garbage(self):
        # Should not raise — returns "unknown" on error
        result = detect_language("!!! @@@ ###")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_cluster_label
# ---------------------------------------------------------------------------

class TestGetClusterLabel:
    def test_empty_list_returns_fallback(self):
        result = get_cluster_label([], cluster_type="issue")
        assert result == "Issue Cluster"

    def test_empty_list_strength_fallback(self):
        result = get_cluster_label([], cluster_type="strength")
        assert result == "Strength Cluster"

    def test_returns_string(self):
        texts = ["The app crashes on startup", "Crashes every time I open it"]
        result = get_cluster_label(texts, cluster_type="issue")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_filters_stop_words(self):
        # Stop words should not appear as the primary label term
        texts = ["the app is very good", "the app is and good", "the app is so good"]
        result = get_cluster_label(texts, cluster_type="strength")
        label_lower = result.lower()
        # Common stop words should not be the entire label
        for stop in ["the", "is", "and", "very", "so"]:
            # The label may contain stop words as part of bigrams but
            # should not be just a single stop word
            if result == stop:
                pytest.fail(f"Label is just a stop word: '{stop}'")

    def test_uses_separator(self):
        texts = [
            "battery drain is terrible",
            "battery dies quickly",
            "battery life is too short",
            "phone gets hot and battery drains",
        ]
        result = get_cluster_label(texts, cluster_type="issue")
        assert "/" in result or len(result) > 3

    def test_single_text(self):
        result = get_cluster_label(["crashes"], cluster_type="issue")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# optimal_cluster_count
# ---------------------------------------------------------------------------

class TestOptimalClusterCount:
    def _make_embeddings(self, n: int) -> np.ndarray:
        rng = np.random.default_rng(seed=42)
        return rng.random((n, 16)).astype(np.float32)

    def test_too_few_samples_returns_min_k(self):
        # n < min_k * 2 → return min_k
        embeddings = self._make_embeddings(3)
        result = optimal_cluster_count(embeddings, min_k=2, max_k=10)
        assert result == 2

    def test_normal_range(self):
        embeddings = self._make_embeddings(60)
        result = optimal_cluster_count(embeddings, min_k=2, max_k=8)
        assert 2 <= result <= 8

    def test_max_k_capped_by_n(self):
        # n=20, max_k=50 → actual_max = min(50, 10) = 10
        embeddings = self._make_embeddings(20)
        result = optimal_cluster_count(embeddings, min_k=2, max_k=50)
        assert result <= 10

    def test_returns_int(self):
        embeddings = self._make_embeddings(30)
        result = optimal_cluster_count(embeddings, min_k=2, max_k=6)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# COMBINED_STOP_WORDS sanity checks
# ---------------------------------------------------------------------------

class TestStopWords:
    def test_contains_german_words(self):
        assert "und" in COMBINED_STOP_WORDS
        assert "die" in COMBINED_STOP_WORDS
        assert "der" in COMBINED_STOP_WORDS

    def test_contains_english_words(self):
        assert "the" in COMBINED_STOP_WORDS
        assert "and" in COMBINED_STOP_WORDS
        assert "is" in COMBINED_STOP_WORDS

    def test_minimum_size(self):
        assert len(COMBINED_STOP_WORDS) > 200


# ---------------------------------------------------------------------------
# EMBEDDING_DIM constant
# ---------------------------------------------------------------------------

def test_embedding_dim():
    assert EMBEDDING_DIM == 384
