"""Tests for the CP-SAT scheduler optimizer."""

from scheduler.shifts import calculate_shifts
from scheduler.optimizer import optimize_schedule


def test_3_emp_basic_coverage():
    """3 employees, standard params: all hard constraints satisfied."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2", "员工3"]
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    demand_30min = {}
    for day in week_days:
        slots = {}
        for s in range(9 * 2, 23 * 2):
            h = s // 2
            m = "00" if s % 2 == 0 else "30"
            t = f"{h:02d}:{m}"
            if (12 <= h < 14) or (17 <= h < 19):
                slots[t] = 60
            else:
                slots[t] = 20
        demand_30min[day] = slots

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE"), f"Failed: {result['status']}"
    schedule = result["schedule"]

    for emp in emp_names:
        assert schedule[emp]["周六"] is not None, f"{emp} 周六休息"
        assert schedule[emp]["周日"] is not None, f"{emp} 周日休息"

    for emp in emp_names:
        prev_rest = False
        for day in week_days:
            is_rest = schedule[emp][day] is None
            if prev_rest and is_rest:
                assert False, f"{emp} 连续休息"
            prev_rest = is_rest

    for emp in emp_names:
        rest_days = sum(1 for d in week_days if schedule[emp][d] is None)
        assert rest_days <= 1, f"{emp} 休息 {rest_days} 天"

    assert len(result["coverage_report"]) == 7
    assert result["gap_total"] >= 0


def test_weekend_full_staff_enforced():
    """Weekend constraint: all employees present Sat and Sun."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2"]
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    demand_30min = {}
    for day in week_days:
        slots = {}
        for s in range(9 * 2, 23 * 2):
            h = s // 2
            m = "00" if s % 2 == 0 else "30"
            slots[f"{h:02d}:{m}"] = 10
        demand_30min[day] = slots

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    for emp in emp_names:
        assert result["schedule"][emp]["周六"] is not None
        assert result["schedule"][emp]["周日"] is not None


def test_no_consecutive_rest():
    """No consecutive rest constraint."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2", "员工3"]
    week_days = ["周一", "周二", "周三", "周四", "周五"]

    demand_30min = {}
    for day in week_days:
        slots = {}
        for s in range(9 * 2, 23 * 2):
            h = s // 2
            m = "00" if s % 2 == 0 else "30"
            slots[f"{h:02d}:{m}"] = 10
        demand_30min[day] = slots

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    for emp in emp_names:
        prev_rest = False
        for day in week_days:
            is_rest = result["schedule"][emp][day] is None
            assert not (prev_rest and is_rest), f"{emp} consecutive rest"
            prev_rest = is_rest


def test_shift_type_minimization():
    """With 2 employees and low demand, optimizer should use fewer shift types."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2"]
    week_days = ["周一"]

    demand_30min = {"周一": {}}
    for s in range(9 * 2, 23 * 2):
        h = s // 2
        m = "00" if s % 2 == 0 else "30"
        demand_30min["周一"][f"{h:02d}:{m}"] = 3

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert result["shift_types_used"] <= 2
