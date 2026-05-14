"""
Tests for scheduler/shifts.py — shift definitions and generation
"""

from scheduler.shifts import (
    get_shifts,
    rotate_shifts,
    generate_weekly_schedule,
    get_half_hourly_coverage,
)


class TestGetShifts:
    def test_returns_three_shifts(self):
        shifts = get_shifts()
        assert len(shifts) == 3

    def test_shift_names(self):
        shifts = get_shifts()
        names = [s.name for s in shifts]
        assert names == ["A", "B", "C"]

    def test_shift_durations(self):
        shifts = get_shifts()
        for s in shifts:
            assert s.duration == 8


class TestRotateShifts:
    def test_basic_rotation(self):
        current = {"张三": "A", "李四": "B", "王五": "C"}
        result = rotate_shifts(current, week_number=1)
        employees = list(current.keys())
        assert result[employees[0]] == "B"  # A → B
        assert result[employees[1]] == "C"  # B → C
        assert result[employees[2]] == "A"  # C → A

    def test_no_rotation_week_0(self):
        current = {"张三": "A", "李四": "B", "王五": "C"}
        result = rotate_shifts(current, week_number=0)
        assert result == current

    def test_full_cycle(self):
        current = {"张三": "A", "李四": "B", "王五": "C"}
        after_3 = rotate_shifts(current, week_number=3)
        assert after_3 == current


class TestGenerateWeeklySchedule:
    def test_basic_schedule(self):
        employees = ["张三", "李四"]
        rest_days = {"张三": ["周二"], "李四": []}
        shifts = get_shifts()
        rotation = {"张三": "A", "李四": "B"}
        week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        schedule = generate_weekly_schedule(employees, rest_days, shifts, rotation, week_days)

        assert "张三" in schedule
        assert "李四" in schedule
        assert schedule["张三"]["周二"] is None
        assert schedule["张三"]["周一"] == "A"

    def test_rest_days_respected(self):
        employees = ["张三"]
        rest_days = {"张三": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}
        shifts = get_shifts()
        rotation = {"张三": "C"}
        week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        schedule = generate_weekly_schedule(employees, rest_days, shifts, rotation, week_days)
        for day in week_days:
            assert schedule["张三"][day] is None


class TestGetHalfHourlyCoverage:
    def test_single_employee(self):
        schedule = {
            "张三": {
                "周一": "A",
            }
        }
        shifts = get_shifts()
        coverage = get_half_hourly_coverage(schedule, shifts, "周一")
        # A shift: 10:00-18:00 → covers 16 half-hour slots (10:00 to 17:30)
        slots_covered = [s for s in coverage if s["staff"] > 0]
        assert len(slots_covered) == 16
        # 10:00 should be covered
        assert coverage[0]["time"] == "10:00"
        assert coverage[0]["staff"] == 1
        # 18:00 should NOT be covered (A ends at 18:00)
        end_slot = [s for s in coverage if s["time"] == "18:00"]
        assert end_slot and end_slot[0]["staff"] == 0

    def test_two_employees_overlap(self):
        schedule = {
            "张三": {"周一": "A"},
            "李四": {"周一": "B"},
        }
        shifts = get_shifts()
        coverage = get_half_hourly_coverage(schedule, shifts, "周一")
        # 10:00 - only A
        slot_10 = [s for s in coverage if s["time"] == "10:00"][0]
        assert slot_10["staff"] == 1
        # 12:00 - A + B
        slot_12 = [s for s in coverage if s["time"] == "12:00"][0]
        assert slot_12["staff"] == 2
        # 18:00 - only B
        slot_18 = [s for s in coverage if s["time"] == "18:00"][0]
        assert slot_18["staff"] == 1

    def test_employee_rest(self):
        schedule = {
            "张三": {"周一": None},
        }
        shifts = get_shifts()
        coverage = get_half_hourly_coverage(schedule, shifts, "周一")
        for slot in coverage:
            assert slot["staff"] == 0
