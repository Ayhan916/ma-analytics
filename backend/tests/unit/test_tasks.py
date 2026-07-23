"""Unit tests for pipeline task logic.

Tests the pure functions from tasks.py without running Celery or touching the DB.
"""
from __future__ import annotations

import pytest

# Import the private function directly — it's pure logic with no side effects
from app.pipeline.tasks import _score_to_sentiment


class TestScoreToSentiment:
    """_score_to_sentiment(score) maps star ratings to sentiment labels.

    Business rule:
      score >= 4.0  → "positive"
      score <= 2.0  → "negative"
      score == 3.0  → None  (ambiguous: ML model decides)
      score is None → None  (no rating available)
    """

    def test_five_star_is_positive(self):
        assert _score_to_sentiment(5.0) == "positive"

    def test_four_star_is_positive(self):
        assert _score_to_sentiment(4.0) == "positive"

    def test_four_point_five_is_positive(self):
        assert _score_to_sentiment(4.5) == "positive"

    def test_two_star_is_negative(self):
        assert _score_to_sentiment(2.0) == "negative"

    def test_one_star_is_negative(self):
        assert _score_to_sentiment(1.0) == "negative"

    def test_one_point_five_is_negative(self):
        assert _score_to_sentiment(1.5) == "negative"

    def test_three_star_is_ambiguous(self):
        # 3-star reviews are sent to the ML model — must return None
        assert _score_to_sentiment(3.0) is None

    def test_three_point_five_is_ambiguous(self):
        assert _score_to_sentiment(3.5) is None

    def test_two_point_five_is_ambiguous(self):
        assert _score_to_sentiment(2.5) is None

    def test_none_score_returns_none(self):
        assert _score_to_sentiment(None) is None

    def test_boundary_exactly_four(self):
        # Boundary check: 4.0 must be "positive", not ambiguous
        assert _score_to_sentiment(4.0) == "positive"

    def test_boundary_exactly_two(self):
        # Boundary check: 2.0 must be "negative", not ambiguous
        assert _score_to_sentiment(2.0) == "negative"

    def test_return_type_is_str_or_none(self):
        for score in [1.0, 2.0, 3.0, 4.0, 5.0, None]:
            result = _score_to_sentiment(score)
            assert result is None or isinstance(result, str)
