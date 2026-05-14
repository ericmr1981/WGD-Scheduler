"""
Tests for scheduler/peaks.py — peak hour models
"""

from scheduler.peaks import (
    get_day_pattern,
    estimate_hourly_customers,
    DEFAULT_PATTERNS,
)


class TestGetDayPattern:
    def test_weekday(self):
        pattern = get_day_pattern("周一")
        assert pattern.day_type == "weekday"
        assert len(pattern.periods) == 2

    def test_weekend(self):
        pattern = get_day_pattern("周六")
        assert pattern.day_type == "weekend"
        assert len(pattern.periods) == 2

    def test_holiday_overrides(self):
        pattern = get_day_pattern("周一", is_holiday=True)
        assert pattern.day_type == "holiday"
        assert len(pattern.periods) == 2

    def test_friday_is_weekday(self):
        """周五也算工作日"""
        pattern = get_day_pattern("周五")
        assert pattern.day_type == "weekday"

    def test_sunday_is_weekend(self):
        pattern = get_day_pattern("周日")
        assert pattern.day_type == "weekend"


class TestEstimateHourlyCustomers:
    def test_returns_12_hours(self):
        """10:00-22:00 = 12 hours"""
        result = estimate_hourly_customers(240, "周一")
        assert len(result) == 12

    def test_all_hours_present(self):
        result = estimate_hourly_customers(240, "周一")
        hours = [r["hour"] for r in result]
        assert hours == list(range(10, 22))

    def test_holiday_higher_volume(self):
        weekday = estimate_hourly_customers(200, "周一")
        holiday = estimate_hourly_customers(200, "周一", is_holiday=True)
        weekday_total = sum(r["customers"] for r in weekday)
        holiday_total = sum(r["customers"] for r in holiday)
        assert holiday_total > weekday_total

    def test_weekend_higher_than_weekday(self):
        weekday = estimate_hourly_customers(200, "周一")
        weekend = estimate_hourly_customers(200, "周六")
        weekday_total = sum(r["customers"] for r in weekday)
        weekend_total = sum(r["customers"] for r in weekend)
        assert weekend_total > weekday_total

    def test_customers_positive(self):
        result = estimate_hourly_customers(100, "周二")
        for r in result:
            assert r["customers"] >= 1
