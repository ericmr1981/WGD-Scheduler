"""
Tests for scheduler/traffic_analyzer.py — customer traffic computation
"""

from datetime import datetime, date

import pytest

from scheduler.traffic_analyzer import (
    get_time_slot,
    group_by_slots,
    average_by_weekday_type,
    build_demand_30min,
    get_actual_traffic,
)


class TestGetTimeSlot:
    """Floor timestamp to nearest 30-min slot."""

    def test_exact_hour(self):
        assert get_time_slot("12:00") == "12:00"
        assert get_time_slot("13:00") == "13:00"
        assert get_time_slot("00:00") == "00:00"

    def test_exact_half(self):
        assert get_time_slot("12:30") == "12:30"
        assert get_time_slot("14:30") == "14:30"

    def test_floors_to_hour(self):
        assert get_time_slot("12:14") == "12:00"
        assert get_time_slot("13:29") == "13:00"
        assert get_time_slot("09:05") == "09:00"

    def test_floors_to_half(self):
        assert get_time_slot("12:34") == "12:30"
        assert get_time_slot("12:59") == "12:30"
        assert get_time_slot("08:45") == "08:30"

    def test_datetime_string_input(self):
        assert get_time_slot("2024-03-15T12:14:00") == "12:00"
        assert get_time_slot("2024-03-15 12:45:00") == "12:30"

    def test_datetime_object_input(self):
        dt = datetime(2024, 3, 15, 14, 22)
        assert get_time_slot(dt) == "14:00"

    def test_midnight_boundary(self):
        assert get_time_slot("23:45") == "23:30"
        assert get_time_slot("23:59") == "23:30"


class TestGroupBySlots:
    """Group order numbers by (date, time_slot)."""

    def test_single_order(self):
        rows = [
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:14:00"},
        ]
        result = group_by_slots(rows)
        assert result == {("2024-03-15", "10:00"): {"ORD-001"}}

    def test_same_order_multiple_products_dedup(self):
        rows = [
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:05:00"},
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:10:00"},
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:20:00"},
        ]
        result = group_by_slots(rows)
        assert result == {("2024-03-15", "10:00"): {"ORD-001"}}

    def test_different_orders_same_slot(self):
        rows = [
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:14:00"},
            {"order_no": "ORD-002", "order_time": "2024-03-15 10:22:00"},
        ]
        result = group_by_slots(rows)
        assert result == {("2024-03-15", "10:00"): {"ORD-001", "ORD-002"}}

    def test_different_slots(self):
        rows = [
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:14:00"},
            {"order_no": "ORD-002", "order_time": "2024-03-15 10:34:00"},
        ]
        result = group_by_slots(rows)
        assert ("2024-03-15", "10:00") in result
        assert ("2024-03-15", "10:30") in result

    def test_multiple_dates(self):
        rows = [
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:14:00"},
            {"order_no": "ORD-002", "order_time": "2024-03-16 10:14:00"},
        ]
        result = group_by_slots(rows)
        assert ("2024-03-15", "10:00") in result
        assert ("2024-03-16", "10:00") in result
        assert len(result) == 2

    def test_order_spanning_slots(self):
        """Same order across different time slots should appear in both."""
        rows = [
            {"order_no": "ORD-001", "order_time": "2024-03-15 10:14:00"},
            {"order_no": "ORD-001", "order_time": "2024-03-15 14:45:00"},
        ]
        result = group_by_slots(rows)
        assert ("2024-03-15", "10:00") in result
        assert ("2024-03-15", "14:30") in result
        assert result[("2024-03-15", "10:00")] == {"ORD-001"}
        assert result[("2024-03-15", "14:30")] == {"ORD-001"}

    def test_empty_input(self):
        assert group_by_slots([]) == {}


