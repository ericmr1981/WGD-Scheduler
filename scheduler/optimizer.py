"""
CP-SAT 排班求解器

将排班问题建模为约束满足+优化问题，使用 Google OR-Tools 求解。
"""

from __future__ import annotations

from typing import Any

from scheduler.shifts import Shift

__all__ = ["optimize_schedule"]

_MAX_SLOTS_PER_DAY = 18  # 9 小时 ÷ 0.5h 每时段
_GAP_WEIGHT = 1000


def _staff_on_duty(
    day_idx: int,
    time_slot: str,
    is_shift_type: dict[str, dict[tuple[int, int], Any]],
    shift_covers: dict[str, set[str]],
    shift_names: list[str],
    num_emps: int,
) -> Any:
    """CP-SAT 表达式：某天某时段在岗员工数对应的 BoolVar 之和。"""
    expr = 0
    for e in range(num_emps):
        for n in shift_names:
            if time_slot in shift_covers.get(n, set()):
                expr += is_shift_type[n][(e, day_idx)]
    return expr


def optimize_schedule(
    emp_names: list[str],
    week_days: list[str],
    shifts: list[Shift],
    productivity: int,
    demand_30min: dict[str, dict[str, int]],
    min_staff: int = 1,
    peak_hourly_customers: int = 0,
    peak_periods: dict[str, str] | None = None,
    opening_staff_count: int = 1,
    open_hour: float = 10.0,
    opening_prep_mins: int = 60,
    num_solutions: int = 3,
    time_limit_seconds: int = 10,
) -> list[dict[str, Any]]:
    """
    使用 CP-SAT 求解最优排班方案。

    Args:
        emp_names: 员工姓名列表 ["员工1", "员工2", ...]
        week_days: 一周天数，必须从周一开始 ["周一","周二",...,"周六","周日"]
        shifts: 班次定义列表 [Shift_A, Shift_B, Shift_C]
        productivity: 单人每小时产能
        demand_30min: {day: {time_str: 预估客流}}
        min_staff: 任何时段最低在岗人数
        peak_hourly_customers: 本周高峰每小时客流量。传入后高峰期产能缺口权重视为 500
        peak_periods: 高峰时段定义 {"weekday_lunch":"12:00-14:00", ...}，与门店配置一致
        time_limit_seconds: 求解时间上限

    Returns:
        {
            "status": "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "ERROR",
            "schedule": {emp: {day: shift_name_or_none}},
            "gap_total": int,
            "shift_types_used": int,
            "coverage_report": [{"day": str, "slots": [{"time": str, "staff": int, "gap": int}]}],
        }
    """
    from ortools.sat.python import cp_model

    num_emps = len(emp_names)
    num_days = len(week_days)

    # ── 所有 30 分钟时段（含开早准备时段）─────────────────────────
    prep_start = open_hour - opening_prep_mins / 60
    all_slot_times: list[str] = []
    for day_data in demand_30min.values():
        for t in day_data:
            if t not in all_slot_times:
                all_slot_times.append(t)
    # 补充开早准备时段（保证硬约束和软约束能生效）
    t = prep_start
    while t < open_hour - 0.01:
        h, m = int(t), int(t % 1 * 60)
        slot = f"{h:02d}:{m:02d}"
        if slot not in all_slot_times:
            all_slot_times.append(slot)
        t += 0.5
    all_slot_times.sort()

    # 每个班次覆盖哪些时段
    shift_covers: dict[str, set[str]] = {}
    for s in shifts:
        covered: set[str] = set()
        for t in all_slot_times:
            h_str, m_str = t.split(":")
            time_val = int(h_str) + int(m_str) / 60
            if s.start <= time_val < s.end:
                covered.add(t)
        shift_covers[s.name] = covered

    shift_names = [s.name for s in shifts]

    # ── 建模型 ──────────────────────────────────────────────────
    model = cp_model.CpModel()

    # 变量: shift[e][d] ∈ {0, 1, ..., len(shifts)}  (0=休息)
    shift_var: dict[tuple[int, int], cp_model.IntVar] = {}
    for e in range(num_emps):
        for d in range(num_days):
            shift_var[(e, d)] = model.NewIntVar(0, len(shifts), f"shift_{e}_{d}")

    # 辅助 BoolVar
    is_rest: dict[tuple[int, int], cp_model.IntVar] = {}
    is_shift_type: dict[str, dict[tuple[int, int], cp_model.IntVar]] = {
        n: {} for n in shift_names
    }
    for e in range(num_emps):
        for d in range(num_days):
            is_rest[(e, d)] = model.NewBoolVar(f"rest_{e}_{d}")
            for n in shift_names:
                is_shift_type[n][(e, d)] = model.NewBoolVar(f"{n}_{e}_{d}")

            model.Add(
                is_rest[(e, d)]
                + sum(is_shift_type[n][(e, d)] for n in shift_names)
                == 1
            )
            model.Add(shift_var[(e, d)] == 0).OnlyEnforceIf(is_rest[(e, d)])
            for i, n in enumerate(shift_names):
                model.Add(shift_var[(e, d)] == i + 1).OnlyEnforceIf(
                    is_shift_type[n][(e, d)]
                )

    # ── 硬约束 ──────────────────────────────────────────────────

    # 1. 周六日全员到岗（按名称查找，支持不定长周）
    try:
        sat_idx = week_days.index("周六")
        for e in range(num_emps):
            model.Add(is_rest[(e, sat_idx)] == 0)
    except ValueError:
        pass
    try:
        sun_idx = week_days.index("周日")
        for e in range(num_emps):
            model.Add(is_rest[(e, sun_idx)] == 0)
    except ValueError:
        pass

    # 2. 无连续休息
    for e in range(num_emps):
        for d in range(num_days - 1):
            model.Add(is_rest[(e, d + 1)] == 0).OnlyEnforceIf(is_rest[(e, d)])

    # 3. 任何时段至少 min_staff 人在岗
    for d in range(num_days):
        for t in all_slot_times:
            model.Add(_staff_on_duty(d, t, is_shift_type, shift_covers, shift_names, num_emps) >= min_staff)

    # 4. 开早时段（开门前 prep 分钟）至少 1 人在岗
    opening_slots = [t for t in all_slot_times
                     if prep_start <= int(t.split(":")[0]) + int(t.split(":")[1]) / 60 < open_hour]
    if opening_slots:
        for d in range(num_days):
            for s in opening_slots:
                model.Add(
                    _staff_on_duty(d, s, is_shift_type, shift_covers, shift_names, num_emps)
                    >= 1
                )

    # 5. 每人每天 ≤ 9h
    for e in range(num_emps):
        for d in range(num_days):
            duty_slots = 0
            for n in shift_names:
                duty_slots += is_shift_type[n][(e, d)] * len(shift_covers.get(n, set()))
            model.Add(duty_slots <= _MAX_SLOTS_PER_DAY)

    # 6. 每人每周 ≤ 54h（整周工作 6 天休 1 天，短周最多休 1 天）
    for e in range(num_emps):
        work_days = model.NewIntVar(0, num_days, f"work_days_{e}")
        model.Add(work_days == sum(1 - is_rest[(e, d)] for d in range(num_days)))
        if num_days >= 7:
            model.Add(work_days == num_days - 1)  # 7 天工作 6 天，休 1 天
        else:
            model.Add(work_days >= num_days - 1)  # 短周最多休 1 天（可不休）

    # 7. 休息日均匀分布（工作日休息人数方差最小）
    weekday_rests: list[cp_model.IntVar] = []
    for d in range(min(5, num_days)):  # 周一到周五
        r = model.NewIntVar(0, num_emps, f"rest_cnt_{d}")
        model.Add(r == sum(is_rest[(e, d)] for e in range(num_emps)))
        weekday_rests.append(r)
    max_rest = model.NewIntVar(0, num_emps, "max_rest")
    min_rest = model.NewIntVar(0, num_emps, "min_rest")
    for r in weekday_rests:
        model.Add(max_rest >= r)
        model.Add(min_rest <= r)
    rest_range = model.NewIntVar(0, num_emps, "rest_range")
    model.Add(rest_range == max_rest - min_rest)

    # ── 软约束：产能缺口 ────────────────────────────────────────
    gap_vars: list[cp_model.IntVar] = []
    total_demand = 0
    for d in range(num_days):
        day_name = week_days[d]
        slot_list = sorted(demand_30min.get(day_name, {}).keys())
        for t in slot_list:
            demand = demand_30min[day_name][t]
            total_demand += demand
            staff_expr = _staff_on_duty(d, t, is_shift_type, shift_covers, shift_names, num_emps)
            # 产能每小时 → 30分钟: staff_expr * productivity / 2
            # gap >= demand - staff_expr * productivity / 2
            # → 2*gap >= 2*demand - staff_expr * productivity
            gap = model.NewIntVar(0, demand, f"gap_{d}_{t.replace(':','_')}")
            model.Add(2 * gap >= 2 * demand - staff_expr * productivity)
            gap_vars.append(gap)

    total_gap = model.NewIntVar(0, total_demand, "total_gap")
    model.Add(total_gap == sum(gap_vars))

    # ── 组合目标 ─────────────────────────────────────────────────
    # ── 软约束：高峰产能缺口（权重 500）──────────────────────────
    _PEAK_WEIGHT = 500
    peak_gap_total = 0
    if peak_hourly_customers > 0 and peak_periods:
        # 解析高峰时段 {"weekday_lunch":"12:00-14:00", ...}
        def _in_peak(t: str, day_name: str) -> bool:
            h = int(t.split(":")[0])
            m = int(t.split(":")[1])
            tv = h + m / 60
            is_we = day_name in {"周六", "周日"}
            if is_we:
                ranges = [
                    peak_periods.get("weekend_lunch", "11:00-14:00"),
                    peak_periods.get("weekend_dinner", "16:00-20:00"),
                ]
            else:
                ranges = [
                    peak_periods.get("weekday_lunch", "12:00-14:00"),
                    peak_periods.get("weekday_dinner", "17:00-19:00"),
                ]
            for r in ranges:
                parts = r.replace("：", ":").replace("－", "-").replace("—", "-").split("-")
                try:
                    sh = int(parts[0].split(":")[0])
                    eh = int(parts[1].split(":")[0])
                    if sh <= tv < eh:
                        return True
                except (IndexError, ValueError):
                    pass
            return False

        peak_gaps: list[cp_model.IntVar] = []
        for d in range(num_days):
            day_name = week_days[d]
            slot_list = sorted(demand_30min.get(day_name, {}).keys())
            for t in slot_list:
                if not _in_peak(t, day_name):
                    continue
                demand = demand_30min[day_name][t]
                staff_expr = _staff_on_duty(d, t, is_shift_type, shift_covers, shift_names, num_emps)
                # 高峰时段要求的产能: peak_hourly_customers / 2 (30min)
                # gap >= peak_30min - staff_expr * productivity / 2
                # 2*gap >= peak_hourly_customers - staff_expr * productivity
                needed = peak_hourly_customers  # 每小时
                pg = model.NewIntVar(0, needed, f"pg_{d}_{t.replace(':','_')}")
                model.Add(2 * pg >= needed - staff_expr * productivity)
                peak_gaps.append(pg)

        if peak_gaps:
            pg_max = peak_hourly_customers * len(peak_gaps)
            peak_gap_total = model.NewIntVar(0, pg_max, "peak_gap_total")
            model.Add(peak_gap_total == sum(peak_gaps))

    _REST_FAIRNESS_WEIGHT = 100

    # ── 软约束：开早时段人数越少越好 ────────────────────────────
    opening_staff_vars: list[cp_model.IntVar] = []
    if opening_slots:
        for d in range(num_days):
            for s in opening_slots:
                opening_staff_vars.append(
                    _staff_on_duty(d, s, is_shift_type, shift_covers, shift_names, num_emps)
                )
    total_opening_staff = model.NewIntVar(0, num_emps * num_days * len(opening_slots or [1]), "total_opening_staff")
    model.Add(total_opening_staff == sum(opening_staff_vars))

    obj_expr = _GAP_WEIGHT * total_gap + _PEAK_WEIGHT * peak_gap_total + _REST_FAIRNESS_WEIGHT * rest_range + 400 * total_opening_staff
    model.Minimize(obj_expr)

    def _extract(slv: cp_model.CpSolver) -> dict:
        schedule: dict[str, dict[str, str | None]] = {}
        for e, emp in enumerate(emp_names):
            schedule[emp] = {}
            for d, day in enumerate(week_days):
                val = slv.Value(shift_var[(e, d)])
                schedule[emp][day] = None if val == 0 else shift_names[val - 1]
        coverage_report = []
        for d, day in enumerate(week_days):
            slots_report = []
            for t in all_slot_times:
                demand = demand_30min.get(day, {}).get(t, 0)
                staff_count = sum(
                    1 for e in range(num_emps) for n in shift_names
                    if t in shift_covers.get(n, set()) and slv.Value(is_shift_type[n][(e, d)]) == 1
                )
                gap = max(0, demand - staff_count * productivity)
                if demand > 0 or staff_count > 0:
                    slots_report.append({"time": t, "staff": staff_count, "demand": demand, "gap": gap})
            coverage_report.append({"day": day, "slots": slots_report})
        return {"schedule": schedule, "gap_total": slv.Value(total_gap),
                "coverage_report": coverage_report}

    # ── 求解（多次，收集 top N）─────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1  # macOS compat: avoid thread hang
    results: list[dict] = []

    for sol_idx in range(num_solutions):
        status = solver.Solve(model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            sol = _extract(solver)
            sol["status"] = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
            sol["objective"] = int(solver.ObjectiveValue())
            results.append(sol)
            if sol_idx < num_solutions - 1:
                model.Add(obj_expr > int(solver.ObjectiveValue()))
        else:
            break

    if results:
        return results
    if status == cp_model.INFEASIBLE:
        return [{"status": "INFEASIBLE", "schedule": {}, "gap_total": -1, "coverage_report": []}]
    return [{"status": "ERROR", "schedule": {}, "gap_total": -1, "coverage_report": []}]
