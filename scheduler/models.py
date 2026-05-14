"""
WGD Scheduler — Data Models

Pydantic models for the scheduling domain.
All models are immutable (frozen) by default.
"""

from datetime import date, time, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DayType(str, Enum):
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class ShiftType(str, Enum):
    A = "A"  # 早班 10:00-18:00
    B = "B"  # 中班 12:00-20:00
    C = "C"  # 晚班 14:00-22:00


class TimeSlot(BaseModel):
    """A time slot within the operating day."""
    name: str
    start: time
    end: time
    day_type: DayType
    estimated_customers_per_hour: int = Field(gt=0)
    is_peak: bool = False

    @property
    def duration_hours(self) -> float:
        return (datetime.combine(date.min, self.end) -
                datetime.combine(date.min, self.start)).total_seconds() / 3600


class StoreConfig(BaseModel):
    """Store configuration input."""
    name: str = "Gelato Store"
    open_time: time = time(10, 0)
    close_time: time = time(22, 0)
    employee_count: int = Field(default=3, ge=1, le=100)
    productivity_per_hour: float = Field(default=18.0, gt=0)

    @property
    def operating_hours(self) -> float:
        return (datetime.combine(date.min, self.close_time) -
                datetime.combine(date.min, self.open_time)).total_seconds() / 3600

    @property
    def needs_overlapping_shifts(self) -> bool:
        """营业时间超过 8h 需要多班次错峰."""
        return self.operating_hours > 8


class Employee(BaseModel):
    """Employee information (simplified, all-staff-can-do-all)."""
    name: str
    max_hours_per_week: int = Field(default=40, le=48)
    available_time_ranges: list[str] = ["10:00-22:00"]
    preference: Optional[str] = None  # e.g., "early shift", "late shift"


class StaffingRequirement(BaseModel):
    """Result of capacity calculation for a time slot."""
    slot: TimeSlot
    calculated_min_staff: int  # Ceiling(customers / productivity)
    actual_staff: int
    is_covered: bool
    gap: int  # positive = understaffed
    note: str = ""


class ShiftAssignment(BaseModel):
    """A single shift assignment for one employee on one day."""
    employee: str
    date: date
    shift_type: ShiftType
    hours: float = 8.0


class WeeklySchedule(BaseModel):
    """Complete weekly schedule."""
    week_start: date
    store: StoreConfig
    assignments: list[ShiftAssignment]
    rest_days: dict[str, list[date]]  # employee -> list of rest days
    staffing_requirements: list[StaffingRequirement]
    status: str = "draft"  # draft / published


class ValidationResult(BaseModel):
    """Result of schedule validation."""
    all_slots_covered: bool
    peak_hours_covered: bool
    no_seven_day_streak: bool
    daily_hours_compliant: bool
    capacity_adequate: bool
    weekend_rest_minimized: bool
    details: dict[str, str]


class ReviewData(BaseModel):
    """Weekly review data for parameter iteration."""
    week_start: date
    estimated_customers: dict[str, int]  # slot_name -> estimated
    actual_customers: dict[str, int]    # slot_name -> actual
    previous_productivity: float
    adjusted_productivity: float
    staff_feedback: str = ""
