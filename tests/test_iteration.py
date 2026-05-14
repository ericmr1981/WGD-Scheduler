"""
Tests for scheduler/iteration.py — weekly review & parameter iteration
"""

from scheduler.iteration import (
    WeeklyReview,
    calculate_adjusted_productivity,
    suggest_improvements,
    maturity_level,
)


class TestCalculateAdjustedProductivity:
    def test_basic_adjustment(self):
        """70% actual (17) + 30% base (18) = 17.3"""
        result = calculate_adjusted_productivity(18, 17)
        assert result == 17.3

    def test_higher_actual(self):
        """70% actual (20) + 30% base (18) = 19.4"""
        result = calculate_adjusted_productivity(18, 20)
        assert result == 19.4

    def test_zero_actual_returns_base(self):
        """If actual_hourly_output is 0, return base unchanged"""
        result = calculate_adjusted_productivity(18, 0)
        assert result == 18


class TestSuggestImprovements:
    def test_long_queue_time(self):
        review = WeeklyReview(
            week_start="2026-W20",
            actual_customers=200,
            actual_staff_hours=72,
            actual_peak_queue_time=15,
            issues=[],
            adjustments={},
        )
        suggestions = suggest_improvements(review, 2)
        assert len(suggestions) >= 1
        assert "排队" in suggestions[0] or "排队" in str(suggestions)

    def test_no_issues(self):
        review = WeeklyReview(
            week_start="2026-W20",
            actual_customers=200,
            actual_staff_hours=72,
            actual_peak_queue_time=5,
            issues=[],
            adjustments={},
        )
        suggestions = suggest_improvements(review, 2)
        assert len(suggestions) == 0

    def test_issues_included(self):
        review = WeeklyReview(
            week_start="2026-W20",
            actual_customers=200,
            actual_staff_hours=72,
            actual_peak_queue_time=3,
            issues=["备料不足", "收银台排队"],
            adjustments={},
        )
        suggestions = suggest_improvements(review, 2)
        assert len(suggestions) == 2


class TestMaturityLevel:
    def test_level_1_no_reviews(self):
        result = maturity_level([])
        assert result["level"] == 1
        assert "初始级" in result["label"]

    def test_level_2_four_reviews(self):
        reviews = [WeeklyReview("w", 100, 72, 5, [], {}) for _ in range(4)]
        result = maturity_level(reviews)
        assert result["level"] == 2

    def test_level_3_twelve_reviews(self):
        reviews = [WeeklyReview("w", 100, 72, 5, [], {}) for _ in range(12)]
        result = maturity_level(reviews)
        assert result["level"] == 3

    def test_level_4_twenty_four_reviews(self):
        reviews = [WeeklyReview("w", 100, 72, 5, [], {}) for _ in range(24)]
        result = maturity_level(reviews)
        assert result["level"] == 4

    def test_level_5_fifty_two_reviews(self):
        reviews = [WeeklyReview("w", 100, 72, 5, [], {}) for _ in range(52)]
        result = maturity_level(reviews)
        assert result["level"] == 5

    def test_review_count_in_output(self):
        reviews = [WeeklyReview("w", 100, 72, 5, [], {}) for _ in range(10)]
        result = maturity_level(reviews)
        assert result["total_reviews"] == 10
