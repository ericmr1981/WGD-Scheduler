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
    time_limit_seconds: int = 10,
) -> dict[str, Any]:
    """
    使用 CP-SAT 求解最优排班方案。

    Args:
        emp_names: 员工姓名列表 ["员工1", "员工2", ...]
        week_days: 一周天数，必须从周一开始 ["周一","周二",...,"周六","周日"]
        shifts: 班次定义列表 [Shift_A, Shift_B, Shift_C]
        productivity: 单人每小时产能
        demand_30min: {day: {time_str: 预估客流}}
        min_staff: 任何时段最低在岗人数
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

    # ── 所有 30 分钟时段 ─────────────────────────────────────────
    all_slot_times: list[str] = []
    for day_data in demand_30min.values():
        for t in day_data:
            if t not in all_slot_times:
                all_slot_times.append(t)
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

    # 1. 周六日全员到岗（week_days 须从周一开始）
    sat_idx = 5
    sun_idx = 6
    for e in range(num_emps):
        if num_days > sat_idx:
            model.Add(is_rest[(e, sat_idx)] == 0)
        if num_days > sun_idx:
            model.Add(is_rest[(e, sun_idx)] == 0)

    # 2. 无连续休息
    for e in range(num_emps):
        for d in range(num_days - 1):
            model.Add(is_rest[(e, d + 1)] == 0).OnlyEnforceIf(is_rest[(e, d)])

    # 3. 任何时段至少 min_staff 人在岗
    for d in range(num_days):
        for t in all_slot_times:
            model.Add(_staff_on_duty(d, t, is_shift_type, shift_covers, shift_names, num_emps) >= min_staff)

    # 4. 每人每天 ≤ 9h
    for e in range(num_emps):
        for d in range(num_days):
            duty_slots = 0
            for n in shift_names:
                duty_slots += is_shift_type[n][(e, d)] * len(shift_covers.get(n, set()))
            model.Add(duty_slots <= _MAX_SLOTS_PER_DAY)

    # 5. 每人每周 ≤ 54h（最多 6 个班次）
    for e in range(num_emps):
        work_days = model.NewIntVar(0, num_days, f"work_days_{e}")
        model.Add(work_days == sum(1 - is_rest[(e, d)] for d in range(num_days)))
        model.Add(work_days <= 6)

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
            gap = model.NewIntVar(0, demand, f"gap_{d}_{t.replace(':','_')}")
            model.Add(gap >= demand - staff_expr * productivity)
            gap_vars.append(gap)

    total_gap = model.NewIntVar(0, total_demand, "total_gap")
    model.Add(total_gap == sum(gap_vars))

    # ── 软约束：班次种类 ────────────────────────────────────────
    uses_shift: dict[str, cp_model.IntVar] = {}
    for n in shift_names:
        var = model.NewBoolVar(f"uses_{n}")
        all_uses = [is_shift_type[n][(e, d)] for e in range(num_emps) for d in range(num_days)]
        model.AddMaxEquality(var, all_uses)
        uses_shift[n] = var

    shift_type_count = model.NewIntVar(0, len(shift_names), "shift_type_count")
    model.Add(shift_type_count == sum(uses_shift.values()))

    # ── 组合目标 ─────────────────────────────────────────────────
    model.Minimize(_GAP_WEIGHT * total_gap + shift_type_count)

    # ── 求解 ─────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)

    # ── 处理结果 ─────────────────────────────────────────────────
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule: dict[str, dict[str, str | None]] = {}
        for e, emp in enumerate(emp_names):
            schedule[emp] = {}
            for d, day in enumerate(week_days):
                val = solver.Value(shift_var[(e, d)])
                schedule[emp][day] = None if val == 0 else shift_names[val - 1]

        coverage_report: list[dict] = []
        for d, day in enumerate(week_days):
            slots_report: list[dict] = []
            for t in all_slot_times:
                demand = demand_30min.get(day, {}).get(t, 0)
                staff_count = sum(
                    1 for e in range(num_emps)
                    for n in shift_names
                    if t in shift_covers.get(n, set())
                    and solver.Value(is_shift_type[n][(e, d)]) == 1
                )
                gap = max(0, demand - staff_count * productivity)
                if demand > 0 or staff_count > 0:
                    slots_report.append({
                        "time": t, "staff": staff_count,
                        "demand": demand, "gap": gap,
                    })
            coverage_report.append({"day": day, "slots": slots_report})

        status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        return {
            "status": status_str,
            "schedule": schedule,
            "gap_total": solver.Value(total_gap),
            "shift_types_used": solver.Value(shift_type_count),
            "coverage_report": coverage_report,
        }
    elif status == cp_model.INFEASIBLE:
        return {"status": "INFEASIBLE", "schedule": {}, "gap_total": -1,
                "shift_types_used": -1, "coverage_report": []}
    else:
        return {"status": "ERROR", "schedule": {}, "gap_total": -1,
                "shift_types_used": -1, "coverage_report": []}
