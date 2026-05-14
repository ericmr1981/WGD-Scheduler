"""
Tests for scheduler/models.py — Pydantic data models
"""

from datetime import date, time
from scheduler.models import (
    StoreConfig, Employee, TimeSlot, ShiftAssignment,
    StaffingRequirement, WeeklySchedule, ValidationResult, ReviewData,
    DayType, ShiftType,
)


class TestStoreConfig:
    def test_default_values(self):
        config = StoreConfig()
        assert config.name == "Gelato Store"
        assert config.employee_count == 3
        assert config.productivity_per_hour == 18.0

    def test_operating_hours(self):
        config = StoreConfig()
        assert config.operating_hours == 12.0  # 10:00-22:00

    def test_needs_overlapping_shifts_true(self):
        config = StoreConfig(open_time=time(10, 0), close_time=time(22, 0))
        assert config.needs_overlapping_shifts is True

    def test_needs_overlapping_shifts_false(self):
        config = StoreConfig(open_time=time(9, 0), close_time=time(17, 0))
        assert config.needs_overlapping_shifts is False


class TestEmployee:
    def test_defaults(self):
        emp = Employee(name="张三")
        assert emp.max_hours_per_week == 40
        assert "10:00-22:00" in emp.available_time_ranges

    def test_with_preference(self):
        emp = Employee(name="李四", preference="early shift")
        assert emp.preference == "early shift"


class TestTimeSlot:
    def test_duration_hours(self):
        slot = TimeSlot(
            name="午高峰", start=time(12, 0), end=time(14, 0),
            day_type=DayType.WEEKDAY, estimated_customers_per_hour=50,
            is_peak=True
        )
        assert slot.duration_hours == 2.0

    def test_default_not_peak(self):
        slot = TimeSlot(
            name="上午", start=time(10, 0), end=time(12, 0),
            day_type=DayType.WEEKDAY, estimated_customers_per_hour=15,
        )
        assert slot.is_peak is False


class TestShiftAssignment:
    def test_default_hours(self):
        assignment = ShiftAssignment(
            employee="张三", date=date(2026, 5, 18),
            shift_type=ShiftType.A
        )
        assert assignment.hours == 8.0


class TestWeeklySchedule:
    def test_default_status(self):
        config = StoreConfig()
        schedule = WeeklySchedule(
            week_start=date(2026, 5, 18),
            store=config,
            assignments=[],
            rest_days={},
            staffing_requirements=[],
        )
        assert schedule.status == "draft"
