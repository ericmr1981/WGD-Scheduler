"""
Tests for scheduler/core.py — core capacity & analysis functions
"""

import pytest
from scheduler.core import (
    calculate_min_staff,
    calculate_total_hours_needed,
    calculate_available_hours,
    analyze_gap,
)


class TestCalculateMinStaff:
    def test_basic_calculation(self):
        """60 customers / 18 productivity = 4 staff"""
        assert calculate_min_staff(60, 18) == 4

    def test_exact_division(self):
        """36 / 18 = 2"""
        assert calculate_min_staff(36, 18) == 2

    def test_rounds_up(self):
        """37 / 18 = 3 (ceil)"""
        assert calculate_min_staff(37, 18) == 3

    def test_minimum_one(self):
        """Even with 0 customers, returns 1"""
        assert calculate_min_staff(0, 18) == 1

    def test_minimum_one_with_low_volume(self):
        """5 / 18 = 1 (ceil, minimum)"""
        assert calculate_min_staff(5, 18) == 1

    def test_low_productivity(self):
        """60 / 5 = 12"""
        assert calculate_min_staff(60, 5) == 12

    def test_high_volume(self):
        """200 / 18 = 12 (ceil)"""
        assert calculate_min_staff(200, 18) == 12

    def test_zero_productivity_raises(self):
        with pytest.raises(ValueError, match="单人产能必须大于 0"):
            calculate_min_staff(60, 0)

    def test_negative_productivity_raises(self):
        with pytest.raises(ValueError, match="单人产能必须大于 0"):
            calculate_min_staff(60, -1)


class TestCalculateTotalHoursNeeded:
    def test_basic(self):
        """12h * 2 staff = 24"""
        assert calculate_total_hours_needed(12, 2, 3) == 24

    def test_one_staff(self):
        assert calculate_total_hours_needed(8, 1, 1) == 8


class TestCalculateAvailableHours:
    def test_basic(self):
        """3 employees * 8h = 24h"""
        assert calculate_available_hours(3, 8) == 24

    def test_default_hours(self):
        assert calculate_available_hours(3) == 24


class TestAnalyzeGap:
    def test_sufficient(self):
        result = analyze_gap(20, 24)
        assert result["status"] == "充足"
        assert result["gap_hours"] <= 0

    def test_balanced(self):
        result = analyze_gap(20, 18)
        assert result["status"] == "平衡"
        assert result["gap_hours"] == 2

    def test_shortage(self):
        """10 needed, 6 available = 40% gap → 缺口"""
        result = analyze_gap(10, 6)
        assert result["status"] == "缺口"
        assert result["gap_hours"] == 4
        assert result["gap_ratio"] == 0.4

    def test_exact_match(self):
        result = analyze_gap(24, 24)
        assert result["status"] == "充足"
        assert result["gap_hours"] == 0