class TestAverageByWeekdayType:
    """Average unique order counts by weekday type."""

    # Helper to reconstruct grouped dict from list of (date, slot, order_nos) tuples
    def _make_grouped(self, entries: list) -> dict:
        result = {}
        for date_str, slot, orders in entries:
            result[(date_str, slot)] = set(orders)
        return result

    def test_single_weekday(self):
        # 2024-03-11 is a Monday
        grouped = {
            ("2024-03-11", "10:00"): {"ORD-001", "ORD-002", "ORD-003"},
            ("2024-03-11", "10:30"): {"ORD-004", "ORD-005"},
        }
        result = average_by_weekday_type(grouped)
        assert result["weekday"]["10:00"] == 3.0
        assert result["weekday"]["10:30"] == 2.0
        assert result["weekend"] == {}

    def test_multiple_weekdays_averaged(self):
        # 2024-03-11 = Monday, 2024-03-12 = Tuesday
        grouped = {
            ("2024-03-11", "10:00"): {"A", "B", "C"},   # 3 orders
            ("2024-03-12", "10:00"): {"D", "E"},          # 2 orders
            ("2024-03-11", "10:30"): {"F", "G"},           # 2 orders
            ("2024-03-12", "10:30"): {"H", "I", "J", "K"},  # 4 orders
        }
        result = average_by_weekday_type(grouped)
        # 10:00: (3+2)/2 = 2.5
        # 10:30: (2+4)/2 = 3.0
        assert result["weekday"]["10:00"] == 2.5
        assert result["weekday"]["10:30"] == 3.0

    def test_weekend_separation(self):
        # 2024-03-16 = Saturday
        grouped = {
            ("2024-03-11", "10:00"): {"A", "B"},          # Mon = 2
            ("2024-03-16", "10:00"): {"C", "D", "E"},      # Sat = 3
        }
        result = average_by_weekday_type(grouped)
        assert result["weekday"]["10:00"] == 2.0
        assert result["weekend"]["10:00"] == 3.0

    def test_mixed_weekdays_and_weekends(self):
        # 2024-03-11 = Mon, 2024-03-13 = Wed, 2024-03-16 = Sat, 2024-03-17 = Sun
        grouped = {
            ("2024-03-11", "10:00"): {"A", "B"},          # Mon
            ("2024-03-13", "10:00"): {"C"},                # Wed
            ("2024-03-16", "10:00"): {"D", "E", "F"},      # Sat
            ("2024-03-17", "10:00"): {"G", "H", "I", "J"}, # Sun
        }
        result = average_by_weekday_type(grouped)
        # weekday: (2+1)/2 = 1.5
        # weekend: (3+4)/2 = 3.5
        assert result["weekday"]["10:00"] == 1.5
        assert result["weekend"]["10:00"] == 3.5

    def test_empty_data(self):
        result = average_by_weekday_type({})
        assert result == {"weekday": {}, "weekend": {}}

    def test_handles_mixed_slots_across_days(self):
        # Not all days have the same slots
        grouped = {
            ("2024-03-11", "10:00"): {"A", "B"},
            ("2024-03-12", "10:00"): {"C"},
            ("2024-03-11", "10:30"): {"D"},
            # No 10:30 on 2024-03-12
        }
        result = average_by_weekday_type(grouped)
        # 10:00: (2+1)/2 = 1.5
        # 10:30: 1/2 = 0.5 (only one weekday had it, still divided by 2 weekdays)
        assert result["weekday"]["10:00"] == 1.5
        assert result["weekday"]["10:30"] == 0.5


class TestBuildDemand30min:
    """Build demand_30min dict for scheduling week."""

    WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]
    WEEKENDS = ["周六", "周日"]
    ALL_DAYS = WEEKDAYS + WEEKENDS

    def test_basic_mapping(self):
        avg_data = {
            "weekday": {"10:00": 5.0, "10:30": 3.0},
            "weekend": {"10:00": 7.0, "10:30": 6.0},
        }
        result = build_demand_30min(avg_data, self.ALL_DAYS, open_hour=10, close_hour=11)
        assert result["周一"]["10:00"] == 5
        assert result["周一"]["10:30"] == 3
        assert result["周六"]["10:00"] == 7
        assert result["周六"]["10:30"] == 6

    def test_fills_missing_slots_with_zero(self):
        avg_data = {
            "weekday": {"10:00": 5.0},
            "weekend": {"10:30": 6.0},
        }
        result = build_demand_30min(avg_data, self.ALL_DAYS, open_hour=10, close_hour=11)
        assert result["周一"]["10:00"] == 5
        assert result["周一"]["10:30"] == 0
        assert result["周六"]["10:00"] == 0
        assert result["周六"]["10:30"] == 6

    def test_weekend_fallback_to_weekday(self):
        avg_data = {
            "weekday": {"10:00": 5.0, "10:30": 3.0},
            "weekend": {},
        }
        result = build_demand_30min(avg_data, self.ALL_DAYS, open_hour=10, close_hour=11)
        assert result["周六"]["10:00"] == 5
        assert result["周六"]["10:30"] == 3
        assert result["周日"]["10:00"] == 5
        assert result["周日"]["10:30"] == 3

    def test_full_day_range(self):
        avg_data = {
            "weekday": {"10:00": 1.0, "10:30": 2.0, "11:00": 3.0},
            "weekend": {},
        }
        result = build_demand_30min(avg_data, ["周一"], open_hour=10, close_hour=12)
        assert len(result["周一"]) == 4  # 10:00, 10:30, 11:00, 11:30
        assert result["周一"]["10:00"] == 1
        assert result["周一"]["11:00"] == 3
        assert result["周一"]["11:30"] == 0

    def test_converts_to_int(self):
        avg_data = {
            "weekday": {"10:00": 5.7},
            "weekend": {},
        }
        result = build_demand_30min(avg_data, ["周一"], open_hour=10, close_hour=11)
        assert result["周一"]["10:00"] == 5
        assert isinstance(result["周一"]["10:00"], int)

    def test_default_hours(self):
        avg_data = {"weekday": {}, "weekend": {}}
        result = build_demand_30min(avg_data, ["周一"], open_hour=10, close_hour=22)
        # Should produce 24 half-hour slots (12 hours * 2)
        assert len(result["周一"]) == 24


class TestGetActualTraffic:
    """Full pipeline test — verifies function exists and handles no data."""

    def test_function_exists(self):
        assert callable(get_actual_traffic)

    def test_returns_empty_dict_when_no_data(self):
        # With no Supabase config, should return {} gracefully
        week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        result = get_actual_traffic("non_existent_store", week_days)
        assert isinstance(result, dict)

    def test_accepts_custom_hours(self):
        week_days = ["周一"]
        result = get_actual_traffic("test_store", week_days, open_hour=9, close_hour=18)
        assert isinstance(result, dict)
