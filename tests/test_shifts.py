"""
Tests for scheduler/shifts.py — shift definitions and generation
"""

from scheduler.shifts import (
    get_shifts,
    rotate_shifts,
    generate_weekly_schedule,
    get_hourly_coverage,
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
        # rotation = 1 % 3 = 1, so shift by 1
        employees = list(current.keys())
        assert result[employees[0]] == "B"  # A → B
        assert result[employees[1]] == "C"  # B → C
        assert result[employees[2]] == "A"  # C → A

    def test_no_rotation_week_0(self):
        current = {"张三": "A", "李四": "B", "王五": "C"}
        result = rotate_shifts(current, week_number=0)
        assert result == current

    def test_full_cycle(self):
        """After 3 weeks, should return to original"""
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

        # 张三休息周二
        assert schedule["张三"]["周二"] is None
        # 张三其他天是A班
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


class TestGetHourlyCoverage:
    def test_single_employee(self):
        schedule = {
            "张三": {
                "周一": "A",  # 10:00-18:00
            }
        }
        shifts = get_shifts()
        coverage = get_hourly_coverage(schedule, shifts, "周一")
        assert len(coverage) == 12  # 10:00-21:00
        # A shift covers 10-17 (8 hour slots)
        assert coverage[0] == 1  # 10:00
        assert coverage[7] == 1  # 17:00
        assert coverage[8] == 0  # 18:00 - A班结束

    def test_two_employees_overlap(self):
        schedule = {
            "张三": {"周一": "A"},  # 10:00-18:00
            "李四": {"周一": "B"},  # 12:00-20:00
        }
        shifts = get_shifts()
        coverage = get_hourly_coverage(schedule, shifts, "周一")
        assert coverage[0] == 1  # 10:00 - only A
        assert coverage[2] == 2  # 12:00 - A + B
        assert coverage[8] == 1  # 18:00 - only B
